import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

load_dotenv()

# ── Model config ──────────────────────────────────────────────────────────────
MODEL_NAME = "openai/gpt-oss-120b"
TEMPERATURE = 0

# ── Primary LLM (Groq) ────────────────────────────────────────────────────────
def _make_groq() -> ChatGroq:
    return ChatGroq(
        model=MODEL_NAME,
        temperature=TEMPERATURE,
        api_key=os.getenv("GROQ_API_KEY"),
    )

# ── Fallback LLM (OpenRouter) ─────────────────────────────────────────────────
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
    """Returns a LangChain LLM with Groq as primary and OpenRouter as fallback."""
    primary = _make_groq()
    fallback = _make_openrouter()
    return primary.with_fallbacks([fallback])

# ── Classifier LLM (Groq, lightweight) ────────────────────────────────────────
CLASSIFIER_MODEL_NAME = "llama-3.1-8b-instant"

def get_classifier_llm() -> ChatGroq:
    """Returns a fast, cheap Groq model for lightweight tasks like intent
    classification.

    No fallback chain here — classify_intent() already has its own graceful
    default (["scout"]) if this call fails, so the added complexity of a
    fallback model isn't needed for a low-stakes, frequently-called task.
    """
    return ChatGroq(
        model=CLASSIFIER_MODEL_NAME,
        temperature=0,
        api_key=os.getenv("GROQ_API_KEY"),
    )