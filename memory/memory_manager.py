import os
from dotenv import load_dotenv
from mem0 import AsyncMemory

load_dotenv()

# ── Personal signal keywords ──────────────────────────────────────────────────
# If a message contains any of these, we pass it to mem0 for extraction.
# This avoids unnecessary LLM calls on messages like "Is Mbappe fit?"
PERSONAL_SIGNALS = [
    "i ", "i'm", "i am", "i run", "i work", "i own", "i live",
    "my ", "my name", "my business", "my team", "my city",
    "we ", "we run", "we own", "we are",
    "i support", "i bet", "i travel", "i'm flying", "i'm going",
    "i care about", "i'm interested", "i follow",
]

# ── mem0 config ────────────────────────────────────────────────────────────────
MEM0_CONFIG = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "campo_memories",
            "embedding_model_dims": 384,
            "host": os.getenv("QDRANT_HOST", "localhost"),
            "port": int(os.getenv("QDRANT_PORT", 6333)),
        },
    },
    "embedder": {
        "provider": "huggingface",
        "config": {
            "model": "sentence-transformers/all-MiniLM-L6-v2",
        },
    },
    "llm": {
        "provider": "groq",
        "config": {
            "model": "llama-3.3-70b-versatile",
            "api_key": os.getenv("GROQ_API_KEY"),
            "temperature": 0.1,
        },
    },
    "history_db_path": os.path.join(os.path.dirname(__file__), "mem0_history.db"),
}

memory = AsyncMemory.from_config(MEM0_CONFIG)

# ── Extraction ─────────────────────────────────────────────────────────────────

def _has_personal_signal(message: str) -> bool:
    """Quick keyword check before calling mem0 (which itself calls an LLM).
    Returns True if the message likely contains personal information.
    """
    message_lower = message.lower()
    return any(signal in message_lower for signal in PERSONAL_SIGNALS)

async def extract_and_save(user_id: str, message: str):
    """Extract preferences from a user message and save via mem0.

    Only calls mem0 if the message contains personal signals.
    mem0 handles extraction, dedup, and conflict resolution internally
    (decides ADD/UPDATE/DELETE/NONE per fact via its own LLM call).

    Args:
        user_id: Unique user identifier
        message: The user's message to check for extractable preferences
    """
    if not _has_personal_signal(message):
        return

    try:
        await memory.add(message, user_id=user_id)
    except Exception as e:
        # Memory extraction failing should never crash the main flow
        print(f"Memory extraction error (non-fatal): {e}")

# ── Loading ────────────────────────────────────────────────────────────────────

async def load_memories(user_id: str, query: str) -> str:
    try:
        result = await memory.search(
            query=query,
            filters={"user_id": user_id},
            top_k=5,
        )
        results = result.get("results", [])
        if not results:
            return ""

        lines = ["User context from previous conversations:"]
        for r in results:
            lines.append(f"- {r['memory']}")

        return "\n".join(lines)
    except Exception as e:
        print(f"Memory loading error (non-fatal): {e}")
        return ""

# ── Injection ──────────────────────────────────────────────────────────────────

async def build_context_message(user_id: str, query: str) -> str | None:
    """Build a context message to inject into agent conversations.

    Loads relevant memories and formats them as a system message
    the agent sees before the user's actual question.

    Returns None if no relevant memories exist.
    """
    memories = await load_memories(user_id, query)
    if not memories:
        return None

    return f"""
{memories}

Use this context to personalize your response where relevant.
Do not explicitly mention that you remember this — just use it naturally.
"""