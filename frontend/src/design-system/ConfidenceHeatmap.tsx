import { cn } from '@/lib/utils'
import { getConfidenceToken } from './tokens'

// ─── Confidence Bar ───────────────────────────────────────────────────────────
interface ConfidenceBarProps {
  score: number
  showLabel?: boolean
  showPercent?: boolean
  size?: 'xs' | 'sm' | 'md' | 'lg'
  animated?: boolean
  className?: string
}

export function ConfidenceBar({
  score,
  showLabel = false,
  showPercent = true,
  size = 'sm',
  animated = true,
  className,
}: ConfidenceBarProps) {
  const token = getConfidenceToken(score)
  const pct = Math.round(score * 100)

  const heights = { xs: 'h-1', sm: 'h-1.5', md: 'h-2', lg: 'h-3' }

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      {(showLabel || showPercent) && (
        <div className="flex items-center justify-between gap-2">
          {showLabel && (
            <span className="type-caption text-[var(--text-3)] capitalize">{token.label}</span>
          )}
          {showPercent && (
            <span
              className="type-caption tabular-nums font-semibold"
              style={{ color: token.color }}
            >
              {pct}%
            </span>
          )}
        </div>
      )}
      <div className={cn('conf-bar-track w-full', heights[size])}>
        <div
          className={cn(
            'conf-bar-fill',
            `conf-${token.css}`,
            animated && 'animate-fill'
          )}
          style={
            {
              width: `${pct}%`,
              '--fill-target': `${pct}%`,
            } as React.CSSProperties
          }
        />
      </div>
    </div>
  )
}

// ─── Confidence Ring ─────────────────────────────────────────────────────────
interface ConfidenceRingProps {
  score: number
  size?: number
  strokeWidth?: number
  showPercent?: boolean
  className?: string
}

export function ConfidenceRing({
  score,
  size = 48,
  strokeWidth = 4,
  showPercent = true,
  className,
}: ConfidenceRingProps) {
  const token = getConfidenceToken(score)
  const pct = Math.round(score * 100)
  const r = (size - strokeWidth) / 2
  const c = 2 * Math.PI * r
  const dash = (pct / 100) * c

  return (
    <div className={cn('relative inline-flex items-center justify-center', className)}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--border)"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={token.color}
          strokeWidth={strokeWidth}
          strokeDasharray={`${dash} ${c}`}
          strokeLinecap="round"
          style={{
            filter: `drop-shadow(0 0 4px ${token.glow})`,
            transition: 'stroke-dasharray 0.6s cubic-bezier(0.34,1,0.64,1)',
          }}
        />
      </svg>
      {showPercent && (
        <span
          className="absolute inset-0 flex items-center justify-center text-[10px] font-bold tabular-nums"
          style={{ color: token.color }}
        >
          {pct}%
        </span>
      )}
    </div>
  )
}

// ─── Confidence Badge ─────────────────────────────────────────────────────────
interface ConfidenceBadgeProps {
  score: number
  variant?: 'pill' | 'dot' | 'label'
  className?: string
}

export function ConfidenceBadge({ score, variant = 'pill', className }: ConfidenceBadgeProps) {
  const token = getConfidenceToken(score)
  const pct = Math.round(score * 100)

  if (variant === 'dot') {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1.5 text-xs font-medium tabular-nums',
          className
        )}
      >
        <span
          className="h-2 w-2 rounded-full flex-shrink-0"
          style={{ backgroundColor: token.color, boxShadow: `0 0 6px ${token.glow}` }}
        />
        <span style={{ color: token.color }}>{pct}%</span>
      </span>
    )
  }

  if (variant === 'label') {
    return (
      <span
        className={cn('text-xs font-semibold capitalize tabular-nums', className)}
        style={{ color: token.color }}
      >
        {token.label} · {pct}%
      </span>
    )
  }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold tabular-nums',
        className
      )}
      style={{
        backgroundColor: token.bg,
        color: token.color,
        boxShadow: `0 0 0 1px ${token.glow}`,
      }}
    >
      {pct}%
    </span>
  )
}

// ─── Confidence Heatmap Strip ─────────────────────────────────────────────────
interface HeatmapStripProps {
  score: number
  showBands?: boolean
  className?: string
}

const BANDS = [
  { min: 0,    max: 0.59, label: 'Critical', color: '#ef4444' },
  { min: 0.60, max: 0.69, label: 'Low',      color: '#f97316' },
  { min: 0.70, max: 0.79, label: 'Medium',   color: '#f59e0b' },
  { min: 0.80, max: 0.89, label: 'Good',     color: '#84cc16' },
  { min: 0.90, max: 0.94, label: 'High',     color: '#10b981' },
  { min: 0.95, max: 1.00, label: 'Perfect',  color: '#06d6a0' },
]

export function HeatmapStrip({ score, showBands = false, className }: HeatmapStripProps) {
  const pct = Math.round(score * 100)

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <div className="relative h-3 w-full rounded-full overflow-hidden">
        <div
          className="absolute inset-0 rounded-full"
          style={{
            background:
              'linear-gradient(90deg, #ef4444 0%, #f97316 20%, #f59e0b 40%, #84cc16 60%, #10b981 80%, #06d6a0 100%)',
          }}
        />
        <div
          className="absolute inset-y-0 right-0 rounded-full bg-[var(--surface)] opacity-70"
          style={{ left: `${pct}%` }}
        />
        <div
          className="absolute top-1/2 -translate-y-1/2 w-0.5 h-5 bg-white rounded-full shadow-md"
          style={{ left: `${pct}%`, transform: 'translate(-50%, -50%)' }}
        />
      </div>

      {showBands && (
        <div className="flex justify-between">
          {BANDS.map((band) => (
            <div key={band.label} className="flex flex-col items-center gap-0.5">
              <div className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: band.color }} />
              <span className="text-[9px] text-[var(--text-4)]">{band.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Compound Confidence component ───────────────────────────────────────────
interface ConfidenceDisplayProps {
  score: number
  variant?: 'bar' | 'ring' | 'badge' | 'strip'
  label?: string
  size?: 'xs' | 'sm' | 'md' | 'lg'
  className?: string
}

export function ConfidenceDisplay({
  score,
  variant = 'bar',
  label,
  size = 'sm',
  className,
}: ConfidenceDisplayProps) {
  if (variant === 'ring') return <ConfidenceRing score={score} className={className} />
  if (variant === 'badge') return <ConfidenceBadge score={score} className={className} />
  if (variant === 'strip') return <HeatmapStrip score={score} className={className} />

  return (
    <ConfidenceBar
      score={score}
      size={size}
      showLabel={!!label}
      showPercent
      className={className}
    />
  )
}
