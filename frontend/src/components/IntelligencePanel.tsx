import type { Turn } from '../types'
import { AGENTS, AGENT_ORDER, deriveSources } from '../lib/agents'
import AgentTraceRow, { type AgentState } from './AgentTraceRow'
import SourcesList from './SourcesList'

interface Props {
  turn: Turn | null
}

function formatLatency(ms: number): string {
  return `${(ms / 1000).toFixed(1)}s`
}

export default function IntelligencePanel({ turn }: Props) {
  const status = turn?.status ?? 'idle'
  const working = status === 'pending'

  // Which agents to render, and in what state.
  //  - idle / pending: show all three (we don't yet know the routing)
  //  - done / error:   show only the agents that actually ran
  const agentsToShow =
    status === 'done' || status === 'error' ? turn!.agentsUsed : AGENT_ORDER

  function stateFor(): AgentState {
    if (working) return 'working'
    if (status === 'done') return 'ok'
    if (status === 'error') return 'error'
    return 'idle'
  }

  const sources =
    status === 'done' ? deriveSources(turn!.agentsUsed) : []

  return (
    <aside className="intel-panel" aria-label="Agent intelligence trace">
      <div className="intel-panel__inner">
        <header className="intel-header">
          <h2 className="intel-header__title">Intelligence</h2>
          <span className={`intel-header__pill intel-header__pill--${status}`}>
            {status === 'idle' && 'IDLE'}
            {status === 'pending' && 'LIVE'}
            {status === 'done' && 'DONE'}
            {status === 'error' && 'ERROR'}
          </span>
        </header>

        <p className="intel-subtitle">
          {status === 'idle' &&
            'Agents on standby. Ask a question to dispatch the desk.'}
          {status === 'pending' &&
            'Classifying intent and dispatching specialist agents in parallel.'}
          {status === 'done' &&
            `${turn!.agentsUsed.length} agent${
              turn!.agentsUsed.length === 1 ? '' : 's'
            } contributed to this briefing.`}
          {status === 'error' &&
            'The dispatch failed before agents could report back.'}
        </p>

        <div className="latency">
          <span className="latency__label">RESPONSE TIME</span>
          <span className="latency__value">
            {status === 'done' && turn!.latencyMs != null
              ? formatLatency(turn!.latencyMs)
              : status === 'pending'
                ? 'ANALYSING…'
                : '—.—s'}
          </span>
        </div>

        <h3 className="panel-heading">Agent trace</h3>
        <ul className="agent-trace">
          {agentsToShow.length === 0 ? (
            <li className="agent-trace__empty">No agents reported.</li>
          ) : (
            agentsToShow.map((id) => (
              <AgentTraceRow key={id} agent={AGENTS[id]} state={stateFor()} />
            ))
          )}
        </ul>

        <SourcesList sources={sources} />
      </div>
    </aside>
  )
}
