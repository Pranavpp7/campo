export type TabId = 'today' | 'ask'

interface Props {
  active: TabId
  onChange: (tab: TabId) => void
}

const TABS: Array<{ id: TabId; icon: string; label: string }> = [
  { id: 'today', icon: '⚽', label: 'Today' },
  { id: 'ask', icon: '💬', label: 'Ask Campo' },
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
