import { useRef, useState } from 'react'
import type { Turn } from '../types'
import MessageList from './MessageList'

interface Props {
  turns: Turn[]
  loading: boolean
  onSubmit: (question: string) => void
}

export default function ChatPanel({ turns, loading, onSubmit }: Props) {
  const [input, setInput] = useState('')
  const inputRef = useRef<HTMLTextAreaElement>(null)

  function submit() {
    const trimmed = input.trim()
    if (!trimmed || loading) return
    onSubmit(trimmed)
    setInput('')
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter inserts a newline.
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  function pickExample(text: string) {
    setInput(text)
    inputRef.current?.focus()
  }

  return (
    <section className="chat-panel" aria-label="Query and answers">
      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault()
          submit()
        }}
      >
        <textarea
          ref={inputRef}
          className="composer__input"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about a match, a trip, or a match-day for your venue…"
          rows={2}
          aria-label="Your question for Campo"
          disabled={loading}
        />
        <button
          type="submit"
          className={`composer__send${loading ? ' composer__send--loading' : ''}`}
          disabled={loading || input.trim().length === 0}
        >
          {loading ? 'Asking…' : 'Ask'}
        </button>
      </form>

      <MessageList turns={turns} onPickExample={pickExample} />
    </section>
  )
}
