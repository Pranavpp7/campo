import type { Turn } from '../types'
import MessageBubble from './MessageBubble'

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
  onPickExample: (text: string) => void
}

export default function MessageList({ turns, onPickExample }: Props) {
  if (turns.length === 0) {
    return (
      <div className="messages messages--empty">
        <div className="empty">
          <p className="empty__eyebrow">THREE SPECIALIST AGENTS · ONE BRIEFING</p>
          <h2 className="empty__headline">Ask the match desk.</h2>
          <p className="empty__lede">
            Campo routes your question to specialist agents — match intelligence,
            travel logistics and local business insight — then returns one
            briefing. Start with a question.
          </p>
          <ul className="examples">
            {EXAMPLES.map((example) => (
              <li key={example.text}>
                <button
                  type="button"
                  className="example-chip"
                  onClick={() => onPickExample(example.text)}
                >
                  <span className="example-chip__tag">{example.tag}</span>
                  {example.text}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    )
  }

  // Newest first — the latest answer sits directly beneath the input.
  return (
    <div className="messages">
      {turns.map((turn) => (
        <article className="turn" key={turn.id}>
          <MessageBubble role="user" content={turn.question} />
          <MessageBubble
            role="campo"
            content={turn.errorMessage ?? turn.answer ?? ''}
            loading={turn.status === 'pending'}
            error={turn.status === 'error'}
          />
        </article>
      ))}
    </div>
  )
}
