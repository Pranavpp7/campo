# evals/e2e/test_brief_quality.py
"""
End-to-end eval for the pre-match brief pipeline.

Generates (or reuses) a real brief through the API for a match on today's
slate, then validates:
  1. Structural: the fixed section skeleton and claims list are present
  2. Safety: no betting/gambling language
  3. Quality: DeepEval GEval scores the brief with Groq gpt-oss-120b as judge

Requires the full stack:
  - docker compose up -d       (Redis at minimum)
  - uv run uvicorn api.main:app --reload

Run:
    uv run pytest evals/e2e/test_brief_quality.py -v -s
"""
import asyncio
import pytest
import httpx
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

from evals.e2e.test_chat_endpoint import _judge, assert_no_betting

API_BASE = "http://localhost:8000"
QUALITY_THRESHOLD = 0.6
GENERATION_TIMEOUT_SECONDS = 360
POLL_INTERVAL_SECONDS = 10

REQUIRED_SECTIONS = ["## The Stakes", "## The Matchup", "## Conditions", "## The One-Liner"]


def brief_quality_metric() -> GEval:
    return GEval(
        name="Campo Brief Quality",
        criteria=(
            "Evaluate whether this is a useful pre-match football brief for a fan. "
            "It should read as match-specific intelligence: concrete facts about the "
            "two teams, the matchup, and the conditions — names, results, figures — "
            "not generic filler that could describe any match. Honest statements "
            "that a specific piece of information was unavailable are acceptable "
            "and should not be penalized, but a brief where most sections carry "
            "no real information is a failure."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        threshold=QUALITY_THRESHOLD,
        model=_judge,
    )


async def _pick_briefable_match(client: httpx.AsyncClient) -> dict:
    resp = await client.get("/briefs/today")
    assert resp.status_code == 200, f"/briefs/today returned {resp.status_code}"
    matches = resp.json()["matches"]
    candidates = [
        m for m in matches if m.get("id") is not None and m.get("status") != "FINISHED"
    ]
    if not candidates:
        pytest.skip("No briefable (non-finished) match on today's slate.")
    return candidates[0]


async def _get_or_generate_brief(client: httpx.AsyncClient, match_id: int) -> dict:
    resp = await client.get(f"/briefs/{match_id}")
    brief = resp.json()
    if brief.get("status") == "ready":
        return brief

    resp = await client.post(f"/briefs/{match_id}/generate")
    assert resp.status_code in (200, 202)

    deadline = asyncio.get_event_loop().time() + GENERATION_TIMEOUT_SECONDS
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        resp = await client.get(f"/briefs/{match_id}")
        brief = resp.json()
        if brief.get("status") in ("ready", "failed"):
            return brief
    pytest.fail(f"Brief {match_id} did not reach a terminal state in {GENERATION_TIMEOUT_SECONDS}s")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_brief_generation_quality(require_api):
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        match = await _pick_briefable_match(client)
        match_id = match["id"]
        home = (match.get("home") or {}).get("name", "?")
        away = (match.get("away") or {}).get("name", "?")

        brief = await _get_or_generate_brief(client, match_id)

        # 1. Structural
        assert brief["status"] == "ready", f"Brief failed: {brief.get('error')}"
        markdown = brief.get("brief_markdown", "")
        for section in REQUIRED_SECTIONS:
            assert section in markdown, f"Missing section {section!r} in brief"
        assert isinstance(brief.get("claims"), list)
        # The pipeline is only doing its job if at least some lanes produced
        # research — an all-lanes-failed brief is honest but not a pass.
        assert len(brief.get("lanes_failed", [])) < 4, (
            f"All research lanes failed: {brief.get('lane_errors')}"
        )

        # 2. Safety
        assert_no_betting(markdown)

        # 3. GEval quality
        test_case = LLMTestCase(
            input=f"Pre-match brief for {home} vs {away} (World Cup 2026).",
            actual_output=markdown,
        )
        metric = brief_quality_metric()
        metric.measure(test_case)
        print(
            f"\n[Brief {home} vs {away}] GEval: {metric.score:.2f} | "
            f"verified: {brief.get('verified')} | claims: {len(brief['claims'])} | "
            f"lanes_failed: {brief.get('lanes_failed')} | Reason: {metric.reason}"
        )
        assert metric.score >= QUALITY_THRESHOLD, (
            f"Brief quality {metric.score:.2f} < {QUALITY_THRESHOLD}. Reason: {metric.reason}"
        )
