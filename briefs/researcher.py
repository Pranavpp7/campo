import asyncio
from pydantic import BaseModel, Field
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import ToolMessage

from llm.factory import get_llm
from tools.football_data import get_wc_matches, get_team_squad, get_wc_standings
from tools.espn import get_live_scores, get_match_summary, get_team_news
from tools.weather import get_venue_weather
from tools.search import web_search
from prompts.briefs import RESEARCHER_PROMPT

# One generic worker, parameterized by its ResearchTask. The pipeline gets its
# multi-agent leverage from running four of these in parallel with isolated
# message contexts — not from giving each lane a different personality.
RESEARCH_TOOLS = [
    get_wc_matches,
    get_team_squad,
    get_wc_standings,
    get_live_scores,
    get_match_summary,
    get_team_news,
    get_venue_weather,
    web_search,
]

# Cap how much of any single tool output we keep as verifier evidence — a fat
# web_search result shouldn't blow the verifier's context.
MAX_EVIDENCE_ITEM_CHARS = 4000


class ResearchResult(BaseModel):
    lane_id: str
    findings: str = Field(default="", description="Worker's bullet-point findings")
    evidence: list[str] = Field(
        default_factory=list,
        description="Raw tool outputs — the corpus the verifier checks claims against",
    )
    error: str | None = None


_agent = None
_agent_lock = asyncio.Lock()


async def _get_agent():
    global _agent
    async with _agent_lock:
        if _agent is None:
            _agent = create_react_agent(
                model=get_llm(),
                tools=RESEARCH_TOOLS,
                prompt=RESEARCHER_PROMPT,
            )
    return _agent


async def run_research(task, date_context: str) -> ResearchResult:
    """Run one research lane. Never raises — a failed lane returns an error
    result so the brief can still ship with that section marked unavailable.
    """
    try:
        agent = await _get_agent()
        messages = [
            {"role": "system", "content": date_context},
            {"role": "user", "content": task.instructions},
        ]
        result = await agent.ainvoke({"messages": messages})

        findings = result["messages"][-1].content

        # Evidence = what the tools actually returned, straight from the
        # transcript. The verifier checks the brief against this, not against
        # whatever the model *says* its sources were.
        evidence = [
            str(m.content)[:MAX_EVIDENCE_ITEM_CHARS]
            for m in result["messages"]
            if isinstance(m, ToolMessage) and m.content
        ]

        return ResearchResult(
            lane_id=task.lane_id,
            findings=findings,
            evidence=evidence,
        )

    except Exception as e:
        return ResearchResult(lane_id=task.lane_id, error=str(e))
