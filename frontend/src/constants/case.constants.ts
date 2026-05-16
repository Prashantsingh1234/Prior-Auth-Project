import type { CaseStatus, CasePriority, AIRecommendation } from '@/types'

export const CASE_STATUS_LABEL: Record<CaseStatus, string> = {
  SUBMITTED:    'Submitted',
  UNDER_REVIEW: 'Under Review',
  PENDING_INFO: 'Pending Info',
  APPROVED:     'Approved',
  DENIED:       'Denied',
  ESCALATED:    'Escalated',
  WITHDRAWN:    'Withdrawn',
}

export const CASE_STATUS_COLOR: Record<CaseStatus, { bg: string; text: string; border: string }> = {
  SUBMITTED:    { bg: 'bg-sky-500/15',     text: 'text-sky-400',     border: 'border-sky-500/25' },
  UNDER_REVIEW: { bg: 'bg-amber-500/15',   text: 'text-amber-400',   border: 'border-amber-500/25' },
  PENDING_INFO: { bg: 'bg-orange-500/15',  text: 'text-orange-400',  border: 'border-orange-500/25' },
  APPROVED:     { bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/25' },
  DENIED:       { bg: 'bg-red-500/15',     text: 'text-red-400',     border: 'border-red-500/25' },
  ESCALATED:    { bg: 'bg-violet-500/15',  text: 'text-violet-400',  border: 'border-violet-500/25' },
  WITHDRAWN:    { bg: 'bg-slate-500/15',   text: 'text-slate-400',   border: 'border-slate-500/25' },
}

export const PRIORITY_LABEL: Record<CasePriority, string> = {
  ROUTINE:  'Routine',
  URGENT:   'Urgent',
  EMERGENT: 'Emergent',
}

export const PRIORITY_COLOR: Record<CasePriority, { bg: string; text: string; border: string; dot: string }> = {
  ROUTINE:  { bg: 'bg-slate-500/10',   text: 'text-slate-400',   border: 'border-slate-500/20',   dot: 'bg-slate-400' },
  URGENT:   { bg: 'bg-amber-500/15',   text: 'text-amber-400',   border: 'border-amber-500/25',   dot: 'bg-amber-400' },
  EMERGENT: { bg: 'bg-red-500/15',     text: 'text-red-400',     border: 'border-red-500/25',     dot: 'bg-red-400 animate-pulse' },
}

export const AI_RECOMMENDATION_LABEL: Record<AIRecommendation, string> = {
  APPROVE:      'Approve',
  DENY:         'Deny',
  REQUEST_INFO: 'Request Info',
  ESCALATE:     'Escalate',
}

export const AI_RECOMMENDATION_COLOR: Record<AIRecommendation, { bg: string; text: string; border: string }> = {
  APPROVE:      { bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/25' },
  DENY:         { bg: 'bg-red-500/15',     text: 'text-red-400',     border: 'border-red-500/25' },
  REQUEST_INFO: { bg: 'bg-amber-500/15',   text: 'text-amber-400',   border: 'border-amber-500/25' },
  ESCALATE:     { bg: 'bg-violet-500/15',  text: 'text-violet-400',  border: 'border-violet-500/25' },
}

export const REVIEWABLE_STATUSES: CaseStatus[] = ['SUBMITTED', 'UNDER_REVIEW', 'PENDING_INFO']
export const TERMINAL_STATUSES:   CaseStatus[] = ['APPROVED', 'DENIED', 'WITHDRAWN']