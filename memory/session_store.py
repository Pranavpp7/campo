import os
import json
from datetime import datetime, timezone

from dotenv import load_dotenv
import redis.asyncio as redis

load_dotenv()

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_HISTORY_TURNS = 20
SESSION_TTL_SECONDS = 7200  # 2 hours, sliding — refreshed on every write

# ── Redis client (shared, async) ──────────────────────────────────────────────
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True,
)

# ── Short Term Memory (Redis-backed) ─────────────────────────────────────────
#
# Each session is split across two Redis keys rather than one JSON blob, so
# that concurrent agents writing to the same session_id (e.g. the orchestrator
# dispatching Scout and Logistics in parallel) don't clobber each other via a
# read-modify-write race:
#   - session:{id}:history -> Redis List (RPUSH per turn, atomic append)
#   - session:{id}:context -> Redis Hash (HSET per key, atomic per-field write)

def _history_key(session_id: str) -> str:
    return f"session:{session_id}:history"

def _context_key(session_id: str) -> str:
    return f"session:{session_id}:context"

async def add_turn(session_id: str, role: str, content: str):
    """Add a conversation turn. Trims to MAX_HISTORY_TURNS."""
    key = _history_key(session_id)
    turn = json.dumps({
        "role": role,
        "content": content,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    await redis_client.rpush(key, turn)
    await redis_client.ltrim(key, -MAX_HISTORY_TURNS, -1)
    await redis_client.expire(key, SESSION_TTL_SECONDS)

async def get_history(session_id: str) -> list[dict]:
    """Get history as {role, content} list — passed directly to LLM."""
    key = _history_key(session_id)
    raw_turns = await redis_client.lrange(key, 0, -1)
    history = []
    for raw in raw_turns:
        turn = json.loads(raw)
        history.append({"role": turn["role"], "content": turn["content"]})
    return history

async def set_context(session_id: str, key: str, value):
    """Store cross-agent context.
    Example: Scout fetches France form → Logistics or LocalPulse reads it
    without re-fetching.
    """
    redis_key = _context_key(session_id)
    await redis_client.hset(redis_key, key, json.dumps(value))
    await redis_client.expire(redis_key, SESSION_TTL_SECONDS)

async def get_context(session_id: str, key: str):
    """Read cross-agent context. Returns None if not set."""
    redis_key = _context_key(session_id)
    raw = await redis_client.hget(redis_key, key)
    return json.loads(raw) if raw is not None else None

async def clear_session(session_id: str):
    """Clear a session entirely (both history and context)."""
    await redis_client.delete(_history_key(session_id), _context_key(session_id))