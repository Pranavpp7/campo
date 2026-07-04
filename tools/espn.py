import time
import requests
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from tools.competitions import ACTIVE

# ── Config ────────────────────────────────────────────────────────────────────
# ESPN's unofficial API
BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"
# League slug comes from the competition registry (fifa.world, eng.1, ...).
# None means ESPN coverage is disabled for this competition — the tools
# return an honest "not available" instead of querying the wrong league.
WC_LEAGUE = ACTIVE.espn_slug

_NO_ESPN = (
    f"ESPN coverage is not configured for the {ACTIVE.label} — "
    "use the other data tools or web_search instead."
)

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

TTL_SCORES = 60          # 1 minute — live scores change fast
TTL_SUMMARY = 5 * 60     # 5 minutes — match summaries
TTL_NEWS = 10 * 60       # 10 minutes — news updates
TTL_STANDINGS = 30 * 60  # 30 minutes — standings

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
        params=params,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()

# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def get_live_scores() -> str:
    """Get current live and recent scores for the competition from ESPN.

    Use this for:
    - Live match scores and current game state
    - Today's completed results
    - Upcoming matches today

    Returns:
        Live scores, match status, and scorers.
    """
    if WC_LEAGUE is None:
        return _NO_ESPN
    cache_key = "espn_live_scores"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        data = _api_get(f"{WC_LEAGUE}/scoreboard")
        events = data.get("events", [])

        if not events:
            return "No live or recent World Cup matches found on ESPN."

        lines = []
        for event in events:
            name = event.get("name", "Unknown Match")
            status = event["status"]["type"]["description"]
            competitions = event.get("competitions", [{}])
            competitors = competitions[0].get("competitors", [])

            if len(competitors) == 2:
                home = competitors[0]
                away = competitors[1]
                home_name = home["team"]["displayName"]
                away_name = away["team"]["displayName"]
                home_score = home.get("score", "?")
                away_score = away.get("score", "?")
                lines.append(
                    f"{name} [{status}]: {home_name} {home_score} - {away_score} {away_name}"
                )

        output = "\n".join(lines) if lines else "No matches available."
        _set_cached(cache_key, output, TTL_SCORES)
        return output

    except Exception as e:
        return f"Error fetching live scores: {str(e)}"


@tool
def get_match_summary(event_id: str) -> str:
    """Get detailed summary of a specific match from ESPN.

    Use this after get_live_scores to get deeper details on a specific match
    including scorers, cards, and key events.

    Args:
        event_id: ESPN event ID from get_live_scores

    Returns:
        Match summary with scorers, cards, possession stats.
    """
    if WC_LEAGUE is None:
        return _NO_ESPN
    cache_key = f"espn_summary_{event_id}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        data = _api_get(f"{WC_LEAGUE}/summary", {"event": event_id})

        lines = []

        # Key events (goals, cards)
        scoring_plays = data.get("scoringPlays", [])
        if scoring_plays:
            lines.append("Goals:")
            for play in scoring_plays:
                team = play.get("team", {}).get("displayName", "Unknown")
                clock = play.get("clock", {}).get("displayValue", "?")
                text = play.get("text", "Goal")
                lines.append(f"  {clock}' - {team}: {text}")

        # Stats
        boxscore = data.get("boxscore", {})
        teams = boxscore.get("teams", [])
        if teams:
            lines.append("\nStats:")
            for team_data in teams:
                team_name = team_data.get("team", {}).get("displayName", "Unknown")
                stats = team_data.get("statistics", [])
                for stat in stats[:5]:  # top 5 stats
                    lines.append(
                        f"  {team_name} - {stat.get('label', '')}: {stat.get('displayValue', '')}"
                    )

        output = "\n".join(lines) if lines else "No detailed summary available."
        _set_cached(cache_key, output, TTL_SUMMARY)
        return output

    except Exception as e:
        return f"Error fetching match summary: {str(e)}"


@tool
def get_team_news(team_name: str) -> str:
    """Get latest ESPN news for a team in the competition.

    Use this to find recent injury reports, press conference quotes,
    and team news that might affect match analysis.

    Args:
        team_name: Team name (e.g. "France", "Brazil", "Arsenal")

    Returns:
        Latest news headlines and summaries for the team.
    """
    if WC_LEAGUE is None:
        return _NO_ESPN
    cache_key = f"espn_news_{team_name.lower()}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        data = _api_get(
            f"{WC_LEAGUE}/news",
            {"limit": 5, "team": team_name}
        )

        articles = data.get("articles", [])
        if not articles:
            return f"No recent ESPN news found for {team_name}."

        lines = [f"Latest ESPN news for {team_name}:"]
        for article in articles[:5]:
            headline = article.get("headline", "No headline")
            description = article.get("description", "")
            published = article.get("published", "")[:10]
            lines.append(f"\n{published}: {headline}")
            if description:
                lines.append(f"  {description[:150]}...")

        output = "\n".join(lines)
        _set_cached(cache_key, output, TTL_NEWS)
        return output

    except Exception as e:
        return f"Error fetching news for {team_name}: {str(e)}"