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

// ── Today screen ─────────────────────────────────────────────────────────────
// Mirrors GET /today-data. Every field can come back null/empty from the
// upstream football-data feed, so consumers must render defensively.

/** Normalized by the backend from football-data.org's wider vocabulary. */
export type MatchStatus = 'SCHEDULED' | 'LIVE' | 'FINISHED'

export interface TeamRef {
  name: string | null
  crest: string | null
}

export interface Match {
  utc_date: string | null
  home: TeamRef
  away: TeamRef
  home_score: number | null
  away_score: number | null
  status: MatchStatus
  venue: string | null
  group: string | null
}

export interface StandingRow {
  position: number | null
  team: TeamRef
  played: number | null
  points: number | null
  won: number | null
  draw: number | null
  lost: number | null
  goals_for: number | null
  goals_against: number | null
  goal_difference: number | null
}

export interface GroupStanding {
  group: string | null
  table: StandingRow[]
}

export interface TodayData {
  matches: Match[]
  recent_matches: Match[]
  standings: GroupStanding[]
  /** When the data was actually fetched upstream — may lag `now` by the cache TTL. */
  as_of: string
  /** Per-dataset failures; the arrays for failed datasets come back empty. */
  errors: Record<string, string> | null
}

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
