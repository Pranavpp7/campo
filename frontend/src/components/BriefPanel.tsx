import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Brief, Match } from '../types'
import { fetchBrief, generateBrief, describeError } from '../lib/api'

interface Props {
  match: Match
  onClose: () => void
}

const POLL_MS = 5000

type PanelState =
  | { status: 'loading' }
  | { status: 'generating' }
  | { status: 'ready'; brief: Brief }
  | { status: 'error'; message: string }

function formatGeneratedAt(iso?: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString([], {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

/**
 * Slide-over panel showing a match's verified pre-match brief.
 *
 * Lifecycle: on open, fetch the brief. "none"/"failed" → trigger background
 * generation and poll; "generating" → poll; "ready" → render. Polling stops
 * on unmount and the moment a terminal state arrives.
 */
export default function BriefPanel({ match, onClose }: Props) {
  const [state, setState] = useState<PanelState>({ status: 'loading' })
  const pollRef = useRef<number | null>(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const startPolling = useCallback(
    (matchId: number) => {
      stopPolling()
      pollRef.current = window.setInterval(async () => {
        try {
          const brief = await fetchBrief(matchId)
          if (brief.status === 'ready') {
            stopPolling()
            setState({ status: 'ready', brief })
          } else if (brief.status === 'failed') {
            stopPolling()
            setState({ status: 'error', message: brief.error ?? 'Brief generation failed.' })
          }
          // "generating" → keep polling silently.
        } catch {
          // One failed poll isn't fatal — the next tick retries.
        }
      }, POLL_MS)
    },
    [stopPolling],
  )

  const load = useCallback(
    async (options?: { force: boolean }) => {
      if (match.id == null) {
        setState({ status: 'error', message: 'No match id available for this fixture.' })
        return
      }
      setState({ status: 'loading' })
      try {
        const brief = options?.force
          ? await generateBrief(match.id, true)
          : await fetchBrief(match.id)

        if (brief.status === 'ready') {
          setState({ status: 'ready', brief })
          return
        }
        if (brief.status === 'none' || brief.status === 'failed') {
          // No brief yet (or a failed one) — kick off generation.
          await generateBrief(match.id, brief.status === 'failed')
        }
        setState({ status: 'generating' })
        startPolling(match.id)
      } catch (error) {
        setState({ status: 'error', message: describeError(error) })
      }
    },
    [match.id, startPolling],
  )

  useEffect(() => {
    void load()
    return stopPolling
  }, [load, stopPolling])

  // Escape closes the panel, like any overlay.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const title = `${match.home?.name ?? 'TBD'} vs ${match.away?.name ?? 'TBD'}`

  return (
    <div className="brief-overlay" role="presentation" onClick={onClose}>
      <aside
        className="brief-panel"
        role="dialog"
        aria-modal="true"
        aria-label={`Match brief: ${title}`}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="brief-panel__header">
          <div>
            <span className="brief-panel__kicker">MATCH BRIEF</span>
            <h2 className="brief-panel__title">{title}</h2>
          </div>
          <button
            type="button"
            className="brief-panel__close"
            onClick={onClose}
            aria-label="Close brief"
          >
            ×
          </button>
        </header>

        <div className="brief-panel__body">
          {state.status === 'loading' && (
            <p className="brief-panel__status" role="status">
              Loading brief…
            </p>
          )}

          {state.status === 'generating' && (
            <div className="brief-panel__status" role="status">
              <p className="brief-panel__generating-title">
                Campo's research desk is on it.
              </p>
              <p className="brief-panel__generating-detail">
                Four researchers are working the match in parallel — team news,
                the matchup, and conditions — then every claim gets fact-checked.
                Usually under two minutes.
              </p>
            </div>
          )}

          {state.status === 'error' && (
            <div className="brief-panel__status" role="alert">
              <p>{state.message}</p>
              <button
                type="button"
                className="brief-panel__retry"
                onClick={() => void load({ force: true })}
              >
                Try again
              </button>
            </div>
          )}

          {state.status === 'ready' && (
            <>
              <div className="brief-panel__meta">
                {state.brief.verified ? (
                  <span className="brief-panel__badge brief-panel__badge--verified">
                    ✓ FACT-CHECKED
                  </span>
                ) : (
                  <span className="brief-panel__badge">UNVERIFIED DRAFT</span>
                )}
                {state.brief.generated_at && (
                  <span className="brief-panel__stamp">
                    {formatGeneratedAt(state.brief.generated_at)}
                  </span>
                )}
              </div>

              <div className="markdown brief-panel__content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {state.brief.brief_markdown ?? ''}
                </ReactMarkdown>
              </div>

              {(state.brief.claims?.length ?? 0) > 0 && (
                <details className="brief-panel__claims">
                  <summary>
                    Claims checked ({state.brief.claims!.length})
                  </summary>
                  <ul>
                    {state.brief.claims!.map((c, i) => (
                      <li
                        key={i}
                        className={
                          c.verdict === 'supported'
                            ? 'brief-claim brief-claim--supported'
                            : 'brief-claim brief-claim--unsupported'
                        }
                      >
                        <span className="brief-claim__verdict">
                          {c.verdict === 'supported' ? '✓' : '✗'}
                        </span>
                        <span>
                          {c.claim}
                          {c.note && <em className="brief-claim__note"> — {c.note}</em>}
                        </span>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </>
          )}
        </div>
      </aside>
    </div>
  )
}
