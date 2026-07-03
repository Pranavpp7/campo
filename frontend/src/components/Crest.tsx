import { useState } from 'react'

interface Props {
  name: string | null | undefined
  crest: string | null | undefined
  /** Pixel diameter. */
  size?: number
}

/** Up to 3 uppercase initials drawn from the team name. */
function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return '?'
  if (words.length === 1) return words[0].slice(0, 3).toUpperCase()
  return words
    .slice(0, 3)
    .map((w) => w[0])
    .join('')
    .toUpperCase()
}

/** Deterministic accent so each fallback badge keeps a stable colour. */
function hueFor(name: string): number {
  let h = 0
  for (let i = 0; i < name.length; i++) {
    h = (h * 31 + name.charCodeAt(i)) % 360
  }
  return h
}

/**
 * Team crest as an <img>, with a graceful fallback to an initials badge when
 * there is no URL or the image fails to load.
 */
export default function Crest({ name, crest, size = 28 }: Props) {
  // Track WHICH url failed, not just that one did — so a re-render with a
  // different crest url gets a fresh chance instead of a stuck fallback.
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  const label = name || 'Unknown'
  const showFallback = !crest || failedSrc === crest

  if (showFallback) {
    const hue = hueFor(label)
    return (
      <span
        className="crest crest--fallback"
        style={{
          width: size,
          height: size,
          fontSize: Math.max(9, size * 0.36),
          color: `hsl(${hue} 70% 78%)`,
          background: `hsl(${hue} 45% 22%)`,
          borderColor: `hsl(${hue} 45% 34%)`,
        }}
        aria-label={label}
        title={label}
      >
        {initials(label)}
      </span>
    )
  }

  return (
    <img
      className="crest"
      src={crest!}
      alt={label}
      title={label}
      width={size}
      height={size}
      loading="lazy"
      onError={() => setFailedSrc(crest!)}
    />
  )
}
