import asyncio
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from llm.factory import get_llm
from tools.football_data import get_wc_matches, get_team_squad, get_wc_standings
from prompts.scout import SCOUT_PROMPT
from memory.session_store import get_history, add_turn, set_context

# ── Tools Scout can use ───────────────────────────────────────────────────────
SCOUT_TOOLS = [
    get_wc_matches,
    get_team_squad,
    get_wc_standings,
]

# ── Agent ─────────────────────────────────────────────────────────────────────
def _build_agent():
    """Build the Scout ReAct agent.
    Called once at module load — agent is reused across requests.
    """
    llm = get_llm()
    return create_react_agent(
        model=llm,
        tools=SCOUT_TOOLS,
        prompt=SCOUT_PROMPT,
    )

# Module-level agent instance — built once, reused
_agent = _build_agent()

# ── Run function ──────────────────────────────────────────────────────────────
async def run_scout(task: str, session_id: str) -> dict:
    """Run the Scout agent on a task.

    Args:
        task: The natural language task from the orchestrator
        session_id: Session ID for memory lookup

    Returns:
        dict with result, sources, and confidence
    """
    try:
        # Build messages — system prompt + conversation history + current task
        history = get_history(session_id)
        messages = history + [{"role": "user", "content": task}]

        # Run the ReAct agent
        result = await asyncio.to_thread(
            _agent.invoke,
            {"messages": messages},
        )

        # Extract the final response
        final_message = result["messages"][-1]
        response_text = final_message.content

        # Save to session memory
        add_turn(session_id, "user", task)
        add_turn(session_id, "assistant", response_text)

        # Store any team data in cross-agent context
        # so BettingEdge can reuse it without re-fetching
        set_context(session_id, "scout_result", response_text)

        return {
            "result": response_text,
            "sources": ["football-data.org", "web_search"],
            "confidence": "high",
            "error": None,
            "fallbacks_used": [],
        }

    except Exception as e:
        return {
            "result": f"Scout agent encountered an error: {str(e)}",
            "sources": [],
            "confidence": "low",
            "error": str(e),
            "fallbacks_used": [],
        }