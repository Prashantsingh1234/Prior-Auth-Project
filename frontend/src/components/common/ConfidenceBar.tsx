import { cn, getConfidenceLevel, formatConfidence } from '@/lib/utils'

interface ConfidenceBarProps {
  value: number
  showLabel?: boolean
  showPercent?: boolean
  size?: 'sm' | 'md' | 'lg'
  variant?: 'bar' | 'ring'
  className?: string
}

const TRACK_H = { sm: 'h-1', md: 'h-1.5', lg: 'h-2' }
const FILL_COLOR = {
  high:   'bg-gradient-to-r from-emerald-500 to-emerald-400',
  medium: 'bg-gradient-to-r from-amber-500 to-amber-400',
  low:    'bg-gradient-to-r from-red-500 to-red-400',
}
const LABEL_COLOR = { high: 'text-emerald-400', medium: 'text-amber-400', low: 'text-red-400' }

export function ConfidenceBar({
  value,
  showLabel = false,
  showPercent = true,
  size = 'md',
  variant = 'bar',
  className,
}: ConfidenceBarProps) {
  const level = getConfidenceLevel(value)
  const pct = Math.round(value * 100)

  if (variant === 'ring') {
    const r = 20
    const circ = 2 * Math.PI * r
    const dash = (pct / 100) * circ
    const ringColor = { high: '#10b981', medium: '#f59e0b', low: '#ef4444' }[level]

    return (
      <div className={cn('flex items-center gap-2', className)}>
        <div className="relative w-12 h-12 flex-shrink-0">
          <svg className="w-12 h-12 -rotate-90" viewBox="0 0 48 48">
            <circle cx="24" cy="24" r={r} fill="none" strokeWidth="4" className="stroke-[var(--border)]" />
            <circle
              cx="24" cy="24" r={r}
              fill="none" strokeWidth="4"
              stroke={ringColor}
              strokeLinecap="round"
              strokeDasharray={`${dash} ${circ}`}
              style={{ transition: 'stroke-dasharray 0.6s ease' }}
            />
          </svg>
          <span className={cn('absolute inset-0 flex items-center justify-center text-xs font-bold', LABEL_COLOR[level])}>
            {pct}%
          </span>
        </div>
        {showLabel && (
          <div>
            <p className={cn('text-xs font-semibold capitalize', LABEL_COLOR[level])}>{level}</p>
            <p className="text-xs text-[var(--text-3)]">Confidence</p>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className={cn('flex-1 rounded-full bg-[var(--elevated)]', TRACK_H[size])}>
        <div
          className={cn('h-full rounded-full transition-all duration-700', FILL_COLOR[level])}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showPercent && (
        <span className={cn('text-xs font-semibold tabular-nums w-9 text-right flex-shrink-0', LABEL_COLOR[level])}>
          {formatConfidence(value)}
        </span>
      )}
      {showLabel && (
        <span className={cn('text-xs capitalize', LABEL_COLOR[level])}>{level}</span>
      )}
    </div>
  )
}