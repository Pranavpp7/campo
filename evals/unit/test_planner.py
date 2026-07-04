# evals/unit/test_planner.py
"""
Unit tests for the brief planner.

plan_research() is pure and deterministic — no LLM, no services, no async.
These tests pin the decomposition contract the rest of the pipeline
depends on: four lanes, correctly parameterized, correctly scoped.

Run:
    uv run pytest evals/unit/test_planner.py -v
"""
import pytest
from briefs.planner import plan_research, LANES

KNOCKOUT_MATCH = {
    "id": 537375,
    "utc_date": "2026-07-04T20:00:00Z",
    "home": {"name": "Paraguay", "crest": None},
    "away": {"name": "France", "crest": None},
    "venue": "AT&T Stadium",
    "stage": "LAST_16",
    "group": None,
    "referees": ["Jesus Valenzuela"],
}

GROUP_MATCH = {
    "id": 1001,
    "utc_date": "2026-06-15T01:00:00Z",
    "home": {"name": "Canada", "crest": None},
    "away": {"name": "Morocco", "crest": None},
    "venue": "BMO Field",
    "stage": None,
    "group": "Group B",
    "referees": [],
}


@pytest.mark.unit
def test_four_lanes_in_order():
    tasks = plan_research(KNOCKOUT_MATCH)
    assert [t.lane_id for t in tasks] == list(LANES)


@pytest.mark.unit
def test_team_lanes_are_scoped_to_their_team():
    tasks = {t.lane_id: t for t in plan_research(KNOCKOUT_MATCH)}
    home = tasks["home_team"].instructions
    away = tasks["away_team"].instructions

    # Each team lane researches its team and explicitly defers the opponent.
    assert home.startswith("Research task: Paraguay")
    assert "Only research Paraguay" in home
    assert "Another worker covers France" in home

    assert away.startswith("Research task: France")
    assert "Only research France" in away
    assert "Another worker covers Paraguay" in away


@pytest.mark.unit
def test_matchup_lane_names_both_teams():
    tasks = {t.lane_id: t for t in plan_research(KNOCKOUT_MATCH)}
    matchup = tasks["matchup"].instructions
    assert "Paraguay vs France" in matchup
    assert "head-to-head" in matchup.lower()


@pytest.mark.unit
def test_conditions_lane_has_venue_and_referee():
    tasks = {t.lane_id: t for t in plan_research(KNOCKOUT_MATCH)}
    conditions = tasks["conditions"].instructions
    assert "AT&T Stadium" in conditions
    assert "Jesus Valenzuela" in conditions


@pytest.mark.unit
def test_conditions_lane_without_referee_says_so():
    tasks = {t.lane_id: t for t in plan_research(GROUP_MATCH)}
    conditions = tasks["conditions"].instructions
    assert "assignment not yet known" in conditions


@pytest.mark.unit
def test_stage_is_humanized():
    tasks = plan_research(KNOCKOUT_MATCH)
    # LAST_16 -> "Last 16", not the raw enum
    assert "Last 16" in tasks[0].instructions
    assert "LAST_16" not in tasks[0].instructions


@pytest.mark.unit
def test_group_match_falls_back_to_group_label():
    tasks = plan_research(GROUP_MATCH)
    assert "Group B" in tasks[0].instructions


@pytest.mark.unit
def test_kickoff_is_human_readable():
    tasks = plan_research(KNOCKOUT_MATCH)
    assert "Saturday 04 July 2026, 20:00" in tasks[0].instructions


@pytest.mark.unit
def test_missing_fields_do_not_crash():
    """Upstream data can be sparse — TBD fixtures must still plan cleanly."""
    sparse = {"id": 9, "home": {}, "away": {}, "venue": None, "utc_date": None}
    tasks = plan_research(sparse)
    assert len(tasks) == 4
    assert "Home team" in tasks[0].instructions
    assert "date TBC" in tasks[0].instructions
    assert "venue TBC" in tasks[3].instructions
