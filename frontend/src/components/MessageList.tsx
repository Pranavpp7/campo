import type { Turn } from '../types'
import MessageBubble from './MessageBubble'

interface Props {
  turns: Turn[]
}

/** The conversation, oldest first — newest exchange sits at the bottom,
 *  directly above the docked input. */
export default function MessageList({ turns }: Props) {
  return (
    <>
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
    </>
  )
}
