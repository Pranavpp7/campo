import os
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# ── MCP Server Configuration ──────────────────────────────────────────────────
MCP_SERVERS = {
    "tavily": {
        "url": "https://mcp.tavily.com/mcp/",
        "transport": "streamable_http",
        "headers": {
            "Authorization": f"Bearer {TAVILY_API_KEY}"
        },
    },
    "open-meteo": {
        "url": "https://mcp.open-meteo.com/",
        "transport": "streamable_http",
    },
}

# ── Tool getters ──────────────────────────────────────────────────────────────

async def get_search_tools() -> list:
    """Get Tavily web search tools via MCP."""
    client = MultiServerMCPClient({"tavily": MCP_SERVERS["tavily"]})
    tools = await client.get_tools()
    return tools

async def get_weather_tools() -> list:
    """Get Open-Meteo weather tools via MCP."""
    client = MultiServerMCPClient({"open-meteo": MCP_SERVERS["open-meteo"]})
    tools = await client.get_tools()
    return tools

async def get_all_mcp_tools() -> list:
    """Get all MCP tools from all servers."""
    client = MultiServerMCPClient(MCP_SERVERS)
    tools = await client.get_tools()
    return tools