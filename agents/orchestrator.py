import asyncio

from agents.campo import run_campo, stream_campo
from memory.session_store import add_turn
from tools.competitions import date_context

# Chat is a single all-tools agent (see agents/campo.py for why). This module
# keeps the /chat contract and owns the per-request plumbing the old
# orchestrator hoisted out of the agents: one memory load, one memory
# extraction, one history write per exchange.

AGENT_TIMEOUT_SECONDS = 120


async def run_orchestrator(
    message: str,
    session_id: str,
    user_id: str = "default",
) -> dict:
    """Entry point for /chat."""
    try:
        # Lazy import — keeps mem0/HuggingFace/Qdrant from initializing at
        # module load time, which caused a 102-second hang when tests imported
        # this module.
        from memory.memory_manager import build_context_message, extract_and_save

        memory_context = await build_context_message(user_id, message)
        memory_context = (
            f"{date_context()}\n\n{memory_context}" if memory_context else date_context()
        )

        response_text = await asyncio.wait_for(
            run_campo(message, session_id, memory_context),
            timeout=AGENT_TIMEOUT_SECONDS,
        )

        # Long-term memory extraction is pre-filtered on personal signals and
        # non-fatal on failure (see memory_manager).
        await extract_and_save(user_id, message)

        if response_text:
            try:
                await add_turn(session_id, "user", message)
                await add_turn(session_id, "assistant", response_text)
            except Exception as e:
                print(f"History persistence failed (non-fatal): {e}")

        return {
            "response": response_text,
            "agents_used": ["campo"],
            "error": None,
        }

    except asyncio.TimeoutError:
        return {
            "response": f"Campo timed out after {AGENT_TIMEOUT_SECONDS}s — try again in a moment.",
            "agents_used": [],
            "error": "timeout",
        }
    except Exception as e:
        return {
            "response": f"Campo encountered an unexpected error: {str(e)}",
            "agents_used": [],
            "error": str(e),
        }


async def stream_orchestrator(
    message: str,
    session_id: str,
    user_id: str = "default",
):
    """Streaming twin of run_orchestrator — yields answer chunks as the agent
    writes them, then does the same per-request bookkeeping (memory
    extraction, one history write per exchange) once the answer is complete.

    Raises on failure — the endpoint turns that into an SSE error event.
    """
    from memory.memory_manager import build_context_message, extract_and_save

    memory_context = await build_context_message(user_id, message)
    memory_context = (
        f"{date_context()}\n\n{memory_context}" if memory_context else date_context()
    )

    parts: list[str] = []
    async for token in stream_campo(message, session_id, memory_context):
        parts.append(token)
        yield token

    response_text = "".join(parts)

    await extract_and_save(user_id, message)

    if response_text:
        try:
            await add_turn(session_id, "user", message)
            await add_turn(session_id, "assistant", response_text)
        except Exception as e:
            print(f"History persistence failed (non-fatal): {e}")
