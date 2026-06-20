import asyncio
from langgraph.prebuilt import create_react_agent
from llm.factory import get_llm
from tools.football_data import get_wc_matches
from tools.weather import get_venue_weather
from tools.logistics import calculate_venue_distance
from tools.search import web_search
from prompts.logistics import LOGISTICS_PROMPT
from memory.session_store import get_history, set_context

BASE_TOOLS = [
    get_wc_matches,
    get_venue_weather,
    calculate_venue_distance,
]

async def _build_agent():
    llm = get_llm()
    all_tools = BASE_TOOLS + [web_search]
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

async def run_logistics(
    task: str,
    session_id: str,
    user_id: str = "default",
    memory_context: str | None = None,
) -> dict:
    """Run the Logistics agent on a task.

    Args:
        task: The natural language task from the orchestrator
        session_id: Session ID for short-term memory (conversation history)
        user_id: User ID for long-term memory (preferences across sessions)
        memory_context: Long-term memory context, loaded once by the orchestrator
    """
    try:
        agent = await _get_agent()

        history = await get_history(session_id)
        messages = history + [{"role": "user", "content": task}]

        # Inject long-term memory context if the orchestrator provided it
        if memory_context:
            messages = [{"role": "system", "content": memory_context}] + messages

        result = await agent.ainvoke({"messages": messages})

        final_message = result["messages"][-1]
        response_text = final_message.content

        # History is persisted once by the orchestrator (run_orchestrator);
        # agents only publish cross-agent context here.
        await set_context(session_id, "logistics_result", response_text)

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