import { useCallback, useEffect, useState } from 'react'
import type { Match, TodayData } from '../types'
import { fetchTodayData, describeError } from '../lib/api'
import MatchCard from '../components/MatchCard'
import GroupTable from '../components/GroupTable'
import BriefPanel from '../components/BriefPanel'

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: TodayData }

function formatAsOf(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
}

/** Header reused across every load state so the brand never flickers away. */
function TodayHeader({
  asOf,
  competition,
  onRefresh,
}: {
  asOf?: string
  competition?: string
  onRefresh?: () => void
}) {
  return (
    <header className="today-header">
      <div className="brand">
        <span className="brand__mark" aria-hidden="true" />
        <span className="brand__name">CAMPO</span>
        <span className="brand__tag">{competition ?? 'Football'} · Today</span>
      </div>
      {asOf && (
        <button type="button" className="today-asof" onClick={onRefresh} title="Refresh">
          <span className="today-asof__label">UPDATED</span>
          <span className="today-asof__value">{formatAsOf(asOf)}</span>
        </button>
      )}
    </header>
  )
}

/** Horizontal shimmer cards while the first fetch is in flight. */
function MatchSkeletons() {
  return (
    <div className="match-row">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="match-card match-card--skeleton" aria-hidden="true">
          <div className="skeleton skeleton--line" style={{ width: '40%' }} />
          <div className="skeleton skeleton--row" />
          <div className="skeleton skeleton--row" />
          <div className="skeleton skeleton--line" style={{ width: '60%' }} />
        </div>
      ))}
    </div>
  )
}

function StandingsSkeletons() {
  return (
    <div className="standings-row">
      {[0, 1, 2].map((i) => (
        <div key={i} className="gtable gtable--skeleton" aria-hidden="true">
          <div className="skeleton skeleton--line" style={{ width: '35%' }} />
          {[0, 1, 2, 3].map((r) => (
            <div key={r} className="skeleton skeleton--row" />
          ))}
        </div>
      ))}
    </div>
  )
}

export default function TodayScreen() {
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  // Match whose brief panel is open, if any.
  const [briefMatch, setBriefMatch] = useState<Match | null>(null)

  const load = useCallback(async () => {
    setState({ status: 'loading' })
    try {
      const data = await fetchTodayData()
      // The backend reports per-dataset failures via `errors` with a 200.
      // If every dataset failed, that's an error screen, not an empty state.
      const allEmpty =
        data.matches.length === 0 &&
        data.recent_matches.length === 0 &&
        data.standings.length === 0
      if (data.errors && allEmpty) {
        setState({ status: 'error', message: Object.values(data.errors).join(' · ') })
        return
      }
      setState({ status: 'ready', data })
    } catch (error) {
      setState({ status: 'error', message: describeError(error) })
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  if (state.status === 'loading') {
    return (
      <div className="today">
        <TodayHeader />
        <div className="today__body">
          <section className="today-section">
            <h2 className="today-section__title">Today's Matches</h2>
            <MatchSkeletons />
          </section>
          <section className="today-section">
            <h2 className="today-section__title">Group Standings</h2>
            <StandingsSkeletons />
          </section>
        </div>
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <div className="today">
        <TodayHeader />
        <div className="today__body">
          <div className="today-error" role="alert">
            <p className="today-error__title">Couldn't load today's matches</p>
            <p className="today-error__msg">{state.message}</p>
            <button type="button" className="today-error__retry" onClick={() => void load()}>
              Try again
            </button>
          </div>
        </div>
      </div>
    )
  }

  const { matches, recent_matches, standings, as_of, competition, errors } = state.data

  const FAILED_LABELS: Record<string, string> = {
    today_matches: "today's matches",
    recent_matches: 'recent results',
    standings: 'standings',
  }
  const failed = errors ? Object.keys(errors).map((k) => FAILED_LABELS[k] ?? k) : []

  return (
    <div className="today">
      <TodayHeader asOf={as_of} competition={competition} onRefresh={() => void load()} />
      <div className="today__body">
        {failed.length > 0 && (
          <div className="today-warning" role="status">
            Couldn't load {failed.join(' and ')} — showing what's available.
            <button type="button" className="today-warning__retry" onClick={() => void load()}>
              Retry
            </button>
          </div>
        )}
        <section className="today-section">
          <h2 className="today-section__title">Today's Matches</h2>
          {matches.length === 0 ? (
            <p className="today-empty">
              {errors?.today_matches
                ? 'Match data is unavailable right now.'
                : 'No matches scheduled today.'}
            </p>
          ) : (
            <div className="match-row">
              {matches.map((m, i) => (
                <MatchCard key={`${m.utc_date}-${i}`} match={m} onBrief={setBriefMatch} />
              ))}
            </div>
          )}
        </section>

        {recent_matches.length > 0 && (
          <section className="today-section">
            <h2 className="today-section__title">Recent Results</h2>
            <div className="match-row">
              {recent_matches.map((m, i) => (
                <MatchCard key={`recent-${m.utc_date}-${i}`} match={m} />
              ))}
            </div>
          </section>
        )}

        <section className="today-section">
          <h2 className="today-section__title">Group Standings</h2>
          {standings.length === 0 ? (
            <p className="today-empty">
              {errors?.standings
                ? 'Standings data is unavailable right now.'
                : "Standings aren't available yet."}
            </p>
          ) : (
            <div className="standings-row">
              {standings.map((g, i) => (
                <GroupTable key={g.group || i} group={g} />
              ))}
            </div>
          )}
        </section>
      </div>

      {briefMatch && (
        <BriefPanel match={briefMatch} onClose={() => setBriefMatch(null)} />
      )}
    </div>
  )
}
