import { useEffect, useRef, useState } from 'react'
import type { Turn } from '../types'
import MessageList from './MessageList'

const EXAMPLES: Array<{ tag: string; text: string }> = [
  {
    tag: 'MATCH INTEL',
    text: 'Tell me about the Morocco vs Brazil match — form, injuries, who to watch.',
  },
  {
    tag: 'TRAVEL',
    text: 'I’m travelling to Dallas for a match. What should I know before I go?',
  },
  {
    tag: 'MATCH DAY OPS',
    text: 'I run a sports bar near MetLife Stadium — what should I expect on a match day?',
  },
  {
    tag: 'GROUPS',
    text: 'Compare the Group D contenders and project who advances.',
  },
]

interface Props {
  turns: Turn[]
  loading: boolean
  onSubmit: (question: string) => void
}

/**
 * Two modes, like every chat product:
 *  - No conversation yet → a single centered composition (headline, input,
 *    example prompts). The input IS the hero — no orphaned bar at the top.
 *  - Conversation active → messages flow top-to-bottom, input docked at the
 *    bottom, newest exchange kept in view.
 */
export default function ChatPanel({ turns, loading, onSubmit }: Props) {
  const [input, setInput] = useState('')
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const hasConversation = turns.length > 0

  // Keep the latest exchange in view as it arrives.
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [turns, loading])

  // Hand focus back to the input once an answer lands (it's disabled in flight).
  useEffect(() => {
    if (!loading) inputRef.current?.focus()
  }, [loading])

  // Auto-grow the textarea with its content (capped in CSS-matching px).
  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }, [input])

  function submit(text: string = input) {
    const trimmed = text.trim()
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

  const composer = (
    <form
      className={`composer ${hasConversation ? 'composer--docked' : 'composer--hero'}`}
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      {/* One integrated field — textarea and send button share a surface. */}
      <div className="composer__field">
        <textarea
          ref={inputRef}
          className="composer__input"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about a match, a trip, or a match-day for your venue…"
          rows={1}
          aria-label="Your question for Campo"
          disabled={loading}
        />
        <button
          type="submit"
          className="composer__send"
          disabled={loading || input.trim().length === 0}
          aria-label={loading ? 'Campo is answering' : 'Send question'}
        >
          {loading ? (
            <span className="composer__spinner" aria-hidden="true" />
          ) : (
            <svg
              viewBox="0 0 24 24"
              width="18"
              height="18"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.4"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M12 19V5M5.5 11.5 12 5l6.5 6.5" />
            </svg>
          )}
        </button>
      </div>
    </form>
  )

  const header = (
    <header className="chat-header">
      <div className="brand">
        <span className="brand__mark" aria-hidden="true" />
        <span className="brand__name">CAMPO</span>
        <span className="brand__tag">World Cup 2026 · Ask</span>
      </div>
    </header>
  )

  if (!hasConversation) {
    return (
      <section className="chat-panel" aria-label="Ask Campo">
        {header}
        <div className="hero">
          <div className="hero__inner">
            <p className="hero__eyebrow">THREE SPECIALIST AGENTS · ONE BRIEFING</p>
            <h2 className="hero__headline">
              Ask the <span className="hero__accent">match desk.</span>
            </h2>
            <p className="hero__lede">
              Match intelligence, travel logistics and local business insight —
              one briefing. Start with a question.
            </p>
            {composer}
            <ul className="examples">
              {EXAMPLES.map((example) => (
                <li key={example.text}>
                  <button
                    type="button"
                    className="example-chip"
                    onClick={() => submit(example.text)}
                  >
                    <span className="example-chip__tag">{example.tag}</span>
                    {example.text}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="chat-panel" aria-label="Query and answers">
      {header}
      <div className="messages" ref={scrollRef}>
        <MessageList turns={turns} />
      </div>
      {composer}
    </section>
  )
}
