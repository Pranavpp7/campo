import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

load_dotenv()

# ── Model config ──────────────────────────────────────────────────────────────
MODEL_NAME = "openai/gpt-oss-120b"
TEMPERATURE = 0

# ── Provider factories ────────────────────────────────────────────────────────
def _make_openrouter() -> ChatOpenAI:
    """OpenRouter — primary for high-TPM calls (agent loops, writer, verifier).
    No strict per-minute token ceiling on free tier, unlike Groq.
    """
    return ChatOpenAI(
        model=f"{MODEL_NAME}:free",
        temperature=TEMPERATURE,
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://github.com/Pranavpp7/campo",
            "X-Title": "Campo",
        },
    )

def _make_groq_fallback() -> ChatGroq:
    """Groq gpt-oss-120b — fallback when OpenRouter errors or rate-limits.
    Free tier is 8k TPM, which a tool-heavy agent request can already
    exceed — kept as a safety net, not a primary.
    """
    return ChatGroq(
        model=MODEL_NAME,
        temperature=TEMPERATURE,
        api_key=os.getenv("GROQ_API_KEY"),
    )

def _make_groq_llama() -> ChatGroq:
    """Groq llama-3.3-70b-versatile — last-resort fallback.
    Higher free-tier TPM (12k) than gpt-oss-120b, so it can absorb the
    tool-heavy research-worker calls that 429 on both chains above
    (observed: OpenRouter's :free pool saturated upstream while Groq's
    8k TPM rejected the researcher's tool-schema payloads).
    """
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=TEMPERATURE,
        api_key=os.getenv("GROQ_API_KEY"),
    )

# ── LLM Factory ───────────────────────────────────────────────────────────────
def get_llm():
    """The one production LLM chain: chat agent, brief research workers,
    brief writer, and brief verifier all use this.

    OpenRouter (no per-minute TPM ceiling) → Groq gpt-oss-120b → Groq
    llama-3.3-70b. Under parallel load the first two can 429 together —
    the brief pipeline additionally handles that with bounded worker
    concurrency and a lane retry pass (briefs/pipeline.py).
    """
    return _make_openrouter().with_fallbacks(
        [_make_groq_fallback(), _make_groq_llama()]
    )
