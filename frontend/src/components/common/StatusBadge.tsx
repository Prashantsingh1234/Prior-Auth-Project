import { cn } from '@/lib/utils'

type CaseStatus =
  | 'SUBMITTED' | 'UNDER_REVIEW' | 'PENDING_INFO'
  | 'APPROVED' | 'DENIED' | 'ESCALATED' | 'WITHDRAWN'

type Priority = 'ROUTINE' | 'URGENT' | 'EMERGENT'
type Recommendation = 'APPROVE' | 'DENY' | 'REQUEST_INFO' | 'ESCALATE'

const STATUS_CONFIG: Record<CaseStatus, { label: string; className: string }> = {
  SUBMITTED:    { label: 'Submitted',    className: 'bg-sky-500/15 text-sky-400 border-sky-500/25' },
  UNDER_REVIEW: { label: 'Under Review', className: 'bg-amber-500/15 text-amber-400 border-amber-500/25' },
  PENDING_INFO: { label: 'Pending Info', className: 'bg-orange-500/15 text-orange-400 border-orange-500/25' },
  APPROVED:     { label: 'Approved',     className: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25' },
  DENIED:       { label: 'Denied',       className: 'bg-red-500/15 text-red-400 border-red-500/25' },
  ESCALATED:    { label: 'Escalated',    className: 'bg-violet-500/15 text-violet-400 border-violet-500/25' },
  WITHDRAWN:    { label: 'Withdrawn',    className: 'bg-slate-500/15 text-slate-400 border-slate-500/25' },
}

const PRIORITY_CONFIG: Record<Priority, { label: string; className: string; dot: string }> = {
  ROUTINE:  { label: 'Routine',  className: 'bg-slate-500/10 text-slate-400 border-slate-500/20',   dot: 'bg-slate-400' },
  URGENT:   { label: 'Urgent',   className: 'bg-amber-500/15 text-amber-400 border-amber-500/25',   dot: 'bg-amber-400' },
  EMERGENT: { label: 'Emergent', className: 'bg-red-500/15 text-red-400 border-red-500/25',         dot: 'bg-red-400 animate-pulse' },
}

const REC_CONFIG: Record<Recommendation, { label: string; className: string }> = {
  APPROVE:      { label: 'Approve',       className: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25' },
  DENY:         { label: 'Deny',          className: 'bg-red-500/15 text-red-400 border-red-500/25' },
  REQUEST_INFO: { label: 'Request Info',  className: 'bg-amber-500/15 text-amber-400 border-amber-500/25' },
  ESCALATE:     { label: 'Escalate',      className: 'bg-violet-500/15 text-violet-400 border-violet-500/25' },
}

interface StatusBadgeProps {
  status: CaseStatus
  size?: 'sm' | 'md'
}

interface PriorityBadgeProps {
  priority: Priority
  size?: 'sm' | 'md'
}

interface RecommendationBadgeProps {
  recommendation: Recommendation
  size?: 'sm' | 'md'
}

const BASE = 'inline-flex items-center gap-1.5 rounded-full border font-medium'
const SIZE = { sm: 'px-2 py-0.5 text-xs', md: 'px-2.5 py-1 text-xs' }

export function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.SUBMITTED
  return <span className={cn(BASE, SIZE[size], cfg.className)}>{cfg.label}</span>
}

export function PriorityBadge({ priority, size = 'sm' }: PriorityBadgeProps) {
  const cfg = PRIORITY_CONFIG[priority] ?? PRIORITY_CONFIG.ROUTINE
  return (
    <span className={cn(BASE, SIZE[size], cfg.className)}>
      <span className={cn('w-1.5 h-1.5 rounded-full', cfg.dot)} />
      {cfg.label}
    </span>
  )
}

export function RecommendationBadge({ recommendation, size = 'sm' }: RecommendationBadgeProps) {
  const cfg = REC_CONFIG[recommendation] ?? REC_CONFIG.APPROVE
  return <span className={cn(BASE, SIZE[size], cfg.className)}>{cfg.label}</span>
}