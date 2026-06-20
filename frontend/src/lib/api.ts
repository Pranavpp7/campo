import axios from 'axios'
import type { ChatRequest, ChatResponse } from '../types'

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
