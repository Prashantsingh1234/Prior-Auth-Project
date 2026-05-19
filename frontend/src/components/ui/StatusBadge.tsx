import { cn } from '@/lib/utils'

const STATUS_MAP: Record<string, { label: string; className: string }> = {
  // Backend uppercase values
  SUBMITTED:             { label: 'Submitted',        className: 'bg-gray-100 text-gray-700' },
  PROCESSING:            { label: 'Processing',       className: 'bg-blue-100 text-blue-700' },
  PENDING_CLARIFICATION: { label: 'Info Requested',   className: 'bg-purple-100 text-purple-800' },
  UNDER_REVIEW:          { label: 'In Review',        className: 'bg-blue-100 text-blue-800' },
  APPROVED:              { label: 'Approved',         className: 'bg-green-100 text-green-800' },
  DENIED:                { label: 'Denied',           className: 'bg-red-100 text-red-800' },
  PENDED:                { label: 'Pended',           className: 'bg-amber-100 text-amber-800' },
  ESCALATED:             { label: 'Escalated',        className: 'bg-orange-100 text-orange-800' },
  CANCELLED:             { label: 'Cancelled',        className: 'bg-gray-100 text-gray-500' },
  // Legacy lowercase values (for backwards compatibility)
  approved:              { label: 'Approved',         className: 'bg-green-100 text-green-800' },
  denied:                { label: 'Denied',           className: 'bg-red-100 text-red-800' },
  pending:               { label: 'Pending',          className: 'bg-amber-100 text-amber-800' },
  in_review:             { label: 'In Review',        className: 'bg-blue-100 text-blue-800' },
  submitted:             { label: 'Submitted',        className: 'bg-gray-100 text-gray-700' },
  info_requested:        { label: 'Info Requested',   className: 'bg-purple-100 text-purple-800' },
}

interface Props {
  status: string
  className?: string
}

export function StatusBadge({ status, className }: Props) {
  const cfg = STATUS_MAP[status] ?? { label: status, className: 'bg-gray-100 text-gray-700' }
  return (
    <span className={cn('inline-flex items-center px-2 py-0.5 rounded text-xs font-medium', cfg.className, className)}>
      {cfg.label}
    </span>
  )
}
