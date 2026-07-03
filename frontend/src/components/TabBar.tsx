import type { ReactNode } from 'react'

export type TabId = 'today' | 'ask'

interface Props {
  active: TabId
  onChange: (tab: TabId) => void
}

/* Inline SVGs (currentColor) so the icons follow the tab's active colour. */
const BallIcon = (
  <svg
    viewBox="0 0 24 24"
    width="20"
    height="20"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.6"
    strokeLinecap="round"
    aria-hidden="true"
  >
    <circle cx="12" cy="12" r="8.6" />
    <path
      d="M12 8.4l3.4 2.5-1.3 4h-4.2l-1.3-4z"
      fill="currentColor"
      stroke="none"
    />
    <path d="M12 8.4V3.9M15.4 10.9l4.2-1.3M14.1 14.9l2.6 3.6M9.9 14.9l-2.6 3.6M8.6 10.9L4.4 9.6" />
  </svg>
)

const ChatIcon = (
  <svg
    viewBox="0 0 24 24"
    width="20"
    height="20"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v7a2.5 2.5 0 0 1-2.5 2.5H9.2L5 19.4a.6.6 0 0 1-1-.5z" />
  </svg>
)

const TABS: Array<{ id: TabId; icon: ReactNode; label: string }> = [
  { id: 'today', icon: BallIcon, label: 'Today' },
  { id: 'ask', icon: ChatIcon, label: 'Ask Campo' },
]

/** Mobile-first bottom navigation; works just as well on desktop. */
export default function TabBar({ active, onChange }: Props) {
  return (
    <nav className="tabbar" aria-label="Primary">
      {TABS.map((tab) => {
        const isActive = tab.id === active
        return (
          <button
            key={tab.id}
            type="button"
            className={`tabbar__tab${isActive ? ' tabbar__tab--active' : ''}`}
            aria-current={isActive ? 'page' : undefined}
            onClick={() => onChange(tab.id)}
          >
            <span className="tabbar__icon" aria-hidden="true">{tab.icon}</span>
            <span className="tabbar__label">{tab.label}</span>
          </button>
        )
      })}
    </nav>
  )
}
