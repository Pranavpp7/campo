import type { AgentId } from '../types'

export interface AgentMeta {
  id: AgentId
  /** Short display name used in the UI. */
  name: string
  /** Parenthetical category, e.g. "Match Intelligence". */
  category: string
  /** One-line description of the agent's remit. */
  role: string
  /** Data sources this agent draws on. */
  sources: string[]
}

/** Canonical render order — Scout, Logistics, LocalPulse. */
export const AGENT_ORDER: AgentId[] = ['scout', 'logistics', 'localpulse']

export const AGENTS: Record<AgentId, AgentMeta> = {
  scout: {
    id: 'scout',
    name: 'Scout',
    category: 'Match Intelligence',
    role: 'Form, squads, injuries, head-to-head and tactical read.',
    sources: ['football-data.org', 'ESPN', 'Web search'],
  },
  logistics: {
    id: 'logistics',
    name: 'Logistics',
    category: 'Travel Planning',
    role: 'Routes to matches, venue weather and multi-match itineraries.',
    sources: ['football-data.org', 'Open-Meteo', 'Web search'],
  },
  localpulse: {
    id: 'localpulse',
    name: 'LocalPulse',
    category: 'Business Intelligence',
    role: 'Demand, weather-aware ops and local rules for venues nearby.',
    sources: ['football-data.org', 'Open-Meteo', 'Web search'],
  },
}

export function isAgentId(value: string): value is AgentId {
  return value === 'scout' || value === 'logistics' || value === 'localpulse'
}

/**
 * Union of the data sources for the agents that ran, de-duplicated and kept in
 * a stable, readable order.
 */
export function deriveSources(agents: AgentId[]): string[] {
  const seen = new Set<string>()
  const ordered: string[] = []
  for (const id of AGENT_ORDER) {
    if (!agents.includes(id)) continue
    for (const source of AGENTS[id].sources) {
      if (seen.has(source)) continue
      seen.add(source)
      ordered.push(source)
    }
  }
  return ordered
}
