import { cn } from '@/lib/utils'
import type { CaseStatus, CasePriority, AIRecommendation } from '@/types/case.types'
import { STATUS, type StatusKey } from './tokens'

// ─── Status Chip ─────────────────────────────────────────────────────────────
interface StatusChipProps {
  status: CaseStatus
  size?: 'xs' | 'sm' | 'md'
  dot?: boolean
  pulse?: boolean
  className?: string
}

const STATUS_MAP: Record<CaseStatus, StatusKey> = {
  PENDING_SUBMISSION: 'review',
  SUBMITTED:          'review',
  AI_PROCESSING:      'review',
  PENDING_REVIEW:     'pend',
  UNDER_REVIEW:       'pend',
  APPROVED:           'approve',
  DENIED:             'deny',
  PENDED:             'pend',
  ESCALATED:          'escalate',
  CLOSED:             'review',
}

const STATUS_LABEL: Record<CaseStatus, string> = {
  PENDING_SUBMISSION: 'Pending',
  SUBMITTED:          'Submitted',
  AI_PROCESSING:      'AI Processing',
  PENDING_REVIEW:     'Pending Review',
  UNDER_REVIEW:       'Under Review',
  APPROVED:           'Approved',
  DENIED:             'Denied',
  PENDED:             'Pended',
  ESCALATED:          'Escalated',
  CLOSED:             'Closed',
}

const ACTIVE_STATUSES: CaseStatus[] = ['AI_PROCESSING', 'UNDER_REVIEW']

export function StatusChip({ status, size = 'sm', dot = true, pulse, className }: StatusChipProps) {
  const key = STATUS_MAP[status] ?? 'review'
  const token = STATUS[key]
  const isActive = pulse ?? ACTIVE_STATUSES.includes(status)

  const sizes = {
    xs: 'px-1.5 py-0.5 text-[10px] gap-1',
    sm: 'px-2 py-0.5 text-xs gap-1.5',
    md: 'px-2.5 py-1 text-sm gap-1.5',
  }

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full font-medium leading-none',
        sizes[size],
        className
      )}
      style={{
        backgroundColor: token.surface,
        color: token.color,
        boxShadow: `0 0 0 1px ${token.border}`,
      }}
    >
      {dot && (
        <span
          className={cn('rounded-full flex-shrink-0', size === 'xs' ? 'h-1.5 w-1.5' : 'h-2 w-2')}
          style={{
            backgroundColor: token.color,
            boxShadow: isActive ? `0 0 6px ${token.glow}` : undefined,
            animation: isActive ? 'pulse 2s ease-in-out infinite' : undefined,
          }}
        />
      )}
      {STATUS_LABEL[status]}
    </span>
  )
}

// ─── Priority Chip ────────────────────────────────────────────────────────────
interface PriorityChipProps {
  priority: CasePriority
  size?: 'xs' | 'sm' | 'md'
  className?: string
}

const PRIORITY_CONFIG: Record<CasePriority, { label: string; color: string; bg: string; border: string; pulse?: boolean }> = {
  ROUTINE:   { label: 'Routine',   color: '#64748b', bg: 'rgba(100,116,139,0.1)', border: 'rgba(100,116,139,0.2)' },
  URGENT:    { label: 'Urgent',    color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.25)' },
  EMERGENT:  { label: 'Emergent',  color: '#ef4444', bg: 'rgba(239,68,68,0.1)',   border: 'rgba(239,68,68,0.25)', pulse: true },
}

export function PriorityChip({ priority, size = 'sm', className }: PriorityChipProps) {
  const cfg = PRIORITY_CONFIG[priority]

  const sizes = {
    xs: 'px-1.5 py-0.5 text-[10px] gap-1',
    sm: 'px-2 py-0.5 text-xs gap-1.5',
    md: 'px-2.5 py-1 text-sm gap-1.5',
  }

  return (
    <span
      className={cn('inline-flex items-center rounded-full font-medium leading-none', sizes[size], className)}
      style={{ backgroundColor: cfg.bg, color: cfg.color, boxShadow: `0 0 0 1px ${cfg.border}` }}
    >
      {cfg.pulse && (
        <span
          className={cn('rounded-full flex-shrink-0 animate-pulse-slow', size === 'xs' ? 'h-1.5 w-1.5' : 'h-2 w-2')}
          style={{ backgroundColor: cfg.color, boxShadow: `0 0 8px ${cfg.color}` }}
        />
      )}
      {cfg.label}
    </span>
  )
}

// ─── Decision Badge ───────────────────────────────────────────────────────────
interface DecisionBadgeProps {
  recommendation: AIRecommendation
  size?: 'sm' | 'md' | 'lg'
  variant?: 'default' | 'filled' | 'outline'
  className?: string
}

const DECISION_CONFIG: Record<AIRecommendation, { label: string; key: StatusKey; icon: string }> = {
  APPROVE:  { label: 'Approve',  key: 'approve',  icon: '✓' },
  DENY:     { label: 'Deny',     key: 'deny',     icon: '✕' },
  PEND:     { label: 'Pend',     key: 'pend',     icon: '⏸' },
  ESCALATE: { label: 'Escalate', key: 'escalate', icon: '↑' },
}

export function DecisionBadge({ recommendation, size = 'md', variant = 'default', className }: DecisionBadgeProps) {
  const cfg = DECISION_CONFIG[recommendation]
  const token = STATUS[cfg.key]

  const sizes = {
    sm: 'px-2 py-0.5 text-xs gap-1',
    md: 'px-3 py-1 text-sm gap-1.5',
    lg: 'px-4 py-1.5 text-base gap-2',
  }

  const styles: React.CSSProperties =
    variant === 'filled'
      ? { backgroundColor: token.color, color: '#fff' }
      : variant === 'outline'
      ? { backgroundColor: 'transparent', color: token.color, boxShadow: `0 0 0 1.5px ${token.color}` }
      : { backgroundColor: token.surface, color: token.color, boxShadow: `0 0 0 1px ${token.border}` }

  return (
    <span
      className={cn('inline-flex items-center rounded-lg font-semibold leading-none', sizes[size], className)}
      style={styles}
    >
      <span className="font-bold opacity-80">{cfg.icon}</span>
      {cfg.label}
    </span>
  )
}

// ─── Outcome Pill (terminal decision display) ─────────────────────────────────
interface OutcomePillProps {
  outcome: 'APPROVED' | 'DENIED' | 'PENDED' | 'ESCALATED'
  className?: string
}

export function OutcomePill({ outcome, className }: OutcomePillProps) {
  const map: Record<OutcomePillProps['outcome'], StatusKey> = {
    APPROVED:  'approve',
    DENIED:    'deny',
    PENDED:    'pend',
    ESCALATED: 'escalate',
  }
  const token = STATUS[map[outcome]]

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-bold uppercase tracking-wide',
        className
      )}
      style={{
        backgroundColor: token.surface,
        color: token.color,
        boxShadow: `0 0 0 1.5px ${token.border}, 0 0 12px ${token.glow}`,
      }}
    >
      {outcome}
    </span>
  )
}

// ─── AI Processing indicator ──────────────────────────────────────────────────
interface AIProcessingBadgeProps {
  stage?: string
  className?: string
}

export function AIProcessingBadge({ stage, className }: AIProcessingBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-medium',
        className
      )}
      style={{
        backgroundColor: 'rgba(139,92,246,0.1)',
        color: '#8b5cf6',
        boxShadow: '0 0 0 1px rgba(139,92,246,0.2)',
      }}
    >
      <span
        className="h-1.5 w-1.5 rounded-full bg-ai-400 animate-ping-slow"
        style={{ boxShadow: '0 0 6px rgba(139,92,246,0.6)' }}
      />
      {stage ?? 'AI Processing'}
    </span>
  )
}
