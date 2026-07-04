import axios from 'axios'
import type { Brief, ChatRequest, ChatResponse, TodayData } from '../types'

const BASE_URL = 'http://localhost:8000'

const client = axios.create({
  baseURL: BASE_URL,
  // Multi-agent runs can be slow: the backend caps each agent at 120s and then
  // still has to classify + synthesize on top, so its worst case is ~150s+.
  // Give the client comfortable headroom so it never aborts a request the
  // backend is still working on.
  timeout: 180_000,
  headers: { 'Content-Type': 'application/json' },
})

export async function sendChat(request: ChatRequest): Promise<ChatResponse> {
  const { data } = await client.post<ChatResponse>('/chat', request)
  return data
}

/**
 * Today screen data: scores + standings. Unlike /chat, this is a fast,
 * deterministic, no-LLM endpoint — so it gets a tight timeout rather than
 * the multi-minute agent budget. 20s leaves room for one upstream retry
 * cycle (the backend retries slow football-data calls with backoff).
 */
export async function fetchTodayData(): Promise<TodayData> {
  const { data } = await client.get<TodayData>('/today-data', { timeout: 20_000 })
  return data
}

/**
 * Pre-match brief endpoints. Generation runs in the background on the server
 * (~1 minute of multi-agent research), so both calls return fast — the UI
 * polls fetchBrief until `status` leaves "generating".
 */
export async function fetchBrief(matchId: number): Promise<Brief> {
  const { data } = await client.get<Brief>(`/briefs/${matchId}`, { timeout: 15_000 })
  return data
}

export async function generateBrief(matchId: number, force = false): Promise<Brief> {
  const { data } = await client.post<Brief>(
    `/briefs/${matchId}/generate`,
    null,
    { params: force ? { force: true } : undefined, timeout: 15_000 },
  )
  return data
}

/** Turn an unknown thrown value into Campo-voiced, user-facing copy. */
export function describeError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (error.code === 'ECONNABORTED') {
      return 'Campo took too long to respond. The match desk may be under heavy load — try again in a moment.'
    }
    // No response received → backend unreachable / CORS / network down.
    if (!error.response) {
      return 'Couldn’t reach Campo. Is the backend running on port 8000?'
    }
    return `Campo returned an error (${error.response.status}). Try again, or check the backend logs.`
  }
  return 'Something went wrong reaching Campo. Try again in a moment.'
}
