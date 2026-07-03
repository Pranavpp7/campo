import type { Match } from '../types'
import Crest from './Crest'

interface Props {
  match: Match
}

/** Local kickoff time, e.g. "18:00". Falls back to "TBD" on a bad date. */
function kickoff(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return 'TBD'
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
}

function StatusBadge({ match }: { match: Match }) {
  if (match.status === 'LIVE') {
    return (
      <span className="match-card__status match-card__status--live">
        <span className="match-card__live-dot" aria-hidden="true" />
        LIVE
      </span>
    )
  }
  if (match.status === 'FINISHED') {
    return <span className="match-card__status match-card__status--finished">FT</span>
  }
  // SCHEDULED → show kickoff time in gold.
  return (
    <span className="match-card__status match-card__status--scheduled">
      {match.utc_date ? kickoff(match.utc_date) : 'TBD'}
    </span>
  )
}

/** A single team row: crest + name on the left, its score on the right. */
function TeamLine({
  team,
  score,
  played,
  winner,
}: {
  team: Match['home']
  score: number | null
  played: boolean
  winner: boolean
}) {
  return (
    <div className={`match-card__team${winner ? ' match-card__team--winner' : ''}`}>
      <Crest name={team?.name} crest={team?.crest} size={30} />
      <span className="match-card__team-name">{team?.name || 'TBD'}</span>
      {played && <span className="match-card__score">{score ?? '–'}</span>}
    </div>
  )
}

export default function MatchCard({ match }: Props) {
  const played = match.status === 'LIVE' || match.status === 'FINISHED'
  const hs = match.home_score
  const as = match.away_score
  const homeWin = played && hs != null && as != null && hs > as
  const awayWin = played && hs != null && as != null && as > hs

  return (
    <article
      className="match-card"
      aria-label={`${match.home?.name ?? 'TBD'} vs ${match.away?.name ?? 'TBD'}`}
    >
      <header className="match-card__top">
        {match.group && <span className="match-card__group">{match.group}</span>}
        <StatusBadge match={match} />
      </header>

      <div className="match-card__teams">
        <TeamLine team={match.home} score={hs} played={played} winner={homeWin} />
        <TeamLine team={match.away} score={as} played={played} winner={awayWin} />
      </div>

      {match.venue && <footer className="match-card__venue">{match.venue}</footer>}
    </article>
  )
}
