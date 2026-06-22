# evals/unit/test_classifier.py
"""
Unit tests for intent classification.

These tests call classify_intent() directly — no agents run, no tools
called, no Redis or Qdrant needed. The only external call is to the
Groq classifier LLM, so these tests require a valid GROQ_API_KEY in
.env but nothing else.

Run:
    uv run pytest evals/unit/test_classifier.py -v
"""
import json
import pytest
from pathlib import Path
from agents.orchestrator import classify_intent

# ── Load golden queries ────────────────────────────────────────────────────────
GOLDEN = json.loads(
    (Path(__file__).parent.parent / "golden_queries.json").read_text()
)
CLASSIFICATION_CASES = GOLDEN["classification"]

# ── Helpers ───────────────────────────────────────────────────────────────────
def _agents_match(actual: list[str], expected: list[str]) -> bool:
    """
    Check that actual agents fired match expected.
    Order doesn't matter; we check set equality.
    Extra agents (false positives) are also failures — the classifier
    should dispatch only what's needed, not fire agents defensively.
    """
    return set(actual) == set(expected)

def _failure_message(query: str, expected: list[str], actual: list[str]) -> str:
    return (
        f"\nQuery   : {query!r}"
        f"\nExpected: {sorted(expected)}"
        f"\nActual  : {sorted(actual)}"
    )

# ── Tests ─────────────────────────────────────────────────────────────────────
@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    CLASSIFICATION_CASES,
    ids=[c["id"] for c in CLASSIFICATION_CASES],
)
async def test_classification(case):
    """
    Each golden query should be routed to exactly the expected agent(s).
    Both false negatives (missing an agent) and false positives (extra
    agent dispatched) are treated as failures.
    """
    query = case["query"]
    expected = case["expected_agents"]

    actual = await classify_intent(query)

    assert _agents_match(actual, expected), _failure_message(
        query, expected, actual
    )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_classifier_defaults_to_scout_on_empty():
    """
    An empty or whitespace-only message should default to ['scout']
    rather than crashing or returning an empty list.
    """
    result = await classify_intent("")
    assert result == ["scout"]

@pytest.mark.unit
@pytest.mark.asyncio
async def test_classifier_defaults_to_scout_on_gibberish():
    """
    Completely unrecognizable input should default to ['scout'] —
    the safest fallback for an ambiguous World Cup query.
    """
    result = await classify_intent("asdfghjkl qwerty 12345")
    assert result in [["scout"], ["scout"]]  # always scout, any order

@pytest.mark.unit
@pytest.mark.asyncio
async def test_classifier_no_betting_agents():
    """
    No query should ever route to 'betting_edge' — that agent was
    dropped from the system. Verify it never appears in output
    regardless of how the query is phrased.
    """
    queries = [
        "what are the odds on Brazil winning?",
        "should I bet on Morocco?",
        "give me a value bet for Group C",
    ]
    for query in queries:
        result = await classify_intent(query)
        assert "betting_edge" not in result, (
            f"betting_edge appeared in result for query: {query!r}"
        )

@pytest.mark.unit
@pytest.mark.asyncio
async def test_classifier_returns_valid_agents_only():
    """
    The classifier should never return an agent name that doesn't exist
    in the system, regardless of input.
    """
    valid = {"scout", "logistics", "localpulse"}
    test_queries = [c["query"] for c in CLASSIFICATION_CASES]

    for query in test_queries:
        result = await classify_intent(query)
        invalid = set(result) - valid
        assert not invalid, (
            f"Unknown agents {invalid} returned for query: {query!r}"
        )