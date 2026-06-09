import os
import uuid
from datetime import datetime

from dotenv import load_dotenv
from langchain_qdrant import QdrantVectorStore as Qdrant
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

load_dotenv()

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_HISTORY_TURNS = 20
LONG_TERM_COLLECTION = "user_profiles"

# ── Embeddings ────────────────────────────────────────────────────────────────
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# ── Qdrant client (shared) ────────────────────────────────────────────────────
qdrant_client = QdrantClient(
    host=os.getenv("QDRANT_HOST", "localhost"),
    port=int(os.getenv("QDRANT_PORT", 6333)),
)

# ── Short Term Memory (Pure Python) ──────────────────────────────────────────
_sessions: dict = {}

def get_session(session_id: str) -> dict:
    """Get or create a session."""
    if session_id not in _sessions:
        _sessions[session_id] = {
            "history": [],
            "context": {},
            "created_at": datetime.utcnow().isoformat(),
        }
    return _sessions[session_id]

def add_turn(session_id: str, role: str, content: str):
    """Add a conversation turn. Trims to MAX_HISTORY_TURNS."""
    session = get_session(session_id)
    session["history"].append({
        "role": role,
        "content": content,
        "ts": datetime.utcnow().isoformat(),
    })
    if len(session["history"]) > MAX_HISTORY_TURNS:
        session["history"] = session["history"][-MAX_HISTORY_TURNS:]

def get_history(session_id: str) -> list[dict]:
    """Get history as {role, content} list — passed directly to LLM."""
    session = get_session(session_id)
    return [
        {"role": t["role"], "content": t["content"]}
        for t in session["history"]
    ]

def set_context(session_id: str, key: str, value):
    """Store cross-agent context.
    Example: Scout fetches France form → BettingEdge reads it without re-fetching.
    """
    get_session(session_id)["context"][key] = value

def get_context(session_id: str, key: str):
    """Read cross-agent context. Returns None if not set."""
    return get_session(session_id)["context"].get(key)

def clear_session(session_id: str):
    """Clear a session entirely."""
    if session_id in _sessions:
        del _sessions[session_id]

async def cleanup_old_sessions(max_age_hours: int = 2):
    """Delete sessions inactive for more than max_age_hours.
    Scheduled to run every 30 minutes via apscheduler in main.py.
    """
    now = datetime.utcnow()
    to_delete = []
    for session_id, session in _sessions.items():
        created = datetime.fromisoformat(session["created_at"])
        age_hours = (now - created).seconds / 3600
        if age_hours > max_age_hours:
            to_delete.append(session_id)
    for session_id in to_delete:
        del _sessions[session_id]

# ── Long Term Memory (LangChain + Qdrant) ─────────────────────────────────────
class LongTermMemory:
    def __init__(self):
        self._store = None  # lazy — don't connect until first use

    def _get_store(self):
        """Connect to Qdrant on first use, not at import time."""
        if self._store is None:
            self._ensure_collection()
            self._store = Qdrant(
                client=qdrant_client,
                collection_name=LONG_TERM_COLLECTION,
                embeddings=embeddings,
            )
        return self._store

    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        existing = [
            c.name for c in qdrant_client.get_collections().collections
        ]
        if LONG_TERM_COLLECTION not in existing:
            qdrant_client.create_collection(
                collection_name=LONG_TERM_COLLECTION,
                vectors_config=VectorParams(
                    size=384,
                    distance=Distance.COSINE,
                ),
            )

    def save_preference(self, user_id: str, preference: str):
        """Save a user preference. Connects to Qdrant on first call."""
        doc = Document(
            page_content=preference,
            metadata={
                "user_id": user_id,
                "saved_at": datetime.utcnow().isoformat(),
                "id": str(uuid.uuid4()),
            },
        )
        self._get_store().add_documents([doc])

    def get_preferences(self, user_id: str, query: str) -> list[str]:
        """Retrieve relevant preferences using semantic search."""
        results = self._get_store().similarity_search(
            query=query,
            k=5,
            filter={"user_id": user_id},
        )
        return [doc.page_content for doc in results]

# Singleton — one instance shared across the app
long_term_memory = LongTermMemory()