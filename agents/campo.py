import asyncio
from langgraph.prebuilt import create_react_agent

from llm.factory import get_llm
from tools.football_data import get_wc_matches, get_team_squad, get_wc_standings
from tools.espn import get_live_scores, get_match_summary, get_team_news
from tools.weather import get_venue_weather
from tools.logistics import calculate_venue_distance
from tools.search import web_search
from tools.briefs import get_match_brief
from prompts.campo import CAMPO_PROMPT
from tools.competitions import ACTIVE
from memory.session_store import get_history

# One agent, all tools. Chat questions don't decompose the way brief
# generation does — routing them across topic agents added latency and a
# synthesis step without adding capability. The multi-agent machinery lives
# in briefs/, where it structurally earns its keep; chat stays simple and is
# grounded in the pipeline's output via get_match_brief.
ALL_TOOLS = [
    get_match_brief,
    get_wc_matches,
    get_team_squad,
    get_wc_standings,
    get_live_scores,
    get_match_summary,
    get_team_news,
    get_venue_weather,
    calculate_venue_distance,
    web_search,
]

_agent = None
_agent_lock = asyncio.Lock()


async def _get_agent():
    global _agent
    async with _agent_lock:
        if _agent is None:
            _agent = create_react_agent(
                model=get_llm(),
                tools=ALL_TOOLS,
                prompt=CAMPO_PROMPT.format(competition=ACTIVE.label),
            )
    return _agent


async def run_campo(
    message: str,
    session_id: str,
    memory_context: str | None = None,
) -> str:
    """Answer one chat message with full conversation history.

    Raises on failure — the orchestrator owns error shaping.
    """
    agent = await _get_agent()

    history = await get_history(session_id)
    messages = history + [{"role": "user", "content": message}]
    if memory_context:
        messages = [{"role": "system", "content": memory_context}] + messages

    result = await agent.ainvoke(
        {"messages": messages},
        config={"run_name": "campo-chat"},
    )
    return result["messages"][-1].content


def _chunk_text(content) -> str:
    """Normalize a message chunk's content to plain text. Providers emit
    either a string or a list of typed parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    return ""


async def stream_campo(
    message: str,
    session_id: str,
    memory_context: str | None = None,
):
    """Yield the agent's answer as text chunks (tool churn stays silent).

    Raises on failure — the orchestrator owns error shaping.
    """
    agent = await _get_agent()

    history = await get_history(session_id)
    messages = history + [{"role": "user", "content": message}]
    if memory_context:
        messages = [{"role": "system", "content": memory_context}] + messages

    async for chunk, metadata in agent.astream(
        {"messages": messages},
        stream_mode="messages",
        config={"run_name": "campo-chat"},
    ):
        # Only the model's own tokens — skip ToolMessages and any non-agent
        # graph nodes so the user never sees raw tool output mid-answer.
        if metadata.get("langgraph_node") != "agent":
            continue
        text = _chunk_text(getattr(chunk, "content", None))
        if text:
            yield text
