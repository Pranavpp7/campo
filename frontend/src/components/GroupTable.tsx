import type { GroupStanding } from '../types'
import Crest from './Crest'

interface Props {
  group: GroupStanding
}

function gd(n: number | null): string {
  if (n == null) return '–'
  return n > 0 ? `+${n}` : `${n}`
}

function num(n: number | null): string | number {
  return n ?? '–'
}

/**
 * Compact group standings table. Top 2 rows advance outright; the 3rd row is
 * marked tentatively — in the 2026 format the 8 best third-placed teams
 * across the 12 groups also advance.
 */
export default function GroupTable({ group }: Props) {
  return (
    <div className="gtable" role="group" aria-label={group.group || 'Group'}>
      <div className="gtable__title">{group.group || 'Group'}</div>
      <table className="gtable__table">
        <thead>
          <tr>
            <th className="gtable__pos" title="Position">#</th>
            <th className="gtable__team">Team</th>
            <th title="Played">P</th>
            <th title="Won">W</th>
            <th title="Drawn">D</th>
            <th title="Lost">L</th>
            <th title="Goal difference">GD</th>
            <th className="gtable__pts" title="Points">Pts</th>
          </tr>
        </thead>
        <tbody>
          {group.table.map((row, i) => (
            <tr
              key={`${row.team?.name ?? 'team'}-${i}`}
              className={
                i < 2
                  ? 'gtable__row gtable__row--advance'
                  : i === 2
                    ? 'gtable__row gtable__row--third'
                    : 'gtable__row'
              }
            >
              <td className="gtable__pos">{row.position ?? i + 1}</td>
              <td className="gtable__team">
                <Crest name={row.team?.name} crest={row.team?.crest} size={20} />
                <span className="gtable__team-name">{row.team?.name || 'TBD'}</span>
              </td>
              <td>{num(row.played)}</td>
              <td>{num(row.won)}</td>
              <td>{num(row.draw)}</td>
              <td>{num(row.lost)}</td>
              <td className="gtable__gd">{gd(row.goal_difference)}</td>
              <td className="gtable__pts">{num(row.points)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
