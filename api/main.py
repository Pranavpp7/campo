from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import time

from agents.orchestrator import run_orchestrator

load_dotenv()

app = FastAPI(title="Campo API", version="1.0.0")

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Schemas ───────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    session_id: str
    message: str
    user_id: str | None = None

class ChatResponse(BaseModel):
    response: str
    agents_used: list[str]
    trace_url: str | None
    latency_ms: int

# ── Routes ────────────────────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    start = time.time()

    user_id = request.user_id or request.session_id

    result = await run_orchestrator(
        message=request.message,
        session_id=request.session_id,
        user_id=user_id,
    )

    latency = int((time.time() - start) * 1000)

    return ChatResponse(
        response=result["response"],
        agents_used=result["agents_used"],
        trace_url=None,
        latency_ms=latency,
    )

@app.get("/health")
async def health():
    return {"status": "ok"}