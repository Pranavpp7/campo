from datetime import datetime, timezone
from pydantic import BaseModel, Field

from prompts.briefs import (
    TEAM_LANE_TEMPLATE,
    MATCHUP_LANE_TEMPLATE,
    CONDITIONS_LANE_TEMPLATE,
)

# The planner is deterministic — a pre-match brief always decomposes into the
# same four research lanes, only parameterized by the fixture. An LLM planner
# here would add latency and nondeterminism without adding value; the
# multi-agent leverage in this pipeline comes from the parallel workers and
# the writer/verifier split, not from dynamic task decomposition.

LANES = ("home_team", "away_team", "matchup", "conditions")


class ResearchTask(BaseModel):
    lane_id: str = Field(description="One of the fixed research lanes")
    instructions: str = Field(description="Fully parameterized task for the worker")


def _friendly_stage(stage: str | None, group: str | None) -> str:
    """'LAST_16' -> 'Last 16'; fall back to the group label or a generic word."""
    if stage:
        return stage.replace("_", " ").title()
    return group or "tournament"


def _friendly_kickoff(utc_date: str | None) -> str:
    if not utc_date:
        return "date TBC"
    try:
        dt = datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
    except ValueError:
        return utc_date
    return dt.astimezone(timezone.utc).strftime("%A %d %B %Y, %H:%M")


def plan_research(match: dict) -> list[ResearchTask]:
    """Decompose a shaped match dict (see tools.football_data.get_match_data)
    into the four research lane tasks."""
    home = (match.get("home") or {}).get("name") or "Home team"
    away = (match.get("away") or {}).get("name") or "Away team"
    venue = match.get("venue") or "venue TBC"
    stage = _friendly_stage(match.get("stage"), match.get("group"))
    kickoff = _friendly_kickoff(match.get("utc_date"))

    referees = match.get("referees") or []
    referees_clause = (
        f" ({', '.join(referees)})" if referees else " (assignment not yet known)"
    )

    return [
        ResearchTask(
            lane_id="home_team",
            instructions=TEAM_LANE_TEMPLATE.format(
                team=home, opponent=away, stage=stage, kickoff=kickoff
            ),
        ),
        ResearchTask(
            lane_id="away_team",
            instructions=TEAM_LANE_TEMPLATE.format(
                team=away, opponent=home, stage=stage, kickoff=kickoff
            ),
        ),
        ResearchTask(
            lane_id="matchup",
            instructions=MATCHUP_LANE_TEMPLATE.format(
                home=home, away=away, stage=stage, kickoff=kickoff
            ),
        ),
        ResearchTask(
            lane_id="conditions",
            instructions=CONDITIONS_LANE_TEMPLATE.format(
                home=home,
                away=away,
                venue=venue,
                kickoff=kickoff,
                referees_clause=referees_clause,
            ),
        ),
    ]
