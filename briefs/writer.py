from langchain_core.messages import HumanMessage

from llm.factory import get_llm
from prompts.briefs import WRITER_PROMPT

LANE_LABELS = {
    "home_team": "Home team research",
    "away_team": "Away team research",
    "matchup": "Matchup research",
    "conditions": "Conditions research",
}


def _format_findings(results: list) -> str:
    parts = []
    for r in results:
        label = LANE_LABELS.get(r.lane_id, r.lane_id)
        if r.error:
            parts.append(f"=== {label} ===\n(This lane failed — information unavailable.)")
        else:
            parts.append(f"=== {label} ===\n{r.findings}")
    return "\n\n".join(parts)


async def write_brief(match: dict, results: list) -> str:
    """Compose the draft brief from the research lanes' findings."""
    home = (match.get("home") or {}).get("name") or "Home team"
    away = (match.get("away") or {}).get("name") or "Away team"
    stage = (match.get("stage") or match.get("group") or "tournament").replace("_", " ").title()

    prompt = WRITER_PROMPT.format(
        home=home,
        away=away,
        stage=stage,
        kickoff=match.get("utc_date") or "TBC",
        venue=match.get("venue") or "TBC",
        findings=_format_findings(results),
    )
    llm = get_llm()
    response = await llm.ainvoke(
        [HumanMessage(content=prompt)],
        config={"run_name": "brief-writer"},
    )
    return response.content.strip()
