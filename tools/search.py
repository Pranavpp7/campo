import asyncio
from langchain_core.tools import tool
from tools.mcp_client import get_search_tools

# ── Singleton: the underlying Tavily search MCP tool ──────────────────────────
_tavily_search_tool = None
_lock = asyncio.Lock()

async def _get_tavily_search():
    """Fetch and cache the raw tavily_search MCP tool (once)."""
    global _tavily_search_tool
    async with _lock:
        if _tavily_search_tool is None:
            mcp_tools = await get_search_tools()
            for t in mcp_tools:
                if t.name == "tavily_search":
                    _tavily_search_tool = t
                    break
            if _tavily_search_tool is None:
                raise RuntimeError("tavily_search tool not found among MCP tools")
    return _tavily_search_tool

# ── Clean wrapper tool exposed to agents ──────────────────────────────────────
@tool
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for current information — news, injuries, form, analyst takes, etc.

    Args:
        query: The search query (e.g. "Morocco World Cup 2026 injury news").
        max_results: How many results to return (default 5).

    Returns:
        Search result snippets with source URLs.
    """
    search = await _get_tavily_search()
    # Only valid Tavily params are passed — anything the model might hallucinate
    # never reaches the underlying tool.
    result = await search.ainvoke({
        "query": query,
        "max_results": max_results,
    })
    return str(result)

    