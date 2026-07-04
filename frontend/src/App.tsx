import { useState } from 'react'
import type { Turn } from './types'
import { sendChat, describeError } from './lib/api'
import ChatPanel from './components/ChatPanel'
import TabBar, { type TabId } from './components/TabBar'
import TodayScreen from './screens/TodayScreen'

function createId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('today')

  // One session id per browser session, generated once.
  const [sessionId] = useState(createId)
  const [turns, setTurns] = useState<Turn[]>([])
  const [loading, setLoading] = useState(false)

  async function handleSubmit(question: string) {
    const id = createId()
    const pending: Turn = {
      id,
      question,
      answer: null,
      latencyMs: null,
      status: 'pending',
    }
    // Oldest first — the conversation flows down to the docked input.
    setTurns((prev) => [...prev, pending])
    setLoading(true)

    try {
      const res = await sendChat({
        session_id: sessionId,
        message: question,
        user_id: sessionId,
      })
      setTurns((prev) =>
        prev.map((turn) =>
          turn.id === id
            ? {
                ...turn,
                answer: res.response,
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
      <main className="screen">
        {/*
          Both screens stay mounted so chat history and the Today fetch survive
          tab switches; only the active one is shown.
        */}
        <div className={`screen__pane${activeTab === 'today' ? '' : ' screen__pane--hidden'}`}>
          <TodayScreen />
        </div>
        <div
          className={`screen__pane${activeTab === 'ask' ? '' : ' screen__pane--hidden'}`}
        >
          {/* Fan-facing chat only — agent traces/sources/latency stay internal. */}
          <ChatPanel turns={turns} loading={loading} onSubmit={handleSubmit} />
        </div>
      </main>

      <TabBar active={activeTab} onChange={setActiveTab} />
    </div>
  )
}
