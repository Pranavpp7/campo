# evals/unit/test_verifier.py
"""
Eval for the brief verifier — the pipeline's fact-checking agent.

Feeds the verifier a draft brief containing PLANTED FALSE CLAIMS alongside
supported ones, against a fixed synthetic evidence corpus, and asserts the
false claims are flagged and struck while the supported ones survive.

Like the classifier evals, this calls a live LLM (via llm.factory.get_llm),
so it needs OPENROUTER_API_KEY / GROQ_API_KEY in .env — but no Redis, no
Qdrant, no running API.

Run:
    uv run pytest evals/unit/test_verifier.py -v
"""
import pytest
from briefs.researcher import ResearchResult
from briefs.verifier import verify_brief

# ── Synthetic evidence corpus ──────────────────────────────────────────────────
# What the research workers' tools "actually returned".
EVIDENCE = [
    ResearchResult(
        lane_id="away_team",
        findings="",
        evidence=[
            "France recent results: beat Senegal 2-0 (28 Jun), beat Brazil 3-1 "
            "(1 Jul), beat Germany 1-0 (24 Jun). (football-data.org)",
            "ESPN news, 1 Jul: Ousmane Dembele ruled out of the remainder of the "
            "tournament with a hamstring injury sustained in training.",
            "Squad: France (Coach: Zinedine Zidane) — Goalkeeper: Mike Maignan; "
            "Offence: Kylian Mbappe, Marcus Thuram. (football-data.org)",
        ],
    ),
    ResearchResult(
        lane_id="conditions",
        findings="",
        evidence=[
            "Weather for AT&T Stadium (Arlington) on 2026-07-04:\n"
            "Condition: Clear sky\nTemperature: 75°F - 95°F\n"
            "Precipitation chance: 5%",
        ],
    ),
]

# ── Draft with planted false claims ────────────────────────────────────────────
# Supported by evidence: Dembele injury, 3-1 win over Brazil, hot clear weather.
# PLANTED (nowhere in evidence, or contradicting it):
#   1. "Mbappe is suspended for this match"       — invented suspension
#   2. "cool evening around 60°F"                 — contradicts 75-95°F evidence
DRAFT = """## France
France arrive in form, having beaten Brazil 3-1 on 1 July. Ousmane Dembele has
been ruled out of the tournament with a hamstring injury (ESPN). Kylian Mbappe
is suspended for this match after accumulating yellow cards.

## Conditions
Fans can expect a cool evening around 60°F with clear skies at AT&T Stadium.
"""


@pytest.mark.unit
async def test_verifier_strikes_planted_claims_and_keeps_supported():
    result = await verify_brief(DRAFT, EVIDENCE)

    # The verifier must have completed a real verification pass.
    assert result["verified"] is True, "verifier fell back to unverified draft"
    claims = result["claims"]
    assert claims, "verifier returned no claims"

    supported = [c["claim"].lower() for c in claims if c["verdict"] == "supported"]
    unsupported = [c["claim"].lower() for c in claims if c["verdict"] == "unsupported"]

    # Planted claim 1: the invented Mbappe suspension is caught.
    assert any(
        "suspend" in c for c in unsupported
    ), f"invented suspension not flagged. Unsupported: {unsupported}"

    # Planted claim 2: the contradicted temperature is caught.
    assert any(
        "60" in c or "cool" in c for c in unsupported
    ), f"contradicted weather not flagged. Unsupported: {unsupported}"

    # A genuinely supported claim survives with the right verdict.
    assert any(
        "dembele" in c for c in supported
    ), f"supported injury claim not confirmed. Supported: {supported}"

    # And the revised brief no longer asserts the false suspension.
    revised = result["brief_markdown"].lower()
    assert "is suspended" not in revised or "could not be verified" in revised, (
        "revised brief still asserts the invented suspension"
    )


@pytest.mark.unit
async def test_verifier_with_no_evidence_ships_unverified():
    """No evidence corpus → the draft must ship unverified rather than be
    judged against nothing (or lost)."""
    result = await verify_brief(DRAFT, [ResearchResult(lane_id="x", evidence=[])])
    assert result["verified"] is False
    assert result["brief_markdown"] == DRAFT
    assert result["claims"] == []
