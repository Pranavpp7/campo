# Campo ⚽

> Multi-agent AI system for the 2026 FIFA World Cup.

I've followed football since I was a kid. When the 2026 World Cup came to North America, I built Campo — an AI system that reasons across match intelligence, fan travel, and venue operations simultaneously, the way a knowledgeable football person actually thinks about a match day.

---

## What it does

Ask anything about the World Cup:

- *"Tell me about Morocco vs Brazil — form, key players, tactics."*
- *"I'm flying to Dallas for the match next week. What do I need to know?"*
- *"I run a bar near AT&T Stadium. What should I prepare for on match day?"*

Campo routes your question to specialist agents, each doing real tool-using ReAct reasoning, and synthesizes their outputs into one coherent briefing.

---

## Architecture

### System overview

![Campo system architecture](assets/architecture.png)

Three specialist agents — **Scout** (match intelligence), **Logistics** (fan travel planning), **LocalPulse** (venue business intelligence) — run in parallel under a LangGraph orchestrator. A lightweight classifier decides which agents to dispatch; a synthesis model merges their outputs into one response.

### Request lifecycle

![Campo request lifecycle](assets/lifecycle.png)

**Memory is two-tier:** Redis for session history and cross-agent context within a conversation; mem0 + Qdrant for long-term user preferences that persist across sessions and get injected into agent context.

---

## Numbers

| | |
|--|--|
| Single-agent latency | ~20s |
| Multi-agent latency | ~40–70s |
| Classification accuracy | 48/50 golden queries |
| Memory pre-filter skip rate | 03% on impersonal queries |
| Scout GEval relevance score | 0.80 / 1.0 |
| LocalPulse GEval relevance score | 0.80–0.90 / 1.0 |

*Evaluated with DeepEval GEval using Groq gpt-oss-120b as judge, threshold 0.6.*

---

## Engineering decisions

**Parallel dispatch.** All agents start simultaneously via `asyncio.gather`. 

**Memory hoisted to orchestrator.** Each agent previously ran its own mem0 vector search and LLM extraction call on the same message — 3× redundant work per multi-agent request. Moving both to the orchestrator reduced them to 1× per request.

**Structural fix for tool hallucination.** The agent LLM invented non-existent parameters against the raw Tavily MCP schema. Instead of patching prompts, we wrapped Tavily in a minimal two-parameter function — making invalid calls structurally impossible. The hallucination hasn't recurred.

**History triplication fix.** Parallel agents each wrote to the same Redis session simultaneously — storing the user message 3× and three separate raw outputs. Moved history writes to the orchestrator: one user turn + one synthesized response per exchange. Regression-tested in `evals/integration/test_history.py`.

**Date-aware agents.** The orchestrator injects the current UTC date into every agent's system message. Logistics refuses to plan travel for matches already played. Scout labels fixtures as upcoming, live, or completed.

---

## Eval suite

```
evals/
  unit/          90 tests — classifier (50) + memory pre-filter (40)
  integration/    4 tests — Redis history correctness
  e2e/            10 tests — DeepEval GEval LLM-as-judge
```

```bash
uv run pytest evals/unit/ -v          # fast, no services needed
uv run pytest evals/integration/ -v   # needs Docker
uv run pytest evals/e2e/ -v -s        # needs full stack + uvicorn
```

---

## Setup

**Prerequisites:** Python 3.13, `uv`, Docker Desktop, Node.js

```bash
git clone https://github.com/Pranavpp7/campo.git
cd campo
uv sync
```

Create `.env` with your API keys — see `.env.example`.

```bash
docker compose up -d                           # Qdrant + Redis
uv run uvicorn api.main:app --reload           # backend on :8000
cd frontend && npm install && npm run dev      # frontend on :3000
```

Open `http://localhost:3000`

---
 
*Built during the 2026 FIFA World Cup because football deserved better AI.*