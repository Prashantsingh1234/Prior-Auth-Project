import { type HTMLAttributes, forwardRef } from 'react'
import { cn } from '@/lib/utils'
import type { StatusKey } from './tokens'

// ─── Base GlassCard ───────────────────────────────────────────────────────────
interface GlassCardProps extends HTMLAttributes<HTMLDivElement> {
  hover?: boolean
  animated?: boolean
}

export const GlassCard = forwardRef<HTMLDivElement, GlassCardProps>(
  ({ hover, animated, className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'glass rounded-2xl p-4',
        hover && 'card-hover',
        animated && 'border-animated',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
)
GlassCard.displayName = 'GlassCard'

// ─── AI card (gradient top accent + purple glow) ──────────────────────────────
interface AICardProps extends HTMLAttributes<HTMLDivElement> {
  glow?: boolean
}

export const AICard = forwardRef<HTMLDivElement, AICardProps>(
  ({ glow, className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('card-ai rounded-2xl p-4', glow && 'shadow-glow-ai', className)}
      {...props}
    >
      {children}
    </div>
  )
)
AICard.displayName = 'AICard'

// ─── Evidence card ────────────────────────────────────────────────────────────
export const EvidenceCard = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('card-evidence rounded-xl p-3', className)}
      {...props}
    >
      {children}
    </div>
  )
)
EvidenceCard.displayName = 'EvidenceCard'

// ─── Status-tinted card ───────────────────────────────────────────────────────
interface StatusCardProps extends HTMLAttributes<HTMLDivElement> {
  status: StatusKey
}

const STATUS_CARD_MAP: Record<StatusKey, string> = {
  approve:  'card-approve',
  deny:     'card-deny',
  pend:     'card-pend',
  review:   'card-review',
  escalate: 'card-escalate',
}

export const StatusCard = forwardRef<HTMLDivElement, StatusCardProps>(
  ({ status, className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(STATUS_CARD_MAP[status], 'rounded-2xl p-4', className)}
      {...props}
    >
      {children}
    </div>
  )
)
StatusCard.displayName = 'StatusCard'

// ─── Panel (full-bleed glass section) ────────────────────────────────────────
export const Panel = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('panel', className)}
      {...props}
    >
      {children}
    </div>
  )
)
Panel.displayName = 'Panel'

// ─── Metric card ──────────────────────────────────────────────────────────────
interface MetricCardGlassProps extends HTMLAttributes<HTMLDivElement> {
  title: string
  value: string | number
  delta?: string
  deltaPositive?: boolean
  icon?: React.ReactNode
  loading?: boolean
}

export function MetricCardGlass({
  title,
  value,
  delta,
  deltaPositive,
  icon,
  loading,
  className,
  ...props
}: MetricCardGlassProps) {
  if (loading) {
    return (
      <div className={cn('glass rounded-2xl p-4 flex flex-col gap-3', className)} {...props}>
        <div className="skeleton h-3 w-20 rounded" />
        <div className="skeleton h-8 w-28 rounded" />
        {delta && <div className="skeleton h-3 w-16 rounded" />}
      </div>
    )
  }

  return (
    <div className={cn('glass card-hover rounded-2xl p-4 flex flex-col gap-1', className)} {...props}>
      <div className="flex items-start justify-between gap-2">
        <span className="type-label text-[var(--text-3)]">{title}</span>
        {icon && (
          <span className="text-[var(--text-4)] flex-shrink-0">{icon}</span>
        )}
      </div>
      <div className="type-metric mt-1">{value}</div>
      {delta && (
        <span
          className={cn(
            'text-xs font-medium tabular-nums',
            deltaPositive ? 'text-approve' : 'text-deny'
          )}
        >
          {deltaPositive ? '↑' : '↓'} {delta}
        </span>
      )}
    </div>
  )
}

// ─── Section card (card + header + content) ───────────────────────────────────
interface SectionCardProps extends HTMLAttributes<HTMLDivElement> {
  title?: string
  description?: string
  actions?: React.ReactNode
  noPadding?: boolean
}

export const SectionCard = forwardRef<HTMLDivElement, SectionCardProps>(
  ({ title, description, actions, noPadding, className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('glass rounded-2xl', !noPadding && 'p-4', className)}
      {...props}
    >
      {(title || description || actions) && (
        <div className={cn('flex items-start justify-between gap-3', !noPadding ? 'mb-4' : 'px-4 pt-4 mb-4')}>
          <div className="flex flex-col gap-0.5">
            {title && <h3 className="type-h4">{title}</h3>}
            {description && <p className="type-body-sm text-[var(--text-3)]">{description}</p>}
          </div>
          {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
        </div>
      )}
      {children}
    </div>
  )
)
SectionCard.displayName = 'SectionCard'
