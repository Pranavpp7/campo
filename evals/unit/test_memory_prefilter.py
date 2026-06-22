# evals/unit/test_memory_prefilter.py
"""
Unit tests for the memory pre-filter.

_has_personal_signal() is a pure synchronous keyword-matching function —
no LLM calls, no external services, no async. These tests run in
milliseconds and should always pass regardless of service state.

Run:
    uv run pytest evals/unit/test_memory_prefilter.py -v
"""
import pytest
from memory.memory_manager import _has_personal_signal

# ── Should trigger (personal signal present) ──────────────────────────────────
SHOULD_TRIGGER = [
    # "i " prefix
    ("I run a bar near AT&T Stadium", True),
    ("I am flying into Dallas for the match", True),
    ("I own a sports bar near the stadium", True),
    ("I work in hospitality near MetLife", True),
    ("I live in Dallas and follow Brazil", True),
    ("I support Morocco", True),
    ("I travel to matches every year", True),
    ("I'm going to the match next week", True),
    ("I'm flying from New York to Dallas", True),
    ("I'm interested in the Group C standings", True),
    ("I follow Real Madrid closely", True),
    ("I care about the result", True),
    ("I'm a huge Brazil fan", True),
    # "my " prefix
    ("My team is Brazil", True),
    ("My business is near the stadium", True),
    ("My name is Pranav", True),
    ("My city is Dallas", True),
    # "we " prefix
    ("We run a restaurant near the venue", True),
    ("We own three locations in Arlington", True),
    ("We are planning to attend the match", True),
    # Mixed case — function should lowercase before checking
    ("I AM FLYING TO DALLAS", True),
    ("MY TEAM IS BRAZIL", True),
    ("We Run A Bar Near The Stadium", True),
]

# ── Should NOT trigger (no personal signal) ────────────────────────────────────
SHOULD_NOT_TRIGGER = [
    # Pure match intelligence
    ("Tell me about Morocco vs Brazil", False),
    ("Who are the top scorers in Group C?", False),
    ("What is Brazil's tactical setup?", False),
    ("Is Vinicius Junior fit for the match?", False),
    ("When does Morocco play next?", False),
    # Pure logistics (no personal framing)
    ("What is the weather forecast for AT&T Stadium?", False),
    ("How far is Dallas from MetLife Stadium?", False),
    ("What are the best hotels near the venue?", False),
    # Pure business intel (no personal framing)
    ("What is the expected crowd size?", False),
    ("What permits are needed for extended bar hours?", False),
    ("What are the local regulations for outdoor seating?", False),
    # Short/ambiguous
    ("Morocco", False),
    ("Group D standings", False),
    ("", False),
    ("   ", False),
]


@pytest.mark.unit
@pytest.mark.parametrize("message,expected", SHOULD_TRIGGER)
def test_prefilter_triggers(message, expected):
    """Messages containing personal signals should return True."""
    result = _has_personal_signal(message)
    assert result == expected, (
        f"Expected _has_personal_signal({message!r}) = {expected}, got {result}"
    )


@pytest.mark.unit
@pytest.mark.parametrize("message,expected", SHOULD_NOT_TRIGGER)
def test_prefilter_does_not_trigger(message, expected):
    """Messages without personal signals should return False."""
    result = _has_personal_signal(message)
    assert result == expected, (
        f"Expected _has_personal_signal({message!r}) = {expected}, got {result}"
    )


@pytest.mark.unit
def test_prefilter_is_case_insensitive():
    """The check must work regardless of message casing."""
    assert _has_personal_signal("I RUN A BAR") is True
    assert _has_personal_signal("i run a bar") is True
    assert _has_personal_signal("I Run A Bar") is True


@pytest.mark.unit
def test_prefilter_returns_bool():
    """Return type must be bool, not a truthy/falsy value."""
    result_true = _has_personal_signal("I run a bar")
    result_false = _has_personal_signal("Morocco vs Brazil")
    assert isinstance(result_true, bool), f"Expected bool, got {type(result_true)}"
    assert isinstance(result_false, bool), f"Expected bool, got {type(result_false)}"


@pytest.mark.unit
def test_prefilter_skip_rate():
    """
    Validate that the pre-filter correctly skips LLM extraction for the
    majority of typical World Cup queries (no personal context).
    The skip rate on non-personal queries should be 100% — every
    impersonal query avoids the mem0 LLM call.
    """
    non_personal = [msg for msg, _ in SHOULD_NOT_TRIGGER]
    skipped = [m for m in non_personal if not _has_personal_signal(m)]
    skip_rate = len(skipped) / len(non_personal)
    assert skip_rate == 1.0, (
        f"Pre-filter skip rate on non-personal queries: {skip_rate:.0%} "
        f"(expected 100%). Missed: {[m for m in non_personal if _has_personal_signal(m)]}"
    )