import asyncio
from langchain_core.tools import tool


@tool
async def get_match_brief(team_name: str) -> str:
    """Get Campo's verified pre-match brief for a team playing today.

    The brief is pre-researched, fact-checked match intelligence: form,
    availability, the matchup, and conditions. ALWAYS check this first when
    the user asks about one of today's matches — it is faster and more
    reliable than researching from scratch.

    Args:
        team_name: Either team's country name (e.g. "France", "Morocco").

    Returns:
        The brief in markdown, or a note that none exists for that team today.
    """
    # Lazy imports keep tool import light (this module loads with the agent).
    from tools.football_data import get_wc_today_matches_data
    from briefs.store import get_brief

    try:
        matches, _ = await asyncio.to_thread(get_wc_today_matches_data)
    except Exception as e:
        return f"Could not check today's fixtures: {e}"

    wanted = team_name.strip().lower()
    for m in matches:
        home = ((m.get("home") or {}).get("name") or "").lower()
        away = ((m.get("away") or {}).get("name") or "").lower()
        if wanted and (wanted in home or wanted in away):
            match_id = m.get("id")
            if match_id is None:
                continue
            record = await get_brief(match_id)
            if record and record.get("status") == "ready":
                header = (
                    f"Verified pre-match brief — {m['home'].get('name')} vs "
                    f"{m['away'].get('name')} (generated {record.get('generated_at')}):\n\n"
                )
                return header + (record.get("brief_markdown") or "")
            return (
                f"{m['home'].get('name')} vs {m['away'].get('name')} is on today's "
                "slate but its brief isn't ready yet — research the question "
                "directly with your other tools."
            )

    return (
        f"No match involving '{team_name}' on today's slate — briefs only exist "
        "for today's fixtures. Research the question directly with your other tools."
    )
