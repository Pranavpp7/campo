import asyncio
from langgraph.prebuilt import create_react_agent
from llm.factory import get_llm
from tools.football_data import get_wc_matches
from tools.weather import get_venue_weather
from tools.logistics import calculate_venue_distance
from tools.mcp_client import get_search_tools
from prompts.logistics import LOGISTICS_PROMPT
from memory.session_store import get_history, add_turn, set_context, get_context
from memory.memory_manager import build_context_message, extract_and_save

BASE_TOOLS = [
    get_wc_matches,
    get_venue_weather,
    calculate_venue_distance,
]

async def _build_agent():
    llm = get_llm()
    mcp_tools = await get_search_tools()
    all_tools = BASE_TOOLS + mcp_tools
    return create_react_agent(
        model=llm,
        tools=all_tools,
        prompt=LOGISTICS_PROMPT,
    )

_agent = None
_agent_lock = asyncio.Lock()

async def _get_agent():
    global _agent
    async with _agent_lock:
        if _agent is None:
            _agent = await _build_agent()
    return _agent

async def run_logistics(task: str, session_id: str, user_id: str = "default") -> dict:
    """Run the Logistics agent on a task.

    Args:
        task: The natural language task from the orchestrator
        session_id: Session ID for short-term memory (conversation history)
        user_id: User ID for long-term memory (preferences across sessions)
    """
    try:
        agent = await _get_agent()

        history = await get_history(session_id)
        messages = history + [{"role": "user", "content": task}]

        history = await get_history(session_id)
        messages = history + [{"role": "user", "content": task}]

        # Inject Scout's findings from this session, if available
        scout_context = await get_context(session_id, "scout_result")
        if scout_context:
            scout_message = (
                "Relevant context from Scout (match intelligence) earlier in "
                "this session:\n\n"
                f"{scout_context}\n\n"
                "Use this information where relevant (e.g. injury news or "
                "match details that affect your planning/recommendations). "
                "Don't repeat it verbatim — incorporate it naturally."
            )
            messages = [{"role": "system", "content": scout_message}] + messages

        # Inject long-term memory context if relevant
        memory_context = await build_context_message(user_id, task)
        if memory_context:
            messages = [{"role": "system", "content": memory_context}] + messages
        memory_context = await build_context_message(user_id, task)
        if memory_context:
            messages = [{"role": "system", "content": memory_context}] + messages

        result = await agent.ainvoke({"messages": messages})

        final_message = result["messages"][-1]
        response_text = final_message.content

        await add_turn(session_id, "user", task)
        await add_turn(session_id, "assistant", response_text)
        await set_context(session_id, "logistics_result", response_text)

        await extract_and_save(user_id, task)

        return {
            "result": response_text,
            "sources": ["football-data.org", "open-meteo", "tavily"],
            "confidence": "high",
            "error": None,
            "fallbacks_used": [],
        }

    except Exception as e:
        return {
            "result": f"Logistics agent encountered an error: {str(e)}",
            "sources": [],
            "confidence": "low",
            "error": str(e),
            "fallbacks_used": [],
        }