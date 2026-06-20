interface Props {
  sources: string[]
}

export default function SourcesList({ sources }: Props) {
  if (sources.length === 0) return null

  return (
    <div className="sources">
      <h3 className="panel-heading">Sources</h3>
      <ul className="sources__list">
        {sources.map((source) => (
          <li key={source} className="sources__item">
            <span className="sources__bullet" aria-hidden="true">
              ↳
            </span>
            <span className="sources__name">{source}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
