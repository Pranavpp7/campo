import { useState } from 'react'
import type { Turn } from './types'
import { isAgentId } from './lib/agents'
import { sendChat, describeError } from './lib/api'
import ChatPanel from './components/ChatPanel'
import IntelligencePanel from './components/IntelligencePanel'

function createId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export default function App() {
  // One session id per browser session, generated once.
  const [sessionId] = useState(createId)
  const [turns, setTurns] = useState<Turn[]>([])
  const [loading, setLoading] = useState(false)

  // Newest first — the Intelligence Panel always reflects the latest query.
  const latest = turns[0] ?? null

  async function handleSubmit(question: string) {
    const id = createId()
    const pending: Turn = {
      id,
      question,
      answer: null,
      agentsUsed: [],
      latencyMs: null,
      status: 'pending',
    }
    setTurns((prev) => [pending, ...prev])
    setLoading(true)

    try {
      const res = await sendChat({
        session_id: sessionId,
        message: question,
        user_id: sessionId,
      })
      const agentsUsed = res.agents_used.filter(isAgentId)
      setTurns((prev) =>
        prev.map((turn) =>
          turn.id === id
            ? {
                ...turn,
                answer: res.response,
                agentsUsed,
                latencyMs: res.latency_ms,
                status: 'done',
              }
            : turn,
        ),
      )
    } catch (error) {
      setTurns((prev) =>
        prev.map((turn) =>
          turn.id === id
            ? { ...turn, status: 'error', errorMessage: describeError(error) }
            : turn,
        ),
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark" aria-hidden="true" />
          <span className="brand__name">CAMPO</span>
          <span className="brand__tag">World Cup 2026 · Multi-Agent Intelligence</span>
        </div>
        <div className="session" title="Session ID">
          <span className="session__label">SESSION</span>
          <span className="session__id">{sessionId.slice(0, 8)}</span>
        </div>
      </header>

      <main className="split">
        <ChatPanel turns={turns} loading={loading} onSubmit={handleSubmit} />
        <IntelligencePanel turn={latest} />
      </main>
    </div>
  )
}
