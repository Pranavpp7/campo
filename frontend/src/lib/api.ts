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

export interface StreamHandlers {
  /** Called per model token — append to the growing answer. */
  onToken: (text: string) => void
  onDone: (latencyMs: number) => void
  onError: (message: string) => void
}

/**
 * Streaming chat via SSE over fetch (axios can't stream response bodies in
 * the browser). Parses `data: {json}\n\n` events; the server ends the stream
 * with a `done` or `error` event.
 */
export async function streamChat(request: ChatRequest, handlers: StreamHandlers): Promise<void> {
  const response = await fetch(`${BASE_URL}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!response.ok || !response.body) {
    handlers.onError(`Campo returned an error (${response.status}). Try again, or check the backend logs.`)
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finished = false

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // SSE events are separated by a blank line; keep the last partial chunk.
    const events = buffer.split('\n\n')
    buffer = events.pop() ?? ''

    for (const event of events) {
      const line = event.split('\n').find((l) => l.startsWith('data: '))
      if (!line) continue
      try {
        const payload = JSON.parse(line.slice(6))
        if (payload.type === 'token') handlers.onToken(payload.text)
        else if (payload.type === 'done') {
          finished = true
          handlers.onDone(payload.latency_ms)
        } else if (payload.type === 'error') {
          finished = true
          handlers.onError(payload.message)
        }
      } catch {
        // Malformed frame — skip it; the terminal event will still arrive.
      }
    }
  }

  if (!finished) {
    handlers.onError('The connection dropped before Campo finished answering. Try again.')
  }
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
