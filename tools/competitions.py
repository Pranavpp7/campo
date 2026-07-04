import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# One place that knows which competition Campo is serving. Everything
# competition-shaped (football-data code, ESPN league slug, reference
# timezone, prompt wording) derives from here, so flipping COMPETITION_CODE
# in .env is genuinely all it takes to point Campo at a new tournament
# or league season.


@dataclass(frozen=True)
class Competition:
    code: str            # football-data.org competition code
    label: str           # human-readable name, used in prompts and the UI
    espn_slug: str | None  # ESPN league slug; None disables the ESPN tools
    tz: str              # IANA timezone that defines the fan-facing "today"
    tz_note: str         # one-line timezone caveat injected into agent context


COMPETITIONS: dict[str, Competition] = {
    "WC": Competition(
        code="WC",
        label="2026 FIFA World Cup",
        espn_slug="fifa.world",
        # Venues span UTC-4 (East Coast) to UTC-7 (Pacific); Central time is
        # the compromise that keeps an evening kickoff on the correct
        # fan-facing day even after its utcDate rolls over to tomorrow.
        tz="America/Chicago",
        tz_note=(
            "All venues are in North American time zones (roughly UTC-4 to "
            "UTC-7), so near the UTC day boundary a venue's local date may be "
            "the previous day."
        ),
    ),
    "PL": Competition(
        code="PL",
        label="Premier League",
        espn_slug="eng.1",
        tz="Europe/London",
        tz_note="All venues are in the UK (UTC+0/+1).",
    ),
    "CL": Competition(
        code="CL",
        label="UEFA Champions League",
        espn_slug="uefa.champions",
        tz="Europe/Paris",
        tz_note=(
            "Venues span Europe (roughly UTC+0 to UTC+3); kickoff local dates "
            "can differ from UTC dates late in the evening."
        ),
    ),
}


def _load_active() -> Competition:
    code = os.getenv("COMPETITION_CODE", "WC").upper()
    if code in COMPETITIONS:
        return COMPETITIONS[code]
    # Unknown code: still usable against football-data.org, with generic
    # wording and no ESPN coverage rather than a crash.
    return Competition(
        code=code,
        label=f"the {code} competition",
        espn_slug=None,
        tz="UTC",
        tz_note="Venue local dates may differ from UTC dates.",
    )


ACTIVE = _load_active()
ACTIVE_TZ = ZoneInfo(ACTIVE.tz)


def date_context() -> str:
    """The current-date system context injected into every agent call —
    chat, research workers, writer and verifier all share this wording."""
    now = datetime.now(timezone.utc).strftime("%A, %d %B %Y, %H:%M UTC")
    return (
        f"The current date and time is {now}. Reason relative to this. "
        f"You are covering the {ACTIVE.label}. {ACTIVE.tz_note} "
        "Account for this when judging whether a match has already been "
        "played, and distinguish matches already played from upcoming ones."
    )
