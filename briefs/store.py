import json

# Reuse the shared async Redis client — same instance the session store uses.
from memory.session_store import redis_client

BRIEF_TTL_SECONDS = 24 * 3600  # a brief is stale once the match is well past
GENERATION_LOCK_TTL_SECONDS = 300  # generous upper bound on one generation run


def _brief_key(match_id: int) -> str:
    return f"brief:{match_id}"


def _lock_key(match_id: int) -> str:
    return f"brief:{match_id}:lock"


async def get_brief(match_id: int) -> dict | None:
    raw = await redis_client.get(_brief_key(match_id))
    return json.loads(raw) if raw else None


async def save_brief(match_id: int, record: dict):
    await redis_client.set(
        _brief_key(match_id), json.dumps(record), ex=BRIEF_TTL_SECONDS
    )


async def try_acquire_generation_lock(match_id: int) -> bool:
    """True if this caller should generate; False if a run is already active.
    The lock self-expires so a crashed generation never wedges a match."""
    return bool(
        await redis_client.set(
            _lock_key(match_id), "1", nx=True, ex=GENERATION_LOCK_TTL_SECONDS
        )
    )


async def release_generation_lock(match_id: int):
    await redis_client.delete(_lock_key(match_id))


async def is_generating(match_id: int) -> bool:
    return bool(await redis_client.exists(_lock_key(match_id)))
