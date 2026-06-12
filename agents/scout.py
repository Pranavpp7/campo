import asyncio
from langgraph.prebuilt import create_react_agent
from llm.factory import get_llm
from tools.football_data import get_wc_matches, get_team_squad, get_wc_standings
from tools.espn import get_live_scores, get_match_summary, get_team_news
from tools.mcp_client import get_search_tools
from prompts.scout import SCOUT_PROMPT
from memory.session_store import get_history, add_turn, set_context
from memory.memory_manager import build_context_message, extract_and_save

BASE_TOOLS = [
    get_wc_matches,
    get_team_squad,
    get_wc_standings,
    get_live_scores,
    get_match_summary,
    get_team_news,
]

async def _build_agent():
    llm = get_llm()
    mcp_tools = await get_search_tools()
    all_tools = BASE_TOOLS + mcp_tools
    return create_react_agent(
        model=llm,
        tools=all_tools,
        prompt=SCOUT_PROMPT,
    )

_agent = None
_agent_lock = asyncio.Lock()

async def _get_agent():
    global _agent
    async with _agent_lock:
        if _agent is None:
            _agent = await _build_agent()
    return _agent

async def run_scout(task: str, session_id: str, user_id: str = "default") -> dict:
    """Run the Scout agent on a task.

    Args:
        task: The natural language task from the orchestrator
        session_id: Session ID for short-term memory (conversation history)
        user_id: User ID for long-term memory (preferences across sessions)
    """
    try:
        agent = await _get_agent()

        history = await get_history(session_id)
        messages = history + [{"role": "user", "content": task}]

        # Inject long-term memory context if relevant
        memory_context = await build_context_message(user_id, task)
        if memory_context:
            messages = [{"role": "system", "content": memory_context}] + messages

        result = await agent.ainvoke({"messages": messages})

        final_message = result["messages"][-1]
        response_text = final_message.content

        await add_turn(session_id, "user", task)
        await add_turn(session_id, "assistant", response_text)
        await set_context(session_id, "scout_result", response_text)

        # Extract any new long-term preferences from this turn
        await extract_and_save(user_id, task)

        return {
            "result": response_text,
            "sources": ["football-data.org", "espn", "tavily"],
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