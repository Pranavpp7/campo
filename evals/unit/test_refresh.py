# evals/unit/test_refresh.py
"""
Unit tests for the near-kickoff brief refresh policy (briefs.refresh).

Pure and deterministic — no Redis, no LLM. The policy: a ready brief is
regenerated exactly once inside [kickoff - window, kickoff), and only if it
was generated before that window opened.

Run:
    uv run pytest evals/unit/test_refresh.py -v
"""
from datetime import datetime, timedelta, timezone

import pytest

from briefs.refresh import REFRESH_WINDOW_MINUTES, should_refresh

KICKOFF = datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc)
WINDOW = timedelta(minutes=REFRESH_WINDOW_MINUTES)


def _record(generated_delta: timedelta, status: str = "ready") -> dict:
    """A brief record generated `generated_delta` before kickoff."""
    return {
        "status": status,
        "kickoff_utc": KICKOFF.isoformat(),
        "generated_at": (KICKOFF - generated_delta).isoformat(),
    }


@pytest.mark.unit
def test_refreshes_old_brief_inside_window():
    record = _record(generated_delta=timedelta(hours=6))
    now = KICKOFF - WINDOW / 2
    assert should_refresh(record, now) is True


@pytest.mark.unit
def test_no_refresh_before_window_opens():
    record = _record(generated_delta=timedelta(hours=6))
    now = KICKOFF - WINDOW - timedelta(minutes=1)
    assert should_refresh(record, now) is False


@pytest.mark.unit
def test_no_refresh_after_kickoff():
    record = _record(generated_delta=timedelta(hours=6))
    assert should_refresh(record, KICKOFF) is False
    assert should_refresh(record, KICKOFF + timedelta(hours=1)) is False


@pytest.mark.unit
def test_self_limits_to_one_refresh():
    """A brief regenerated inside the window must not refresh again."""
    refreshed = _record(generated_delta=WINDOW / 2)  # generated_at inside window
    now = KICKOFF - timedelta(minutes=5)
    assert should_refresh(refreshed, now) is False


@pytest.mark.unit
def test_non_ready_records_are_not_refreshes():
    now = KICKOFF - WINDOW / 2
    assert should_refresh(_record(timedelta(hours=6), status="failed"), now) is False
    assert should_refresh({"status": "ready"}, now) is False  # no dates
    assert should_refresh({}, now) is False


@pytest.mark.unit
def test_unparseable_dates_never_refresh():
    record = {
        "status": "ready",
        "kickoff_utc": "not-a-date",
        "generated_at": "also-not-a-date",
    }
    assert should_refresh(record, KICKOFF - WINDOW / 2) is False
