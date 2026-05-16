import { clsx } from 'clsx'
import type { CaseStatus, CasePriority, CriterionStatus, DecisionOutcome } from '@/api/types'

// ─── Case Status Badge ────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<CaseStatus, { label: string; className: string }> = {
  SUBMITTED:             { label: 'Submitted',             className: 'bg-slate-100 text-slate-700 ring-slate-200' },
  PROCESSING:            { label: 'Processing',            className: 'bg-blue-100 text-blue-700 ring-blue-200 animate-pulse-slow' },
  PENDING_CLARIFICATION: { label: 'Pending Clarification', className: 'bg-amber-100 text-amber-700 ring-amber-200' },
  UNDER_REVIEW:          { label: 'Under Review',          className: 'bg-violet-100 text-violet-700 ring-violet-200' },
  APPROVED:              { label: 'Approved',              className: 'bg-green-100 text-green-700 ring-green-200' },
  DENIED:                { label: 'Denied',                className: 'bg-red-100 text-red-700 ring-red-200' },
  PENDED:                { label: 'Pended',                className: 'bg-orange-100 text-orange-700 ring-orange-200' },
  ESCALATED:             { label: 'Escalated',             className: 'bg-purple-100 text-purple-700 ring-purple-200' },
  CANCELLED:             { label: 'Cancelled',             className: 'bg-gray-100 text-gray-500 ring-gray-200' },
}

interface StatusBadgeProps {
  status: CaseStatus
  size?: 'sm' | 'md'
}

export function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const cfg = STATUS_CONFIG[status]
  return (
    <span
      className={clsx(
        'inline-flex items-center font-medium rounded-full ring-1',
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs',
        cfg.className,
      )}
    >
      {cfg.label}
    </span>
  )
}

// ─── Priority Badge ───────────────────────────────────────────────────────────

const PRIORITY_CONFIG: Record<CasePriority, { label: string; className: string; dot: string }> = {
  ROUTINE:  { label: 'Routine',  className: 'bg-slate-100 text-slate-600', dot: 'bg-slate-400' },
  URGENT:   { label: 'Urgent',   className: 'bg-orange-100 text-orange-700', dot: 'bg-orange-500' },
  EMERGENT: { label: 'Emergent', className: 'bg-red-100 text-red-700', dot: 'bg-red-500 animate-pulse' },
}

export function PriorityBadge({ priority }: { priority: CasePriority }) {
  const cfg = PRIORITY_CONFIG[priority]
  return (
    <span className={clsx('inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-full', cfg.className)}>
      <span className={clsx('w-1.5 h-1.5 rounded-full', cfg.dot)} />
      {cfg.label}
    </span>
  )
}

// ─── AI Recommendation Badge ──────────────────────────────────────────────────

const DECISION_CONFIG: Record<DecisionOutcome, { label: string; className: string }> = {
  APPROVE: { label: 'Approve',  className: 'bg-green-100 text-green-700 ring-green-200' },
  DENY:    { label: 'Deny',     className: 'bg-red-100 text-red-700 ring-red-200' },
  PEND:    { label: 'Pend',     className: 'bg-amber-100 text-amber-700 ring-amber-200' },
}

export function RecommendationBadge({ recommendation }: { recommendation: DecisionOutcome }) {
  const cfg = DECISION_CONFIG[recommendation]
  return (
    <span className={clsx('inline-flex items-center px-2.5 py-1 text-xs font-semibold rounded-full ring-1', cfg.className)}>
      AI: {cfg.label}
    </span>
  )
}

// ─── Criterion Status Badge ───────────────────────────────────────────────────

const CRITERION_CONFIG: Record<CriterionStatus, { label: string; icon: string; className: string }> = {
  PASS:                 { label: 'Pass',                 icon: '✓', className: 'text-green-700 bg-green-50' },
  FAIL:                 { label: 'Fail',                 icon: '✗', className: 'text-red-700 bg-red-50' },
  INSUFFICIENT_EVIDENCE:{ label: 'Insufficient Evidence',icon: '?', className: 'text-amber-700 bg-amber-50' },
  NOT_APPLICABLE:       { label: 'N/A',                  icon: '—', className: 'text-gray-500 bg-gray-50' },
}

export function CriterionBadge({ status }: { status: CriterionStatus }) {
  const cfg = CRITERION_CONFIG[status]
  return (
    <span className={clsx('inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded', cfg.className)}>
      <span className="font-bold">{cfg.icon}</span>
      {cfg.label}
    </span>
  )
}
