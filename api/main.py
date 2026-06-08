from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import time

load_dotenv()

app = FastAPI(title="Campo API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Schemas ---
class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    response: str
    agents_used: list[str]
    trace_url: str | None
    latency_ms: int

# --- Routes ---
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    start = time.time()

    # Placeholder — orchestrator goes here in Phase 2
    response_text = f"Echo: {request.message}"
    agents_used = []

    latency = int((time.time() - start) * 1000)

    return ChatResponse(
        response=response_text,
        agents_used=agents_used,
        trace_url=None,
        latency_ms=latency,
    )

@app.get("/health")
async def health():
    return {"status": "ok"}