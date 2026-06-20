// ── API contract (mirrors the FastAPI backend) ──────────────────────────────

export interface ChatRequest {
  session_id: string
  message: string
  user_id?: string
}

export interface ChatResponse {
  /** Markdown — rendered with react-markdown + remark-gfm. */
  response: string
  /** Subset of ["scout", "logistics", "localpulse"]. */
  agents_used: string[]
  trace_url: string | null
  latency_ms: number
}

export type AgentId = 'scout' | 'logistics' | 'localpulse'

/** A single query↔answer exchange, tracked through its lifecycle. */
export interface Turn {
  id: string
  question: string
  answer: string | null
  agentsUsed: AgentId[]
  latencyMs: number | null
  status: 'pending' | 'done' | 'error'
  errorMessage?: string
}
