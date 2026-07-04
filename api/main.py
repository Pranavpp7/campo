from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from datetime import datetime, timezone
import asyncio
import os
import time

from agents.orchestrator import run_orchestrator

load_dotenv()

# ── Scheduled brief generation ────────────────────────────────────────────────
# Pre-generates briefs for today's matches so fans open a ready brief instead
# of watching a ~1-minute pipeline run. Off by default (and in tests) — enable
# with BRIEFS_AUTO_GENERATE=true.

BRIEF_SCAN_INTERVAL_MINUTES = 30


async def auto_generate_briefs():
    """Scan today's fixtures and generate any missing briefs, one at a time —
    each brief already runs 4 parallel workers, so parallelism across matches
    would just trip free-tier LLM rate limits."""
    from tools.football_data import get_wc_today_matches_data
    from briefs.store import get_brief, try_acquire_generation_lock
    from briefs.pipeline import generate_and_store

    try:
        matches, _ = await asyncio.to_thread(get_wc_today_matches_data)
    except Exception as e:
        print(f"[briefs-scheduler] could not fetch today's matches: {e}")
        return

    for m in matches:
        match_id = m.get("id")
        if match_id is None or m.get("status") == "FINISHED":
            continue
        record = await get_brief(match_id)
        if record and record.get("status") == "ready":
            continue
        if not await try_acquire_generation_lock(match_id):
            continue  # another worker (or a manual trigger) is already on it
        home = (m.get("home") or {}).get("name")
        away = (m.get("away") or {}).get("name")
        print(f"[briefs-scheduler] generating brief for {home} vs {away} ({match_id})")
        await generate_and_store(match_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if os.getenv("BRIEFS_AUTO_GENERATE", "false").lower() == "true":
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            auto_generate_briefs,
            "interval",
            minutes=BRIEF_SCAN_INTERVAL_MINUTES,
            next_run_time=datetime.now(timezone.utc),  # also run once at startup
        )
        scheduler.start()
        print(
            f"[briefs-scheduler] auto-generation on — scanning every "
            f"{BRIEF_SCAN_INTERVAL_MINUTES} minutes"
        )
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Campo API", version="1.0.0", lifespan=lifespan)

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
    id: int | None = None
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
    played: int | None = None
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

    # The tools use blocking `requests` under the hood — run them in worker
    # threads so a slow upstream call can't stall the event loop.
    # Upcoming fixtures.
    try:
        upcoming_text = await asyncio.to_thread(get_wc_matches.invoke, {"status": "SCHEDULED"})
    except Exception as e:
        errors["upcoming_matches"] = str(e)

    # Recent / completed results.
    try:
        recent_text = await asyncio.to_thread(get_wc_matches.invoke, {"status": "FINISHED"})
    except Exception as e:
        errors["recent_matches"] = str(e)

    # Group standings.
    try:
        standings_text = await asyncio.to_thread(get_wc_standings.invoke, {})
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
        # Blocking `requests` call — keep it off the event loop.
        response["standings_text"] = await asyncio.to_thread(get_wc_standings.invoke, {})
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
    from tools.football_data import (
        get_wc_today_matches_data,
        get_wc_recent_results_data,
        get_wc_standings_data,
    )

    # The data functions use blocking `requests` — run them in worker threads,
    # in parallel, so slow upstream calls neither stall the event loop nor
    # stack up sequentially.
    results = await asyncio.gather(
        asyncio.to_thread(get_wc_today_matches_data),
        asyncio.to_thread(get_wc_recent_results_data),
        asyncio.to_thread(get_wc_standings_data),
        return_exceptions=True,
    )

    errors: dict[str, str] = {}
    fetched_ats: list[str] = []

    def unpack(result, key: str) -> list[dict]:
        if isinstance(result, BaseException):
            errors[key] = str(result)
            return []
        data, fetched_at = result
        fetched_ats.append(fetched_at)
        return data

    upcoming = unpack(results[0], "today_matches")
    recent = unpack(results[1], "recent_matches")
    groups = unpack(results[2], "standings")

    # as_of reflects when the data was actually fetched upstream (responses
    # may be served from cache); report the oldest dataset's stamp.
    as_of = min(fetched_ats) if fetched_ats else datetime.now(timezone.utc).isoformat()

    return TodayDataResponse(
        matches=upcoming,
        recent_matches=recent,
        standings=groups,
        as_of=as_of,
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
        # Blocking `requests` call — keep it off the event loop.
        groups, fetched_at = await asyncio.to_thread(get_wc_standings_data)
        return StandingsDataResponse(
            standings=groups,
            as_of=fetched_at,
        )
    except Exception as e:
        return StandingsDataResponse(
            standings=[],
            as_of=datetime.now(timezone.utc).isoformat(),
            error=str(e),
        )


# ── Pre-match briefs ──────────────────────────────────────────────────────────
# The verified-brief pipeline (briefs/) is Campo's real multi-agent system:
# deterministic planner -> 4 parallel research workers -> writer -> verifier.
# These endpoints only read the store and kick background generation — the
# request path never blocks on the ~1-minute pipeline.

@app.get("/briefs/today")
async def briefs_today():
    """Today's matches annotated with each one's brief status — lets the Today
    screen render brief affordances without N per-match requests."""
    from tools.football_data import get_wc_today_matches_data
    from briefs.store import get_brief, is_generating

    matches, fetched_at = await asyncio.to_thread(get_wc_today_matches_data)

    annotated = []
    for m in matches:
        match_id = m.get("id")
        brief_status = "none"
        if match_id is not None:
            record = await get_brief(match_id)
            if record:
                brief_status = record.get("status", "none")
            elif await is_generating(match_id):
                brief_status = "generating"
        annotated.append({**m, "brief_status": brief_status})

    return {"matches": annotated, "as_of": fetched_at}


@app.get("/briefs/{match_id}")
async def get_match_brief(match_id: int):
    """Fetch a brief. `status` is one of ready | failed | generating | none."""
    from briefs.store import get_brief, is_generating

    record = await get_brief(match_id)
    if record:
        return record
    if await is_generating(match_id):
        return {"match_id": match_id, "status": "generating"}
    return {"match_id": match_id, "status": "none"}


@app.post("/briefs/{match_id}/generate", status_code=202)
async def trigger_brief_generation(match_id: int, force: bool = False):
    """Kick off background generation for a match (idempotent).

    Returns the existing brief if one is ready and `force` is not set;
    otherwise 202 + generating. Generation runs as a fire-and-forget task —
    progress is observed by polling GET /briefs/{match_id}.
    """
    from briefs.store import get_brief, try_acquire_generation_lock
    from briefs.pipeline import generate_and_store

    record = await get_brief(match_id)
    if record and record.get("status") == "ready" and not force:
        return record

    if not await try_acquire_generation_lock(match_id):
        return {"match_id": match_id, "status": "generating"}

    task = asyncio.create_task(generate_and_store(match_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"match_id": match_id, "status": "generating"}


# Keep strong references to fire-and-forget tasks — asyncio only holds weak
# ones, so an unreferenced task can be garbage-collected mid-run.
_background_tasks: set = set()


@app.get("/health")
async def health():
    return {"status": "ok"}