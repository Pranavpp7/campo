# Campo Today/Standings Endpoints — Report

## Step 1 — Tool function return shapes

All relevant functions return **formatted strings**, and all are LangChain `@tool`
objects (must be called via `.invoke(...)`):

- `get_wc_matches(status="SCHEDULED")` → **string** (`"2026-06-14 19:00 UTC | Mexico 2 - 1 Poland"`, max 20 lines)
- `get_wc_standings()` → **string** (ASCII table per group: `Pos/Team/Pts/W/D/L/GD`)
- `get_live_scores()` (espn.py) → **string** (`"Match [Status]: Home 1 - 0 Away"`)
- `get_team_squad`, `get_match_summary`, `get_team_news` → also strings (not needed here)

**Flag:** None return structured dict/list — so the endpoints use the documented
`*_text` fallback shape.

## Step 2 — Diff for api/main.py

```diff
@@ imports
 from dotenv import load_dotenv
+from datetime import datetime, timezone
 import time

@@ routes (added before /health)
+@app.get("/today")
+async def today():
+    """Deterministic data endpoint ... NO LLM, NO agent, NO orchestrator."""
+    from tools.football_data import get_wc_matches, get_wc_standings   # lazy
+    errors = {}
+    upcoming_text = recent_text = standings_text = None
+    try:    upcoming_text  = get_wc_matches.invoke({"status": "SCHEDULED"})
+    except Exception as e:  errors["upcoming_matches"] = str(e)
+    try:    recent_text    = get_wc_matches.invoke({"status": "FINISHED"})
+    except Exception as e:  errors["recent_matches"]   = str(e)
+    try:    standings_text = get_wc_standings.invoke({})
+    except Exception as e:  errors["standings"]        = str(e)
+    response = {
+        "matches_text": upcoming_text,
+        "recent_matches_text": recent_text,
+        "standings_text": standings_text,
+        "as_of": datetime.now(timezone.utc).isoformat(),
+    }
+    if errors: response["errors"] = errors
+    return response
+
+@app.get("/standings")
+async def standings():
+    """Deterministic data endpoint ... NO LLM, NO agent, NO orchestrator."""
+    from tools.football_data import get_wc_standings   # lazy
+    response = {"standings_text": None, "as_of": datetime.now(timezone.utc).isoformat()}
+    try:    response["standings_text"] = get_wc_standings.invoke({})
+    except Exception as e:  response["error"] = str(e)
+    return response
```

(Abbreviated for readability — the real code keeps full docstrings, comments,
and one-`try`-per-call structure.)

Decisions worth flagging:

- **`.invoke(...)` not direct call** — these are `@tool` objects; `get_wc_matches("SCHEDULED")`
  would fail, `.invoke({"status": ...})` is correct.
- **Two `get_wc_matches` calls** (`SCHEDULED` + `FINISHED`) since one call only returns a
  single status — gives upcoming AND recent. Hence `matches_text` (upcoming) +
  `recent_matches_text` (recent).
- **Per-call try/except** → partial success: `/today` returns whatever worked and lists
  failures under `errors`.
- Both endpoints `async`, both have no-LLM docstrings, imports lazy inside functions.

## Step 3 — Compile

`python -m py_compile api/main.py` → **OK, compiles cleanly.**
Did not run uvicorn or hit the endpoints, per instructions.

---

## Step 4 — Structured `*_data` endpoints (implemented)

The string endpoints above can only be dropped into a `<pre>` block — a fan UI
**cannot** build match cards, sortable standings tables, team crests, or
click-a-match interactions from them. The structured `*_data` endpoints below
fix that: they return real JSON arrays the frontend can bind to.

### Tool data functions — `tools/football_data.py`

Two plain functions (intentionally **NOT** `@tool` decorated — they're for REST
endpoints, not agents). Both reuse the existing `_api_get` + TTL cache, and let
exceptions propagate so the endpoint owns error handling. Cache lookups use
`is not None` so an empty list isn't mistaken for a cache miss.

- `get_wc_matches_data(status="SCHEDULED") -> list[dict]` — no 20-match cap
  (the cap exists only to protect LLM token budgets). Cache key
  `wc_matches_data_{status}`, TTL `TTL_MATCHES`.
- `get_wc_standings_data() -> list[dict]` — cache key `wc_standings_data`,
  TTL `TTL_STANDINGS`.

### Pydantic model trees — `api/main.py`

```python
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
    matches: list[MatchOut]          # upcoming (SCHEDULED)
    recent_matches: list[MatchOut]   # completed (FINISHED)
    standings: list[StandingsGroupOut]
    as_of: str
    errors: dict[str, str] | None = None

class StandingsDataResponse(BaseModel):
    standings: list[StandingsGroupOut]
    as_of: str
    error: str | None = None
```

### Routes — `api/main.py` (added before `/health`)

```python
@app.get("/today-data", response_model=TodayDataResponse)
async def today_data():
    """Structured (typed) Today screen data. NO LLM, NO agent, NO orchestrator."""
    from tools.football_data import get_wc_matches_data, get_wc_standings_data   # lazy
    errors = {}
    upcoming = recent = groups = []
    try:    upcoming = get_wc_matches_data("SCHEDULED")
    except Exception as e:  errors["upcoming_matches"] = str(e)
    try:    recent   = get_wc_matches_data("FINISHED")
    except Exception as e:  errors["recent_matches"]   = str(e)
    try:    groups   = get_wc_standings_data()
    except Exception as e:  errors["standings"]        = str(e)
    return TodayDataResponse(
        matches=upcoming, recent_matches=recent, standings=groups,
        as_of=datetime.now(timezone.utc).isoformat(), errors=errors or None,
    )

@app.get("/standings-data", response_model=StandingsDataResponse)
async def standings_data():
    """Structured (typed) standings. NO LLM, NO agent, NO orchestrator."""
    from tools.football_data import get_wc_standings_data   # lazy
    try:
        return StandingsDataResponse(
            standings=get_wc_standings_data(),
            as_of=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        return StandingsDataResponse(
            standings=[], as_of=datetime.now(timezone.utc).isoformat(), error=str(e),
        )
```

(Abbreviated — real code keeps full docstrings and one-`try`-per-call structure.)

`python -m py_compile api/main.py tools/football_data.py` → **both compile cleanly.**

### Two notes worth knowing

1. **`group` / `venue` can be `null` on lower plan tiers.** These fields come
   straight from football-data.org; on the WC competition they may be absent
   depending on plan tier and stage. The models allow `None`, so responses stay
   valid either way — the frontend should treat both as optional.
2. **Separate cache keys → separate API calls (rate-limit tradeoff).** The
   string tools (`wc_matches_*`, `wc_standings`) and the data tools
   (`wc_matches_data_*`, `wc_standings_data`) use distinct cache keys, so there's
   no collision — but hitting both a string endpoint and a data endpoint makes
   two separate upstream calls, each counting against the football-data.org rate
   limit. If that becomes a problem, refactor the string tools to format the
   `*_data` output so a single fetch backs both.

### Still optional / future

- **Fold in `get_live_scores()` structured data** (ESPN gives event IDs + live
  clock/status) for a live score ticker.
