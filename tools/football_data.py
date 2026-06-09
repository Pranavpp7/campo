import os
import time
import requests
from dotenv import load_dotenv
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
API_KEY = os.getenv("FOOTBALL_DATA_API_KEY")
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": API_KEY}
WC_CODE = "WC"  # 2026 FIFA World Cup competition code

# ── TTL Cache ─────────────────────────────────────────────────────────────────
_cache: dict = {}

def _get_cached(key: str):
    if key in _cache:
        if time.time() < _cache[key]["expires_at"]:
            return _cache[key]["data"]
    return None

def _set_cached(key: str, data, ttl_seconds: int):
    _cache[key] = {
        "data": data,
        "expires_at": time.time() + ttl_seconds,
    }

TTL_MATCHES = 6 * 3600    # 6 hours
TTL_SQUADS  = 24 * 3600   # 24 hours — squads rarely change
TTL_STANDINGS = 3 * 3600  # 3 hours

# ── Retry ─────────────────────────────────────────────────────────────────────
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def _api_get(endpoint: str, params: dict = {}) -> dict:
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
            return f"No {status} matches found for the 2026 World Cup."

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