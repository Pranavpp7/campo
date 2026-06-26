from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from datetime import datetime, timezone
import time

from agents.orchestrator import run_orchestrator

load_dotenv()

app = FastAPI(title="Campo API", version="1.0.0")

# ── CORS ─────────────────────────────────────────────────────────────────────
# Browsers treat localhost and 127.0.0.1 as distinct origins, so allow both —
# the dev frontend may be opened under either hostname on port 3000.
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Schemas ───────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    session_id: str
    message: str
    user_id: str | None = None

class ChatResponse(BaseModel):
    response: str
    agents_used: list[str]
    trace_url: str | None
    latency_ms: int

# ── Structured (typed) data models for the Today screen ────────────────────────
class TeamOut(BaseModel):
    name: str | None = None
    crest: str | None = None

class MatchOut(BaseModel):
    utc_date: str | None = None
    home: TeamOut
    away: TeamOut
    home_score: int | None = None
    away_score: int | None = None
    status: str | None = None
    venue: str | None = None
    group: str | None = None

class StandingRowOut(BaseModel):
    position: int | None = None
    team: TeamOut
    points: int | None = None
    won: int | None = None
    draw: int | None = None
    lost: int | None = None
    goals_for: int | None = None
    goals_against: int | None = None
    goal_difference: int | None = None

class StandingsGroupOut(BaseModel):
    group: str | None = None
    table: list[StandingRowOut]

class TodayDataResponse(BaseModel):
    matches: list[MatchOut]
    recent_matches: list[MatchOut]
    standings: list[StandingsGroupOut]
    as_of: str
    errors: dict[str, str] | None = None

class StandingsDataResponse(BaseModel):
    standings: list[StandingsGroupOut]
    as_of: str
    error: str | None = None

# ── Routes ────────────────────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    start = time.time()

    user_id = request.user_id or request.session_id

    result = await run_orchestrator(
        message=request.message,
        session_id=request.session_id,
        user_id=user_id,
    )

    latency = int((time.time() - start) * 1000)

    return ChatResponse(
        response=result["response"],
        agents_used=result["agents_used"],
        trace_url=None,
        latency_ms=latency,
    )

@app.get("/today")
async def today():
    """Deterministic data endpoint for the Today screen.

    Calls the football-data tool functions directly — NO LLM, NO agent,
    NO orchestrator. Just a structured JSON pass-through of the tools' output.

    NOTE: get_wc_matches / get_wc_standings are LangChain @tool objects that
    return preformatted strings, so this returns the documented `*_text`
    fallback shape rather than structured `matches: [...]` / `standings: [...]`
    arrays. See the report for what a structured variant would require.
    """
    # Lazy import to avoid paying the tools' import cost at app startup.
    from tools.football_data import get_wc_matches, get_wc_standings

    errors: dict[str, str] = {}
    upcoming_text = None
    recent_text = None
    standings_text = None

    # Upcoming fixtures.
    try:
        upcoming_text = get_wc_matches.invoke({"status": "SCHEDULED"})
    except Exception as e:
        errors["upcoming_matches"] = str(e)

    # Recent / completed results.
    try:
        recent_text = get_wc_matches.invoke({"status": "FINISHED"})
    except Exception as e:
        errors["recent_matches"] = str(e)

    # Group standings.
    try:
        standings_text = get_wc_standings.invoke({})
    except Exception as e:
        errors["standings"] = str(e)

    response: dict = {
        "matches_text": upcoming_text,
        "recent_matches_text": recent_text,
        "standings_text": standings_text,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }
    if errors:
        # Partial success: return whatever succeeded and note what failed.
        response["errors"] = errors
    return response


@app.get("/standings")
async def standings():
    """Deterministic data endpoint for group standings.

    Calls get_wc_standings() directly — NO LLM, NO agent, NO orchestrator.
    The tool returns a preformatted string, so this passes it through as
    `standings_text`.
    """
    from tools.football_data import get_wc_standings

    response: dict = {
        "standings_text": None,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }
    try:
        response["standings_text"] = get_wc_standings.invoke({})
    except Exception as e:
        response["error"] = str(e)
    return response


@app.get("/today-data", response_model=TodayDataResponse)
async def today_data():
    """Structured (typed) data endpoint for the Today screen.

    Calls the structured *_data tool functions directly — NO LLM, NO agent,
    NO orchestrator. Returns real JSON arrays (match cards, standings rows)
    that a fan UI can bind to, unlike the string-based /today endpoint.
    """
    from tools.football_data import get_wc_matches_data, get_wc_standings_data

    errors: dict[str, str] = {}
    upcoming: list[dict] = []
    recent: list[dict] = []
    groups: list[dict] = []

    try:
        upcoming = get_wc_matches_data("SCHEDULED")
    except Exception as e:
        errors["upcoming_matches"] = str(e)

    try:
        recent = get_wc_matches_data("FINISHED")
    except Exception as e:
        errors["recent_matches"] = str(e)

    try:
        groups = get_wc_standings_data()
    except Exception as e:
        errors["standings"] = str(e)

    return TodayDataResponse(
        matches=upcoming,
        recent_matches=recent,
        standings=groups,
        as_of=datetime.now(timezone.utc).isoformat(),
        errors=errors or None,
    )


@app.get("/standings-data", response_model=StandingsDataResponse)
async def standings_data():
    """Structured (typed) standings endpoint.

    Calls get_wc_standings_data() directly — NO LLM, NO agent, NO orchestrator.
    Returns structured group/table JSON for a sortable standings UI.
    """
    from tools.football_data import get_wc_standings_data

    try:
        groups = get_wc_standings_data()
        return StandingsDataResponse(
            standings=groups,
            as_of=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        return StandingsDataResponse(
            standings=[],
            as_of=datetime.now(timezone.utc).isoformat(),
            error=str(e),
        )


@app.get("/health")
async def health():
    return {"status": "ok"}