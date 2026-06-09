import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

load_dotenv()

# ── Model config ──────────────────────────────────────────────────────────────
MODEL_NAME = "openai/gpt-oss-120b"
TEMPERATURE = 0  # 0 = deterministic, better for reasoning agents

# ── Primary LLM (Groq) ────────────────────────────────────────────────────────
def _make_groq() -> ChatGroq:
    return ChatGroq(
        model=MODEL_NAME,
        temperature=TEMPERATURE,
        api_key=os.getenv("GROQ_API_KEY"),
    )

# ── Fallback LLM (OpenRouter) ─────────────────────────────────────────────────
# OpenRouter uses the OpenAI-compatible API — same interface, different base URL
def _make_openrouter() -> ChatOpenAI:
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

# ── LLM Factory ───────────────────────────────────────────────────────────────
def get_llm():
    """Returns a LangChain LLM with Groq as primary and OpenRouter as fallback.
    
    Uses LangChain's built-in with_fallbacks() — if Groq returns a rate limit
    error (429), LangChain automatically retries with OpenRouter. The calling
    agent never needs to know which one is being used.
    """
    primary = _make_groq()
    fallback = _make_openrouter()
    return primary.with_fallbacks([fallback])