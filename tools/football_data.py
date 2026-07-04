import os
import time
import requests
from datetime import date, datetime, timedelta, timezone
from dotenv import load_dotenv
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
API_KEY = os.getenv("FOOTBALL_DATA_API_KEY")
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": API_KEY}
# Competition to serve. Defaults to the 2026 FIFA World Cup; point it at any
# football-data.org competition code (PL, CL, ...) to reuse Campo for another
# tournament or league season.
WC_CODE = os.getenv("COMPETITION_CODE", "WC")

# Reference timezone for what counts as "today". Venues span UTC-4 (East
# Coast) to UTC-7 (Pacific); UTC-5 (central) is the compromise that keeps an
# evening kickoff on the correct fan-facing day even though its utcDate has
# already rolled over to tomorrow.
TOURNAMENT_TZ = timezone(timedelta(hours=-5))

# ── TTL Cache ─────────────────────────────────────────────────────────────────
_cache: dict = {}

def _get_cached_entry(key: str) -> dict | None:
    entry = _cache.get(key)
    if entry and time.time() < entry["expires_at"]:
        return entry
    return None

def _get_cached(key: str):
    entry = _get_cached_entry(key)
    return entry["data"] if entry else None

def _set_cached(key: str, data, ttl_seconds: int) -> str:
    """Cache `data` and return the fetch timestamp recorded for it."""
    fetched_at = datetime.now(timezone.utc).isoformat()
    _cache[key] = {
        "data": data,
        "expires_at": time.time() + ttl_seconds,
        "fetched_at": fetched_at,
    }
    return fetched_at

TTL_MATCHES = 6 * 3600    # 6 hours
TTL_SQUADS  = 24 * 3600   # 24 hours — squads rarely change
TTL_STANDINGS = 3 * 3600  # 3 hours
# The Today screen shows live scores, so its data ages much faster than the
# LLM-tool caches above.
TTL_TODAY = 120           # 2 minutes — today's matches, including live scores
TTL_RECENT = 30 * 60      # 30 minutes — finished results don't change
TTL_STANDINGS_DATA = 30 * 60

# ── Retry ─────────────────────────────────────────────────────────────────────
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def _api_get(endpoint: str, params: dict = {}) -> dict:
    if not API_KEY:
        raise RuntimeError(
            "FOOTBALL_DATA_API_KEY is not set — add it to your .env file."
        )
    response = requests.get(
        f"{BASE_URL}/{endpoint}",
        headers=HEADERS,
        params=params,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()

# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def get_wc_matches(status: str = "SCHEDULED") -> str:
    """Get 2026 FIFA World Cup matches filtered by status.

    Use this to find upcoming matches, live scores, or completed results.

    Args:
        status: One of SCHEDULED, LIVE, IN_PLAY, PAUSED, FINISHED, POSTPONED
                Use SCHEDULED for upcoming matches.
                Use FINISHED for completed results.
                Use LIVE or IN_PLAY for live matches.

    Returns:
        List of matches with teams, scores, dates and venues.
    """
    cache_key = f"wc_matches_{status}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        data = _api_get(f"competitions/{WC_CODE}/matches", {"status": status})
        matches = data.get("matches", [])

        if not matches:
            # Cache the empty result too — otherwise every call during a
            # matchless period hits the rate-limited API.
            output = f"No {status} matches found for the 2026 World Cup."
            _set_cached(cache_key, output, TTL_MATCHES)
            return output

        lines = []
        for m in matches[:20]:  # cap at 20 to avoid token overflow
            home = m["homeTeam"]["name"]
            away = m["awayTeam"]["name"]
            date = m["utcDate"][:10]
            time_utc = m["utcDate"][11:16]
            score = m.get("score", {})
            ft = score.get("fullTime", {})
            home_score = ft.get("home")
            away_score = ft.get("away")

            if home_score is not None:
                lines.append(f"{date} {time_utc} UTC | {home} {home_score} - {away_score} {away}")
            else:
                lines.append(f"{date} {time_utc} UTC | {home} vs {away}")

        output = "\n".join(lines)
        _set_cached(cache_key, output, TTL_MATCHES)
        return output

    except Exception as e:
        return f"Error fetching WC matches: {str(e)}"


@tool
def get_team_squad(team_name: str) -> str:
    """Get the full squad for a World Cup 2026 team including player positions.

    Use this to check who is in a team's squad before asking about specific players.
    Useful for injury context — if a player isn't listed they may be injured or excluded.

    Args:
        team_name: Country name (e.g. "France", "Brazil", "United States")

    Returns:
        Full squad with player names, positions and dates of birth.
    """
    cache_key = f"team_squad_{team_name.lower()}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        data = _api_get(f"competitions/{WC_CODE}/teams")
        teams = data.get("teams", [])

        # Find the team by name (case-insensitive partial match)
        matched = None
        for team in teams:
            if team_name.lower() in team["name"].lower():
                matched = team
                break

        if not matched:
            available = [t["name"] for t in teams]
            return f"Team '{team_name}' not found. Available teams: {', '.join(available[:20])}"

        squad = matched.get("squad", [])
        if not squad:
            return f"No squad data available for {matched['name']}."

        lines = [f"Squad: {matched['name']} (Coach: {matched.get('coach', {}).get('name', 'Unknown')})"]
        lines.append("-" * 40)

        for pos in ["Goalkeeper", "Defence", "Midfield", "Offence"]:
            players = [p for p in squad if p["position"] == pos]
            if players:
                lines.append(f"\n{pos}:")
                for p in players:
                    lines.append(f"  - {p['name']} (born {p.get('dateOfBirth', 'N/A')})")

        output = "\n".join(lines)
        _set_cached(cache_key, output, TTL_SQUADS)
        return output

    except Exception as e:
        return f"Error fetching squad for '{team_name}': {str(e)}"


@tool
def get_wc_standings() -> str:
    """Get the current 2026 FIFA World Cup group stage standings.

    Use this to understand which teams are advancing, their points,
    goal difference, and current group position.

    Returns:
        Group standings table with points, wins, draws, losses and goal difference.
    """
    cache_key = "wc_standings"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        data = _api_get(f"competitions/{WC_CODE}/standings")
        standings = data.get("standings", [])

        if not standings:
            return "No standings available yet — group stage may not have started."

        lines = []
        for group in standings:
            group_name = group.get("group", "Group")
            lines.append(f"\n{group_name}:")
            lines.append(f"{'Pos':<4} {'Team':<25} {'Pts':<5} {'W':<4} {'D':<4} {'L':<4} {'GD'}")
            lines.append("-" * 55)
            for entry in group["table"]:
                lines.append(
                    f"{entry['position']:<4} "
                    f"{entry['team']['name']:<25} "
                    f"{entry['points']:<5} "
                    f"{entry['won']:<4} "
                    f"{entry['draw']:<4} "
                    f"{entry['lost']:<4} "
                    f"{entry['goalDifference']:+}"
                )

        output = "\n".join(lines)
        _set_cached(cache_key, output, TTL_STANDINGS)
        return output

    except Exception as e:
        return f"Error fetching standings: {str(e)}"


# ── Structured data functions (for REST endpoints, NOT agents) ──────────────────
# These return parsed JSON-serialisable structures instead of display strings.
# They are intentionally NOT @tool decorated — they're meant to be called
# directly by API endpoints that power a fan-facing UI. Exceptions propagate so
# the caller (the endpoint) can decide how to surface partial failures.
#
# Each returns (data, fetched_at) where fetched_at is the ISO timestamp of the
# actual upstream fetch — cached responses keep their original stamp so the UI
# can report data age honestly.

def _normalize_status(raw: str | None) -> str:
    """Collapse football-data.org's status vocabulary (TIMED, IN_PLAY, PAUSED,
    AWARDED, …) into the three states the UI renders."""
    if raw in ("IN_PLAY", "PAUSED", "LIVE"):
        return "LIVE"
    if raw in ("FINISHED", "AWARDED"):
        return "FINISHED"
    return "SCHEDULED"


def _shape_match(m: dict) -> dict:
    home_team = m.get("homeTeam", {})
    away_team = m.get("awayTeam", {})
    ft = m.get("score", {}).get("fullTime", {})
    return {
        "id": m.get("id"),
        "utc_date": m.get("utcDate"),
        "home": {"name": home_team.get("name"), "crest": home_team.get("crest")},
        "away": {"name": away_team.get("name"), "crest": away_team.get("crest")},
        "home_score": ft.get("home"),
        "away_score": ft.get("away"),
        "status": _normalize_status(m.get("status")),
        "venue": m.get("venue"),
        "group": m.get("group") or m.get("stage"),
    }


def _local_date(utc_iso: str | None) -> date | None:
    """The tournament-local calendar date a UTC kickoff falls on."""
    if not utc_iso:
        return None
    try:
        dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(TOURNAMENT_TZ).date()


def get_wc_today_matches_data() -> tuple[list[dict], str]:
    """Today's 2026 World Cup matches in every state — upcoming, live and
    finished — so a live match never disappears from the Today screen.

    Fetched by date window rather than status: a status filter would miss
    TIMED (confirmed-kickoff) and IN_PLAY/PAUSED (live) matches entirely.
    """
    cache_key = "wc_today_matches_data"
    entry = _get_cached_entry(cache_key)
    if entry is not None:
        return entry["data"], entry["fetched_at"]

    today = datetime.now(TOURNAMENT_TZ).date()
    # A tournament-local day spans two UTC dates, so over-fetch a 2-day UTC
    # window and filter to the exact local day below.
    data = _api_get(f"competitions/{WC_CODE}/matches", {
        "dateFrom": today.isoformat(),
        "dateTo": (today + timedelta(days=2)).isoformat(),
    })
    matches = [
        _shape_match(m)
        for m in data.get("matches", [])
        if _local_date(m.get("utcDate")) == today
    ]
    matches.sort(key=lambda m: m["utc_date"] or "")

    fetched_at = _set_cached(cache_key, matches, TTL_TODAY)
    return matches, fetched_at


def get_wc_recent_results_data(days: int = 4, limit: int = 12) -> tuple[list[dict], str]:
    """Finished 2026 World Cup matches from the last `days` days, newest
    first, excluding today's (which the today feed already covers)."""
    cache_key = "wc_recent_results_data"
    entry = _get_cached_entry(cache_key)
    if entry is not None:
        return entry["data"], entry["fetched_at"]

    today = datetime.now(TOURNAMENT_TZ).date()
    data = _api_get(f"competitions/{WC_CODE}/matches", {
        "status": "FINISHED",
        "dateFrom": (today - timedelta(days=days)).isoformat(),
        "dateTo": (today + timedelta(days=1)).isoformat(),
    })
    finished = []
    for m in data.get("matches", []):
        local = _local_date(m.get("utcDate"))
        if local is not None and local < today:
            finished.append(_shape_match(m))
    finished.sort(key=lambda m: m["utc_date"] or "", reverse=True)
    result = finished[:limit]

    fetched_at = _set_cached(cache_key, result, TTL_RECENT)
    return result, fetched_at


def get_wc_standings_data() -> tuple[list[dict], str]:
    """Structured 2026 World Cup group stage standings.

    Returns:
        (groups, fetched_at) where groups is a list of:
        {
            "group": str,
            "table": [
                {
                    "position": int,
                    "team": {"name": str, "crest": str | None},
                    "played": int,
                    "points": int,
                    "won": int,
                    "draw": int,
                    "lost": int,
                    "goals_for": int,
                    "goals_against": int,
                    "goal_difference": int,
                },
                ...
            ],
        }
    """
    cache_key = "wc_standings_data"
    entry = _get_cached_entry(cache_key)
    if entry is not None:
        return entry["data"], entry["fetched_at"]

    data = _api_get(f"competitions/{WC_CODE}/standings")
    standings = data.get("standings", [])

    result = []
    for group in standings:
        table = []
        for entry in group.get("table", []):
            team = entry.get("team", {})
            table.append({
                "position": entry.get("position"),
                "team": {"name": team.get("name"), "crest": team.get("crest")},
                "played": entry.get("playedGames"),
                "points": entry.get("points"),
                "won": entry.get("won"),
                "draw": entry.get("draw"),
                "lost": entry.get("lost"),
                "goals_for": entry.get("goalsFor"),
                "goals_against": entry.get("goalsAgainst"),
                "goal_difference": entry.get("goalDifference"),
            })
        result.append({
            "group": group.get("group"),
            "table": table,
        })

    fetched_at = _set_cached(cache_key, result, TTL_STANDINGS_DATA)
    return result, fetched_at


TTL_MATCH_DETAIL = 10 * 60  # 10 minutes — single-match detail for brief generation


def get_match_data(match_id: int) -> tuple[dict, str]:
    """Structured detail for a single match by football-data.org id.

    Used by the brief pipeline to anchor a brief to a concrete fixture.
    Returns the `_shape_match` shape plus `stage` and `referees`.
    Raises on unknown id / upstream failure — callers decide how to surface it.
    """
    cache_key = f"match_data_{match_id}"
    entry = _get_cached_entry(cache_key)
    if entry is not None:
        return entry["data"], entry["fetched_at"]

    m = _api_get(f"matches/{match_id}")
    # The single-match endpoint nests the payload under "match" on some plans
    # and returns it flat on others — handle both.
    m = m.get("match", m)

    shaped = _shape_match(m)
    shaped["stage"] = m.get("stage")
    shaped["referees"] = [
        r.get("name") for r in m.get("referees", []) if r.get("name")
    ]

    fetched_at = _set_cached(cache_key, shaped, TTL_MATCH_DETAIL)
    return shaped, fetched_at