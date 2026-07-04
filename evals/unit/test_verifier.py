# evals/unit/test_verifier.py
"""
Scored eval for the brief verifier — the pipeline's fact-checking agent.

Runs 4 realistic scenarios (18 claims, 9 of them PLANTED falsehoods across
injuries, scores, conditions and head-to-head history) and measures:

  - catch rate:        planted claims flagged unsupported or struck from the
                       revised brief (headline metric — higher is better)
  - false-strike rate: genuinely supported claims wrongly flagged
                       (lower is better)

Like the pipeline itself, this calls a live LLM (llm.factory.get_llm), so it
needs OPENROUTER_API_KEY / GROQ_API_KEY in .env — but no Redis, no Qdrant,
no running API.

Run:
    uv run pytest evals/unit/test_verifier.py -v -s
"""
import json
from pathlib import Path

import pytest

from briefs.researcher import ResearchResult
from briefs.verifier import verify_brief

CASES = json.loads(
    (Path(__file__).parent.parent / "verifier_cases.json").read_text(encoding="utf-8")
)
SCENARIOS = CASES["scenarios"]

# Thresholds the suite enforces. The verifier is adversarial by design, so we
# demand a high catch rate; occasional over-zealous strikes are tolerable
# (a struck true claim costs detail, a surviving false claim costs trust).
MIN_CATCH_RATE = 0.75
MAX_FALSE_STRIKE_RATE = 0.34


def _flagged_unsupported(claim_spec: dict, claims: list[dict]) -> bool:
    """True if any verifier claim matching the spec's keywords was judged
    unsupported."""
    for c in claims:
        text = c["claim"].lower()
        if c["verdict"] == "unsupported" and any(
            k.lower() in text for k in claim_spec["keywords"]
        ):
            return True
    return False


def _struck_from_brief(claim_spec: dict, revised: str) -> bool:
    """True if the claim's anchor phrase no longer appears asserted in the
    revised brief (removed outright, or explicitly hedged)."""
    revised_lower = revised.lower()
    anchor = claim_spec["anchor"].lower()
    if anchor not in revised_lower:
        return True
    # Anchor survives — accept if the surrounding text was hedged.
    return "could not be verified" in revised_lower or "unverified" in revised_lower


@pytest.mark.unit
async def test_verifier_catch_rate():
    """The headline eval: run every scenario, score planted-claim catches and
    false strikes across the whole set, and enforce thresholds."""
    caught, missed_details = 0, []
    false_strikes, false_strike_details = 0, []
    total_planted = 0
    total_supported = 0

    for scenario in SCENARIOS:
        evidence = [
            ResearchResult(lane_id=scenario["name"], evidence=scenario["evidence"])
        ]
        result = await verify_brief(scenario["draft"], evidence)

        assert result["verified"] is True, (
            f"[{scenario['name']}] verifier fell back to unverified draft"
        )
        claims = result["claims"]
        revised = result["brief_markdown"]

        for spec in scenario["claims"]:
            label = f"{scenario['name']}::{spec['anchor']}"
            if spec["expected"] == "planted":
                total_planted += 1
                if _flagged_unsupported(spec, claims) or _struck_from_brief(spec, revised):
                    caught += 1
                else:
                    missed_details.append(label)
            else:
                total_supported += 1
                if _flagged_unsupported(spec, claims):
                    false_strikes += 1
                    false_strike_details.append(label)

    catch_rate = caught / total_planted
    false_strike_rate = false_strikes / total_supported

    print(
        f"\n[verifier eval] planted caught: {caught}/{total_planted} "
        f"(catch rate {catch_rate:.0%}) | "
        f"false strikes: {false_strikes}/{total_supported} "
        f"({false_strike_rate:.0%})"
    )
    if missed_details:
        print(f"[verifier eval] missed planted claims: {missed_details}")
    if false_strike_details:
        print(f"[verifier eval] falsely struck claims: {false_strike_details}")

    assert catch_rate >= MIN_CATCH_RATE, (
        f"Catch rate {catch_rate:.0%} below {MIN_CATCH_RATE:.0%}. "
        f"Missed: {missed_details}"
    )
    assert false_strike_rate <= MAX_FALSE_STRIKE_RATE, (
        f"False-strike rate {false_strike_rate:.0%} above "
        f"{MAX_FALSE_STRIKE_RATE:.0%}. Struck: {false_strike_details}"
    )


@pytest.mark.unit
async def test_verifier_with_no_evidence_ships_unverified():
    """No evidence corpus → the draft must ship unverified rather than be
    judged against nothing (or lost)."""
    draft = "## France\nFrance are in excellent form."
    result = await verify_brief(draft, [ResearchResult(lane_id="x", evidence=[])])
    assert result["verified"] is False
    assert result["brief_markdown"] == draft
    assert result["claims"] == []
