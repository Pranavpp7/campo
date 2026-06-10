import asyncio
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from llm.factory import get_llm
from tools.football_data import get_wc_matches, get_team_squad, get_wc_standings
from tools.mcp_client import get_search_tools
from prompts.scout import SCOUT_PROMPT
from memory.session_store import get_history, add_turn, set_context
from tools.football_data import get_wc_matches, get_team_squad, get_wc_standings
from tools.espn import get_live_scores, get_match_summary, get_team_news

# ── Base tools (always available) ─────────────────────────────────────────────
BASE_TOOLS = [
    get_wc_matches,
    get_team_squad,
    get_wc_standings,
    get_live_scores,
    get_match_summary,
    get_team_news,
]

# ── Agent factory (async — loads MCP tools at startup) ────────────────────────
async def _build_agent():
    """Build Scout with both structured and MCP tools."""
    llm = get_llm()
    mcp_tools = await get_search_tools()
    all_tools = BASE_TOOLS + mcp_tools
    return create_react_agent(
        model=llm,
        tools=all_tools,
        prompt=SCOUT_PROMPT,
    )

# Module-level agent — built once on first use
_agent = None
_agent_lock = asyncio.Lock()

async def _get_agent():
    """Get or build the Scout agent (singleton)."""
    global _agent
    async with _agent_lock:
        if _agent is None:
            _agent = await _build_agent()
    return _agent

# ── Run function ──────────────────────────────────────────────────────────────
async def run_scout(task: str, session_id: str) -> dict:
    """Run the Scout agent on a task."""
    try:
        agent = await _get_agent()

        history = get_history(session_id)
        messages = history + [{"role": "user", "content": task}]

        result = await agent.ainvoke({"messages": messages})

        final_message = result["messages"][-1]
        response_text = final_message.content

        add_turn(session_id, "user", task)
        add_turn(session_id, "assistant", response_text)
        set_context(session_id, "scout_result", response_text)

        return {
            "result": response_text,
            "sources": ["football-data.org", "tavily"],
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