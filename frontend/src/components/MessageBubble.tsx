import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface Props {
  role: 'user' | 'campo'
  /** Markdown for campo; plain text for user. Ignored while loading. */
  content: string
  loading?: boolean
  error?: boolean
}

export default function MessageBubble({ role, content, loading, error }: Props) {
  if (role === 'user') {
    return (
      <div className="bubble bubble--user">
        <span className="bubble__tag">QUERY</span>
        <p className="bubble__question">{content}</p>
      </div>
    )
  }

  return (
    <div className={`bubble bubble--campo${error ? ' bubble--error' : ''}`}>
      <span className="bubble__tag">CAMPO</span>
      {loading ? (
        <div className="bubble__thinking" role="status" aria-label="Campo is analysing">
          <span className="thinking-dot" />
          <span className="thinking-dot" />
          <span className="thinking-dot" />
          <span className="thinking-label">Routing to specialist agents…</span>
        </div>
      ) : error ? (
        <p className="bubble__error-text">{content}</p>
      ) : (
        <div className="markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
      )}
    </div>
  )
}
