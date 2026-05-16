import { cn } from '@/lib/utils'
import type { AuditEvent } from '@/types'
import { formatDateTime } from '@/lib/utils'
import {
  FileUp, UserCheck, Brain, Eye, CheckCircle2,
  XCircle, MessageSquare, ArrowUpRight, AlertTriangle, FileText,
} from 'lucide-react'

const EVENT_ICON: Record<string, React.ElementType> = {
  SUBMITTED:               FileUp,
  ASSIGNED:                UserCheck,
  AI_PROCESSED:            Brain,
  REVIEWED:                Eye,
  APPROVED:                CheckCircle2,
  DENIED:                  XCircle,
  ESCALATED:               ArrowUpRight,
  PENDED:                  AlertTriangle,
  CLARIFICATION_REQUESTED: MessageSquare,
  CLARIFICATION_ANSWERED:  MessageSquare,
  DOCUMENT_UPLOADED:       FileText,
  DOCUMENT_VIEWED:         Eye,
  STATUS_CHANGED:          FileUp,
}
const EVENT_COLOR: Record<string, string> = {
  SUBMITTED:               'text-brand-400   bg-brand-500/15',
  ASSIGNED:                'text-sky-400     bg-sky-500/15',
  AI_PROCESSED:            'text-violet-400  bg-violet-500/15',
  REVIEWED:                'text-slate-400   bg-slate-500/15',
  APPROVED:                'text-emerald-400 bg-emerald-500/15',
  DENIED:                  'text-red-400     bg-red-500/15',
  ESCALATED:               'text-violet-400  bg-violet-500/15',
  PENDED:                  'text-amber-400   bg-amber-500/15',
  CLARIFICATION_REQUESTED: 'text-orange-400  bg-orange-500/15',
  CLARIFICATION_ANSWERED:  'text-green-400   bg-green-500/15',
  DOCUMENT_UPLOADED:       'text-brand-400   bg-brand-500/15',
  DOCUMENT_VIEWED:         'text-slate-400   bg-slate-500/15',
  STATUS_CHANGED:          'text-amber-400   bg-amber-500/15',
}

interface TimelineEventProps {
  event:    AuditEvent
  isLast?:  boolean
}

export function TimelineEvent({ event, isLast }: TimelineEventProps) {
  const Icon  = EVENT_ICON[event.eventType] ?? Eye
  const color = EVENT_COLOR[event.eventType] ?? 'text-slate-400 bg-slate-500/15'
  const [textColor, bgColor] = color.split(' ')

  return (
    <div className="flex items-start gap-4">
      <div className="flex flex-col items-center">
        <div className={cn('w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 border-2 border-[var(--surface)] z-10', bgColor)}>
          <Icon className={cn('w-3.5 h-3.5', textColor)} />
        </div>
        {!isLast && <div className="w-px flex-1 bg-[var(--border)] mt-1 min-h-4" />}
      </div>
      <div className={cn('pb-4 flex-1', isLast && 'pb-0')}>
        <p className="text-sm text-[var(--text-1)] leading-snug">{event.description}</p>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-xs text-[var(--text-3)]">{event.actorName}</span>
          <span className="text-xs text-[var(--text-3)]">·</span>
          <span className="text-xs text-[var(--text-3)]">{formatDateTime(event.occurredAt)}</span>
        </div>
      </div>
    </div>
  )
}