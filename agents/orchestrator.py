import json
import asyncio
from datetime import datetime, timezone
from typing import Annotated
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, SystemMessage
from llm.factory import get_classifier_llm
from agents.scout import run_scout
from agents.logistics import run_logistics
from agents.localpulse import run_localpulse
from memory.memory_manager import build_context_message, extract_and_save

# ── Constants ─────────────────────────────────────────────────────────────────
VALID_AGENTS = {"scout", "logistics", "localpulse"}
AGENT_TIMEOUT_SECONDS = 120

AGENT_RUNNERS = {
    "scout": run_scout,
    "logistics": run_logistics,
    "localpulse": run_localpulse,
}

AGENT_DISPLAY_NAMES = {
    "scout": "Scout (Match Intelligence)",
    "logistics": "Logistics (Travel Planning)",
    "localpulse": "LocalPulse (Business Intelligence)",
}

# ── State Schema ──────────────────────────────────────────────────────────────
class OrchestratorState(BaseModel):
    """State passed between LangGraph nodes."""
    message: str = Field(description="The user's original message")
    session_id: str = Field(description="Session ID for short-term memory")
    user_id: str = Field(default="default", description="User ID for long-term memory")
    agents: list[str] = Field(default_factory=list, description="Classified agent names")
    memory_context: str | None = Field(default=None, description="Long-term memory context, loaded once per request")
    agent_results: dict[str, dict] = Field(default_factory=dict, description="Results keyed by agent name")
    response: str = Field(default="", description="Final synthesized response")
    agents_used: list[str] = Field(default_factory=list, description="Agents that ran successfully")
    error: str | None = Field(default=None, description="Top-level error if orchestration failed")

# ── Prompts ───────────────────────────────────────────────────────────────────
CLASSIFY_PROMPT = """You are an intent classifier for Campo, a multi-agent World Cup 2026 assistant.

Available agents:
- scout: Match intelligence — team form, squad news, injuries, head-to-head,
  tactical analysis, and (only if explicitly requested) match outcome predictions.
- logistics: Fan travel planning — getting to matches, venue weather,
  accommodation areas, multi-match itinerary feasibility.
- localpulse: Business intelligence for food & beverage / hospitality operators
  near venues — expected demand, weather-informed operations, local regulations.

Given the user's message, decide which agent(s) are relevant. A message can need
multiple agents (e.g. a fan traveling to a match who also runs a bar near a venue
needs scout + logistics + localpulse).

Respond with a JSON array of agent names from ["scout", "logistics", "localpulse"].
Choose only the agents genuinely relevant to the message — don't include one
"just in case".

User message: {message}

Respond with JSON only, no other text.
"""

SYNTHESIS_PROMPT = """You are the synthesis layer of Campo, a multi-agent World Cup 2026 assistant.

You have received responses from one or more specialist agents. Your job is to
combine them into a single, coherent, well-structured response for the user.

Rules:
1. Preserve all specific facts, numbers, names, and citations from agent outputs —
   do NOT summarize away concrete detail (injury names, weather figures, permit
   deadlines, distances, etc.)
2. Eliminate redundancy — if multiple agents mention the same fact (e.g. venue
   name, match date), state it once.
3. Structure clearly — use headers or clear transitions if the response covers
   multiple domains (e.g. match intel + travel + business).
4. Do not invent any information not present in the agent outputs.
5. If an agent returned an error or timed out, note briefly that that area of
   information was unavailable, and continue with what is available.
6. Match the user's register — if they asked casually, respond conversationally;
   if they asked in detail, give full detail.

User message:
{message}

Agent outputs:
{agent_outputs}

Write a single, unified response now.
"""

# ── Nodes ─────────────────────────────────────────────────────────────────────
async def classify_node(state: OrchestratorState) -> OrchestratorState:
    """Classify which agents are relevant to the user's message."""
    try:
        llm = get_classifier_llm()
        prompt = CLASSIFY_PROMPT.format(message=state.message)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        agents = json.loads(raw.strip())
        agents = [a for a in agents if a in VALID_AGENTS]
        agents = agents if agents else ["scout"]

    except Exception as e:
        print(f"Classification error, defaulting to scout: {e}")
        agents = ["scout"]

    return state.model_copy(update={"agents": agents})

async def dispatch_node(state: OrchestratorState) -> OrchestratorState:
    """Dispatch to all classified agents in parallel."""
    results: dict[str, dict] = {}

    # Load long-term memory context ONCE per request, instead of each agent
    # independently re-running the same mem0 vector search.
    memory_context = await build_context_message(state.user_id, state.message)

    # Inject the current date so agents reason relative to "now" (e.g. don't
    # plan travel to a match that has already been played). Prepended to the
    # memory_context string so it rides the existing injection path — no new
    # runner parameter — and it still reaches agents when there are no memories.
    current_date = datetime.now(timezone.utc).strftime("%A, %d %B %Y")
    date_context = (
        f"The current date is {current_date} (UTC). Reason relative to this date — "
        "distinguish matches already played from upcoming ones."
    )
    memory_context = (
        f"{date_context}\n\n{memory_context}" if memory_context else date_context
    )

    async def run_with_timeout(agent_name: str) -> dict:
        runner = AGENT_RUNNERS[agent_name]
        try:
            return await asyncio.wait_for(
                runner(state.message, state.session_id, state.user_id, memory_context),
                timeout=AGENT_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            return {
                "result": f"{AGENT_DISPLAY_NAMES[agent_name]} timed out after {AGENT_TIMEOUT_SECONDS}s.",
                "sources": [],
                "confidence": "low",
                "error": "timeout",
                "fallbacks_used": [],
            }
        except Exception as e:
            return {
                "result": f"{AGENT_DISPLAY_NAMES[agent_name]} encountered an error: {str(e)}",
                "sources": [],
                "confidence": "low",
                "error": str(e),
                "fallbacks_used": [],
            }

    # Run all classified agents fully in parallel. Previously Scout ran first
    # (serial) so others could read its scout_result from session context, but
    # that added a full agent's latency before the rest even started. The
    # downstream agents no longer read scout_result, so there's no ordering need.
    all_results = await asyncio.gather(
        *[run_with_timeout(a) for a in state.agents]
    )
    for agent_name, result in zip(state.agents, all_results):
        results[agent_name] = result

    # Extract and persist any new long-term preferences ONCE per request,
    # instead of each agent re-running the same Groq extraction on the same message.
    await extract_and_save(state.user_id, state.message)

    agents_used = [a for a, r in results.items() if not r.get("error")]

    return state.model_copy(update={
        "memory_context": memory_context,
        "agent_results": results,
        "agents_used": agents_used,
    })

async def synthesize_node(state: OrchestratorState) -> OrchestratorState:
    """Synthesize agent outputs into a single coherent response."""
    try:
        # Build agent outputs string for the synthesis prompt
        agent_outputs_parts = []
        for agent_name, result in state.agent_results.items():
            display = AGENT_DISPLAY_NAMES[agent_name]
            content = result.get("result", "No output.")
            agent_outputs_parts.append(f"=== {display} ===\n{content}")
        agent_outputs = "\n\n".join(agent_outputs_parts)

        # Single-agent case: skip synthesis LLM call, return directly
        if len(state.agent_results) == 1:
            only_result = next(iter(state.agent_results.values()))
            return state.model_copy(update={"response": only_result["result"]})

        # Multi-agent case: synthesize.
        # Synthesis is text combination (merge/dedupe structured agent outputs),
        # not heavy reasoning — the lightweight classifier-tier model is
        # sufficient and avoids adding another large-model call to an already
        # expensive multi-agent path (less latency, less rate-limit pressure).
        llm = get_classifier_llm()
        prompt = SYNTHESIS_PROMPT.format(
            message=state.message,
            agent_outputs=agent_outputs,
        )
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return state.model_copy(update={"response": response.content.strip()})

    except Exception as e:
        # Fallback: concatenate raw outputs rather than losing them
        fallback = "\n\n".join(
            f"**{AGENT_DISPLAY_NAMES[a]}**\n{r['result']}"
            for a, r in state.agent_results.items()
        )
        return state.model_copy(update={
            "response": fallback,
            "error": f"Synthesis failed ({e}), showing raw agent outputs.",
        })

# ── Graph ─────────────────────────────────────────────────────────────────────
def _build_graph() -> StateGraph:
    graph = StateGraph(OrchestratorState)

    graph.add_node("classify", classify_node)
    graph.add_node("dispatch", dispatch_node)
    graph.add_node("synthesize", synthesize_node)

    graph.set_entry_point("classify")
    graph.add_edge("classify", "dispatch")
    graph.add_edge("dispatch", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()

_graph = _build_graph()

# ── Public API ────────────────────────────────────────────────────────────────
async def run_orchestrator(
    message: str,
    session_id: str,
    user_id: str = "default",
) -> dict:
    """Entry point for the orchestrator — called by /chat."""
    try:
        initial_state = OrchestratorState(
            message=message,
            session_id=session_id,
            user_id=user_id,
        )
        final_state = await _graph.ainvoke(initial_state)

        return {
            "response": final_state.get("response", ""),
            "agents_used": final_state.get("agents_used", []),
            "error": final_state.get("error"),
            "agent_results": final_state.get("agent_results", {}),
        }

    except Exception as e:
        return {
            "response": f"Orchestrator encountered an unexpected error: {str(e)}",
            "agents_used": [],
            "error": str(e),
            "agent_results": {},
        }