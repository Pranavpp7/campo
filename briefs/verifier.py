import asyncio
import json
from langchain_core.messages import HumanMessage

from llm.factory import get_llm
from prompts.briefs import VERIFIER_PROMPT

# Keep the verifier's total evidence bounded — 4 lanes x several tool calls
# can get large. Per-item truncation already happened in the researcher.
# 24k chars ≈ 6k tokens: leaves the full prompt within the Groq fallbacks'
# free-tier TPM, so a saturated OpenRouter doesn't take verification down
# with it (observed: 40k evidence made the fallback chain 429 too).
MAX_EVIDENCE_TOTAL_CHARS = 24_000

# One retry after a cooldown when providers rate-limit — same treatment the
# research lanes get in the pipeline.
RATE_LIMIT_RETRY_DELAY_SECONDS = 60


def _format_evidence(results: list) -> str:
    parts = []
    for r in results:
        if r.error or not r.evidence:
            continue
        items = "\n---\n".join(r.evidence)
        parts.append(f"### Lane: {r.lane_id}\n{items}")
    corpus = "\n\n".join(parts)
    return corpus[:MAX_EVIDENCE_TOTAL_CHARS]


def _strip_json_fences(raw: str) -> str:
    """Same fence-stripping discipline as the old classifier parse."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


async def verify_brief(draft: str, results: list) -> dict:
    """Fact-check the draft against the raw tool-output evidence.

    Returns {brief_markdown, claims, verified}. On any verifier failure the
    unverified draft ships with verified=False — a fact-checking hiccup must
    never lose a brief.
    """
    try:
        evidence = _format_evidence(results)
        if not evidence:
            return {"brief_markdown": draft, "claims": [], "verified": False}

        prompt = VERIFIER_PROMPT.format(draft=draft, evidence=evidence)
        llm = get_llm()
        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
        except Exception as e:
            if "429" not in str(e) and "rate" not in str(e).lower():
                raise
            await asyncio.sleep(RATE_LIMIT_RETRY_DELAY_SECONDS)
            response = await llm.ainvoke([HumanMessage(content=prompt)])

        parsed = json.loads(_strip_json_fences(response.content))
        revised = parsed.get("revised_brief") or draft
        claims = [
            {
                "claim": c.get("claim", ""),
                "verdict": c.get("verdict", "unsupported"),
                "note": c.get("note", ""),
            }
            for c in parsed.get("claims", [])
            if isinstance(c, dict) and c.get("claim")
        ]
        return {"brief_markdown": revised, "claims": claims, "verified": True}

    except Exception as e:
        print(f"Verifier failed (shipping unverified draft): {e}")
        return {"brief_markdown": draft, "claims": [], "verified": False}
