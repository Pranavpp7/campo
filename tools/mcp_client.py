import os
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

MCP_SERVERS = {
    "tavily": {
        "url": "https://mcp.tavily.com/mcp/",
        "transport": "streamable_http",
        "headers": {
            "Authorization": f"Bearer {TAVILY_API_KEY}"
        },
    },
}

async def get_search_tools() -> list:
    """Get Tavily web search tools via MCP."""
    client = MultiServerMCPClient({"tavily": MCP_SERVERS["tavily"]})
    tools = await client.get_tools()
    return tools

async def get_all_mcp_tools() -> list:
    """Get all MCP tools."""
    client = MultiServerMCPClient(MCP_SERVERS)
    tools = await client.get_tools()
    return tools