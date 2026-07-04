import os
import time
import asyncio
from datetime import datetime, timezone

from tools.competitions import date_context
from tools.football_data import get_match_data
from briefs.planner import plan_research
from briefs.researcher import run_research, ResearchResult
from briefs.writer import write_brief
from briefs.verifier import verify_brief
from briefs.store import save_brief, release_generation_lock

# Orchestrated as a plain async function rather than a LangGraph StateGraph:
# the pipeline is linear with one fan-out (plan -> gather(workers) -> write ->
# verify), so a graph would be ceremony without control-flow value.

LANE_TIMEOUT_SECONDS = 120
# One brief runs 4 ReAct workers; on free-tier LLM quotas 4-way parallelism
# reliably trips 429s on BOTH providers at once (observed in testing), so the
# default is 2. Raise it if you have paid-tier keys.
WORKER_CONCURRENCY = int(os.getenv("BRIEF_WORKER_CONCURRENCY", "2"))
# When a lane fails on provider rate limits, wait this long and retry it once —
# upstream free-tier 429s are typically per-minute windows, so wait a full one.
RATE_LIMIT_RETRY_DELAY_SECONDS = 60

def _is_rate_limited(error: str | None) -> bool:
    if not error:
        return False
    lowered = error.lower()
    return "429" in lowered or "rate" in lowered


async def generate_brief(match_id: int) -> dict:
    """Run the full pipeline for one match and return the brief record.

    Raises only if the match itself can't be fetched — individual lane
    failures degrade to an honest gap in the brief instead.
    """
    start = time.time()

    # Blocking `requests` call — keep it off the event loop.
    match, _ = await asyncio.to_thread(get_match_data, match_id)

    tasks = plan_research(match)
    date_ctx = date_context()
    semaphore = asyncio.Semaphore(WORKER_CONCURRENCY)

    async def run_lane(task):
        async with semaphore:
            try:
                return await asyncio.wait_for(
                    run_research(task, date_ctx),
                    timeout=LANE_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                # run_research handles its own exceptions; only the timeout
                # escapes to here.
                return ResearchResult(
                    lane_id=task.lane_id,
                    error=f"timed out after {LANE_TIMEOUT_SECONDS}s",
                )

    results = list(await asyncio.gather(*[run_lane(t) for t in tasks]))

    # One retry pass for rate-limited lanes: free-tier 429s are per-minute
    # windows, so a single cooldown usually recovers the whole brief.
    retry_indexes = [
        i for i, r in enumerate(results) if _is_rate_limited(r.error)
    ]
    if retry_indexes:
        print(
            f"[brief {match_id}] {len(retry_indexes)} lane(s) rate-limited — "
            f"retrying after {RATE_LIMIT_RETRY_DELAY_SECONDS}s"
        )
        await asyncio.sleep(RATE_LIMIT_RETRY_DELAY_SECONDS)
        retried = await asyncio.gather(*[run_lane(tasks[i]) for i in retry_indexes])
        for i, r in zip(retry_indexes, retried):
            results[i] = r

    for r in results:
        if r.error:
            print(f"[brief {match_id}] lane {r.lane_id} failed: {r.error[:300]}")

    research_seconds = round(time.time() - start, 1)

    write_start = time.time()
    draft = await write_brief(match, results)
    write_seconds = round(time.time() - write_start, 1)

    verify_start = time.time()
    verification = await verify_brief(draft, results)
    verify_seconds = round(time.time() - verify_start, 1)

    return {
        "match_id": match_id,
        "home": (match.get("home") or {}).get("name"),
        "away": (match.get("away") or {}).get("name"),
        "kickoff_utc": match.get("utc_date"),
        "stage": match.get("stage") or match.get("group"),
        "venue": match.get("venue"),
        "status": "ready",
        "brief_markdown": verification["brief_markdown"],
        "claims": verification["claims"],
        "verified": verification["verified"],
        "lanes_failed": [r.lane_id for r in results if r.error],
        # Full error strings stay server-side friendly but debuggable.
        "lane_errors": {r.lane_id: r.error for r in results if r.error},
        # Observability: where the time went and how hard each lane worked.
        "lane_metrics": {
            r.lane_id: {
                "duration_seconds": r.duration_seconds,
                "tool_calls": r.tool_calls,
                "evidence_items": len(r.evidence),
            }
            for r in results
        },
        "stage_seconds": {
            "research": research_seconds,
            "write": write_seconds,
            "verify": verify_seconds,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_seconds": round(time.time() - start, 1),
    }


async def generate_and_store(match_id: int):
    """Background entry point — caller must already hold the generation lock.

    Persists a `ready` record on success or a `failed` record on error, and
    always releases the lock so the match never wedges.
    """
    try:
        record = await generate_brief(match_id)
        await save_brief(match_id, record)
    except Exception as e:
        print(f"Brief generation failed for match {match_id}: {e}")
        try:
            await save_brief(match_id, {
                "match_id": match_id,
                "status": "failed",
                "error": str(e),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as save_err:
            print(f"Could not persist failed-brief record for {match_id}: {save_err}")
    finally:
        try:
            await release_generation_lock(match_id)
        except Exception as lock_err:
            # The lock self-expires, so this only delays retries briefly.
            print(f"Could not release generation lock for {match_id}: {lock_err}")
