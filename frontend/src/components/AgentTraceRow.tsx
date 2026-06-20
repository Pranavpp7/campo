import type { AgentMeta } from '../lib/agents'

export type AgentState = 'idle' | 'working' | 'ok' | 'error'

interface Props {
  agent: AgentMeta
  state: AgentState
}

const STATE_LABEL: Record<AgentState, string> = {
  idle: 'STANDBY',
  working: 'WORKING',
  ok: 'COMPLETE',
  error: 'FAILED',
}

export default function AgentTraceRow({ agent, state }: Props) {
  return (
    <li className={`agent-row agent-row--${state}`}>
      <span className="agent-row__dot" aria-hidden="true" />
      <div className="agent-row__body">
        <div className="agent-row__head">
          <span className="agent-row__name">{agent.name}</span>
          <span className="agent-row__category">{agent.category}</span>
        </div>
        <p className="agent-row__role">{agent.role}</p>
      </div>
      <span className="agent-row__status">{STATE_LABEL[state]}</span>
    </li>
  )
}
