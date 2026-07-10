import os
from datetime import datetime, timedelta, timezone

# Near-kickoff refresh policy. Confirmed lineups and late team news land in
# the last ~75 minutes before kickoff; a brief researched hours earlier
# misses them. Inside the window, a ready brief that predates the window is
# regenerated once — pure policy here, so it unit-tests without Redis or LLMs.

REFRESH_WINDOW_MINUTES = int(os.getenv("BRIEF_REFRESH_WINDOW_MINUTES", "90"))


def _parse_utc(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    # Brief records store aware ISO timestamps; treat a bare one as UTC.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def should_refresh(record: dict, now: datetime | None = None) -> bool:
    """True when a ready brief should be regenerated for lineup-window news.

    Fires only inside [kickoff - window, kickoff), and only for briefs
    generated before the window opened — a refreshed brief's generated_at
    lands inside the window, so the rule self-limits to one refresh per match.
    Missing or failed briefs are the scheduler's normal generation path, not
    a refresh.
    """
    if record.get("status") != "ready":
        return False
    kickoff = _parse_utc(record.get("kickoff_utc"))
    generated_at = _parse_utc(record.get("generated_at"))
    if kickoff is None or generated_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    window_open = kickoff - timedelta(minutes=REFRESH_WINDOW_MINUTES)
    return window_open <= now < kickoff and generated_at < window_open
