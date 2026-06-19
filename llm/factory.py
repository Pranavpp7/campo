import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

load_dotenv()

# ── Model config ──────────────────────────────────────────────────────────────
MODEL_NAME = "openai/gpt-oss-120b"
CLASSIFIER_MODEL_NAME = "llama-3.1-8b-instant"
TEMPERATURE = 0

# ── Provider factories ────────────────────────────────────────────────────────
def _make_openrouter() -> ChatOpenAI:
    """OpenRouter — primary for high-TPM calls (agent loops, synthesis).
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

def _make_groq_primary() -> ChatGroq:
    """Groq gpt-oss-120b — fallback for agent/synthesis calls.
    Free tier is 8k TPM, which a single Scout request (~9.3k tokens)
    already exceeds — kept only as a safety net if OpenRouter is down.
    """
    return ChatGroq(
        model=MODEL_NAME,
        temperature=TEMPERATURE,
        api_key=os.getenv("GROQ_API_KEY"),
    )

# ── LLM Factory ───────────────────────────────────────────────────────────────
def get_llm():
    """Heavy LLM — for agent ReAct loops and multi-agent synthesis.

    Routes to OpenRouter (no per-minute TPM ceiling) with Groq as fallback.
    A single Scout agent request is ~9,336 tokens, which already exceeds
    Groq's free-tier 8,000 TPM limit — so OpenRouter must be primary here.
    """
    primary = _make_openrouter()
    fallback = _make_groq_primary()
    return primary.with_fallbacks([fallback])

def get_classifier_llm() -> ChatGroq:
    """Lightweight LLM — for intent classification only.

    Short prompts (~200 tokens), well within Groq's free-tier limits.
    Uses llama-3.1-8b-instant: fast, cheap, no fallback needed since
    classify_intent() already defaults to ['scout'] on any failure.
    """
    return ChatGroq(
        model=CLASSIFIER_MODEL_NAME,
        temperature=0,
        api_key=os.getenv("GROQ_API_KEY"),
    )