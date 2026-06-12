import os
import json
from datetime import datetime

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
    decode_responses=True,  # so we get str back, not bytes
)

# ── Short Term Memory (Redis-backed) ─────────────────────────────────────────

def _session_key(session_id: str) -> str:
    return f"session:{session_id}"

async def get_session(session_id: str) -> dict:
    """Get a session dict, or a fresh default if it doesn't exist yet.
    Note: a fresh default is NOT written to Redis here — it's only
    persisted once something calls add_turn/set_context.
    """
    raw = await redis_client.get(_session_key(session_id))
    if raw is None:
        return {
            "history": [],
            "context": {},
            "created_at": datetime.utcnow().isoformat(),
        }
    return json.loads(raw)

async def _save_session(session_id: str, session: dict):
    """Write the session back, refreshing its TTL (sliding expiration)."""
    await redis_client.set(
        _session_key(session_id),
        json.dumps(session),
        ex=SESSION_TTL_SECONDS,
    )

async def add_turn(session_id: str, role: str, content: str):
    """Add a conversation turn. Trims to MAX_HISTORY_TURNS."""
    session = await get_session(session_id)
    session["history"].append({
        "role": role,
        "content": content,
        "ts": datetime.utcnow().isoformat(),
    })
    if len(session["history"]) > MAX_HISTORY_TURNS:
        session["history"] = session["history"][-MAX_HISTORY_TURNS:]
    await _save_session(session_id, session)

async def get_history(session_id: str) -> list[dict]:
    """Get history as {role, content} list — passed directly to LLM."""
    session = await get_session(session_id)
    return [
        {"role": t["role"], "content": t["content"]}
        for t in session["history"]
    ]

async def set_context(session_id: str, key: str, value):
    """Store cross-agent context.
    Example: Scout fetches France form → MatchInsight reads it without re-fetching.
    """
    session = await get_session(session_id)
    session["context"][key] = value
    await _save_session(session_id, session)

async def get_context(session_id: str, key: str):
    """Read cross-agent context. Returns None if not set."""
    session = await get_session(session_id)
    return session["context"].get(key)

async def clear_session(session_id: str):
    """Clear a session entirely."""
    await redis_client.delete(_session_key(session_id))