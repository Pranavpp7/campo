import { useState } from 'react'
import type { Turn } from './types'
import { streamChat, describeError } from './lib/api'
import ChatPanel from './components/ChatPanel'
import TabBar, { type TabId } from './components/TabBar'
import TodayScreen from './screens/TodayScreen'

function createId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

/**
 * Stable per-browser user id, persisted in localStorage. This is what makes
 * long-term memory (mem0) actually work: preferences extracted in one visit
 * are recalled in the next. Falls back to a per-session id if storage is
 * unavailable (private browsing).
 */
function getUserId(): string {
  const KEY = 'campo-user-id'
  try {
    const existing = localStorage.getItem(KEY)
    if (existing) return existing
    const fresh = createId()
    localStorage.setItem(KEY, fresh)
    return fresh
  } catch {
    return createId()
  }
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('today')

  // One session id per browser session; one user id per browser, persisted.
  const [sessionId] = useState(createId)
  const [userId] = useState(getUserId)
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

    const patchTurn = (patch: Partial<Turn>) =>
      setTurns((prev) =>
        prev.map((turn) => (turn.id === id ? { ...turn, ...patch } : turn)),
      )

    try {
      // Tokens render as they arrive; the turn stays 'pending' (the thinking
      // indicator) until the first token lands.
      await streamChat(
        { session_id: sessionId, message: question, user_id: userId },
        {
          onToken: (text) =>
            setTurns((prev) =>
              prev.map((turn) =>
                turn.id === id
                  ? { ...turn, answer: (turn.answer ?? '') + text }
                  : turn,
              ),
            ),
          onDone: (latencyMs) => patchTurn({ latencyMs, status: 'done' }),
          onError: (message) => patchTurn({ status: 'error', errorMessage: message }),
        },
      )
    } catch (error) {
      patchTurn({ status: 'error', errorMessage: describeError(error) })
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
