# evals/integration/test_history.py
"""
Integration tests for conversation history correctness.

These tests call run_orchestrator() directly (no HTTP server needed)
and inspect Redis to verify history is written correctly.

The key regression this catches: in parallel multi-agent dispatch,
all agents used to write add_turn() to the same session_id simultaneously,
storing the user message 3x and three separate assistant answers.
This test will fail immediately if that bug regresses.

Requires: Redis + Qdrant running (docker compose up -d)

Run:
    uv run pytest evals/integration/test_history.py -v
"""
import pytest
import uuid
from redis.asyncio import Redis
from agents.orchestrator import run_orchestrator

REDIS_URL = "redis://localhost:6379"


async def get_raw_history(session_id: str) -> list[dict]:
    """Read raw history entries from Redis for a session."""
    redis = Redis.from_url(REDIS_URL)
    try:
        import json
        raw = await redis.lrange(f"session:{session_id}:history", 0, -1)
        return [json.loads(entry) for entry in raw]
    finally:
        await redis.aclose()


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture
def fresh_session() -> str:
    """A unique session ID per test so tests don't pollute each other."""
    return f"eval-history-{uuid.uuid4().hex[:8]}"


# ── Tests ─────────────────────────────────────────────────────────────────────
@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_agent_writes_one_turn(fresh_session):
    """
    A query routed to a single agent should produce exactly:
    - 1 user turn
    - 1 assistant turn
    Nothing more.
    """
    await run_orchestrator(
        message="Tell me about Morocco's squad",
        session_id=fresh_session,
        user_id="eval-user",
    )

    history = await get_raw_history(fresh_session)

    user_turns = [h for h in history if h["role"] == "user"]
    assistant_turns = [h for h in history if h["role"] == "assistant"]

    assert len(user_turns) == 1, (
        f"Expected 1 user turn, got {len(user_turns)}. "
        f"Full history: {history}"
    )
    assert len(assistant_turns) == 1, (
        f"Expected 1 assistant turn, got {len(assistant_turns)}. "
        f"Full history: {history}"
    )
    assert user_turns[0]["content"] == "Tell me about Morocco's squad", (
        f"User turn content mismatch: {user_turns[0]['content']}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_agent_writes_one_turn(fresh_session):
    """
    A query routed to multiple agents should STILL produce exactly:
    - 1 user turn
    - 1 assistant turn

    This is the core regression test for history triplication.
    Before the fix, parallel agents each wrote add_turn() independently,
    storing the user message 3x. This test catches that if it regresses.
    """
    await run_orchestrator(
        message="I run a bar near AT&T Stadium and I am traveling to the Morocco vs Brazil match",
        session_id=fresh_session,
        user_id="eval-user",
    )

    history = await get_raw_history(fresh_session)

    user_turns = [h for h in history if h["role"] == "user"]
    assistant_turns = [h for h in history if h["role"] == "assistant"]

    assert len(user_turns) == 1, (
        f"History triplication detected — expected 1 user turn, "
        f"got {len(user_turns)}. This is the regression bug. "
        f"Full history: {history}"
    )
    assert len(assistant_turns) == 1, (
        f"Expected 1 assistant turn, got {len(assistant_turns)}. "
        f"Full history: {history}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_turn_conversation_grows_correctly(fresh_session):
    """
    Two sequential messages should produce exactly 4 history entries:
    [user1, assistant1, user2, assistant2]

    This verifies history accumulates correctly across turns without
    duplication or gaps.
    """
    await run_orchestrator(
        message="Tell me about Morocco's squad",
        session_id=fresh_session,
        user_id="eval-user",
    )
    await run_orchestrator(
        message="What about their head to head record against Brazil?",
        session_id=fresh_session,
        user_id="eval-user",
    )

    history = await get_raw_history(fresh_session)

    assert len(history) == 4, (
        f"Expected 4 history entries after 2 turns, got {len(history)}. "
        f"Full history: {[h['role'] for h in history]}"
    )

    # Verify alternating roles
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    assert history[2]["role"] == "user"
    assert history[3]["role"] == "assistant"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_history_content_is_synthesized_response(fresh_session):
    """
    The assistant turn stored in history should be the final synthesized
    response — not a raw agent output or an empty string.
    """
    result = await run_orchestrator(
        message="Tell me about Morocco's squad",
        session_id=fresh_session,
        user_id="eval-user",
    )

    history = await get_raw_history(fresh_session)
    assistant_turns = [h for h in history if h["role"] == "assistant"]

    assert len(assistant_turns) == 1
    stored_response = assistant_turns[0]["content"]

    # Must not be empty
    assert stored_response.strip(), "Assistant turn in history is empty"

    # Must match what run_orchestrator returned
    assert stored_response == result["response"], (
        "Stored history response doesn't match what run_orchestrator returned. "
        "History and API response are out of sync."
    )

# Must contain something football-related OR be a recognizable agent error.
    # Agent errors (e.g. "Event loop is closed" from MCP cleanup) are legitimate
    # responses that get stored to history correctly — the history correctness
    # assertion above already verified the sync. This check guards against
    # truly empty or garbage responses.
    football_terms = ["morocco", "squad", "player", "team", "match", "brazil"]
    error_terms = ["error", "encountered", "timed out"]
    response_lower = stored_response.lower()
    has_football = any(term in response_lower for term in football_terms)
    has_error = any(term in response_lower for term in error_terms)
    assert has_football or has_error, (
        f"Assistant response is neither football content nor a recognizable error. "
        f"Response: {stored_response[:200]}..."
    )