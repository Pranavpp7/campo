import os
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from llm.factory import get_llm
from memory.session_store import long_term_memory

load_dotenv()

# ── Personal signal keywords ──────────────────────────────────────────────────
# If a message contains any of these, we check for extractable preferences.
# This avoids unnecessary LLM calls on messages like "Is Mbappe fit?"
PERSONAL_SIGNALS = [
    "i ", "i'm", "i am", "i run", "i work", "i own", "i live",
    "my ", "my name", "my business", "my team", "my city",
    "we ", "we run", "we own", "we are",
    "i support", "i bet", "i travel", "i'm flying", "i'm going",
    "i care about", "i'm interested", "i follow",
]

EXTRACTION_PROMPT = """You are a memory extraction assistant. 
Your job is to identify facts about the user that would help personalize future responses.

Extract ONLY concrete, reusable facts about the user. Examples of what to extract:
- "User runs a food truck near the Houston World Cup venue"
- "User supports the France national team"
- "User is flying from Dallas to attend USA games"
- "User prefers value bets on underdogs"
- "User is a sports journalist covering the World Cup"

Do NOT extract:
- Questions the user asked
- General football opinions
- One-time queries
- Anything not about the user personally

User message: {message}

Respond with a JSON array of strings. Each string is one extractable fact.
If nothing is worth saving, respond with an empty array: []
Respond with JSON only, no other text.
"""

# ── Extraction ─────────────────────────────────────────────────────────────────

def _has_personal_signal(message: str) -> bool:
    """Quick keyword check before calling the LLM.
    Returns True if the message likely contains personal information.
    """
    message_lower = message.lower()
    return any(signal in message_lower for signal in PERSONAL_SIGNALS)

async def extract_and_save(user_id: str, message: str):
    """Extract preferences from a user message and save to long term memory.
    
    Only calls the LLM if the message contains personal signals.
    This keeps token usage minimal — most messages skip the LLM entirely.
    
    Args:
        user_id: Unique user identifier
        message: The user's message to check for extractable preferences
    """
    # Step 1 — quick keyword check, no LLM needed
    if not _has_personal_signal(message):
        return

    # Step 2 — call LLM to extract structured preferences
    try:
        llm = get_llm()
        prompt = EXTRACTION_PROMPT.format(message=message)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content.strip()

        # Parse JSON response
        import json
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        
        preferences = json.loads(raw.strip())

        # Step 3 — save each extracted preference to Qdrant
        for preference in preferences:
            if isinstance(preference, str) and len(preference) > 10:
                long_term_memory.save_preference(user_id, preference)

    except Exception as e:
        # Memory extraction failing should never crash the main flow
        print(f"Memory extraction error (non-fatal): {e}")

# ── Loading ────────────────────────────────────────────────────────────────────

def load_memories(user_id: str, query: str) -> str:
    try:
        preferences = long_term_memory.get_preferences(user_id, query)
        if not preferences:
            return ""
        
        # Dedupe while preserving order
        seen = set()
        unique_prefs = []
        for pref in preferences:
            if pref not in seen:
                seen.add(pref)
                unique_prefs.append(pref)
        
        lines = ["User context from previous conversations:"]
        for pref in unique_prefs:
            lines.append(f"- {pref}")
        
        return "\n".join(lines)
    except Exception as e:
        print(f"Memory loading error (non-fatal): {e}")
        return ""

# ── Injection ──────────────────────────────────────────────────────────────────

def build_context_message(user_id: str, query: str) -> str | None:
    """Build a context message to inject into agent conversations.
    
    Loads relevant memories and formats them as a system message
    the agent sees before the user's actual question.
    
    Returns None if no relevant memories exist.
    """
    memories = load_memories(user_id, query)
    if not memories:
        return None
    
    return f"""
{memories}

Use this context to personalize your response where relevant.
Do not explicitly mention that you remember this — just use it naturally.
"""