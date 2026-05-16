import { clsx } from 'clsx'

interface ConfidenceBarProps {
  score: number       // 0.0 – 1.0
  showLabel?: boolean
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

function confidenceColor(score: number): string {
  if (score >= 0.85) return 'bg-green-500'
  if (score >= 0.65) return 'bg-amber-400'
  return 'bg-red-500'
}

function confidenceLabel(score: number): string {
  if (score >= 0.85) return 'High'
  if (score >= 0.65) return 'Medium'
  return 'Low'
}

function confidenceTextColor(score: number): string {
  if (score >= 0.85) return 'text-green-700'
  if (score >= 0.65) return 'text-amber-700'
  return 'text-red-700'
}

export function ConfidenceBar({
  score,
  showLabel = true,
  size = 'md',
  className,
}: ConfidenceBarProps) {
  const pct   = Math.round(score * 100)
  const color = confidenceColor(score)
  const label = confidenceLabel(score)
  const textColor = confidenceTextColor(score)

  const barHeight = size === 'sm' ? 'h-1' : size === 'lg' ? 'h-3' : 'h-2'

  return (
    <div className={clsx('flex items-center gap-2', className)}>
      <div className={clsx('flex-1 bg-slate-100 rounded-full overflow-hidden', barHeight)}>
        <div
          className={clsx('h-full rounded-full transition-all duration-500', color)}
          style={{ width: `${pct}%` }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Confidence: ${pct}%`}
        />
      </div>
      {showLabel && (
        <span className={clsx('text-xs font-semibold tabular-nums', textColor)}>
          {pct}%
        </span>
      )}
      {showLabel && size !== 'sm' && (
        <span className={clsx('text-xs font-medium', textColor)}>
          {label}
        </span>
      )}
    </div>
  )
}

// ─── Circular confidence indicator ───────────────────────────────────────────

export function ConfidenceRing({ score, size = 48 }: { score: number; size?: number }) {
  const pct        = score * 100
  const radius     = (size - 8) / 2
  const circumference = 2 * Math.PI * radius
  const dashOffset = circumference - (pct / 100) * circumference
  const color = score >= 0.85 ? '#16a34a' : score >= 0.65 ? '#d97706' : '#dc2626'

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="#e2e8f0" strokeWidth={4}
        />
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={color} strokeWidth={4}
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.5s ease' }}
        />
      </svg>
      <span
        className="absolute text-xs font-bold tabular-nums"
        style={{ color }}
      >
        {Math.round(pct)}%
      </span>
    </div>
  )
}
