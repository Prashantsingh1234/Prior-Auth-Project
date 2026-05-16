import { format, formatDistanceToNow } from 'date-fns'
import { clsx } from 'clsx'
import {
  CheckCircle2, XCircle, Clock, ArrowUpCircle, MessageSquare,
  FileText, UserCheck, Activity,
} from 'lucide-react'
import type { AuditEvent, ReviewerActionType } from '@/api/types'

interface AuditHistoryProps {
  events: AuditEvent[]
  isLoading?: boolean
}

const EVENT_CONFIG: Record<ReviewerActionType, { icon: React.ReactNode; color: string; bg: string }> = {
  ASSIGNED:                 { icon: <UserCheck className="w-3.5 h-3.5" />,    color: 'text-violet-600', bg: 'bg-violet-50' },
  APPROVED:                 { icon: <CheckCircle2 className="w-3.5 h-3.5" />, color: 'text-green-600',  bg: 'bg-green-50' },
  DENIED:                   { icon: <XCircle className="w-3.5 h-3.5" />,      color: 'text-red-600',    bg: 'bg-red-50' },
  PENDED:                   { icon: <Clock className="w-3.5 h-3.5" />,        color: 'text-amber-600',  bg: 'bg-amber-50' },
  OVERRIDE_APPROVED:        { icon: <CheckCircle2 className="w-3.5 h-3.5" />, color: 'text-green-700',  bg: 'bg-green-100' },
  OVERRIDE_DENIED:          { icon: <XCircle className="w-3.5 h-3.5" />,      color: 'text-red-700',    bg: 'bg-red-100' },
  REQUESTED_CLARIFICATION:  { icon: <MessageSquare className="w-3.5 h-3.5" />, color: 'text-amber-600', bg: 'bg-amber-50' },
  ESCALATED:                { icon: <ArrowUpCircle className="w-3.5 h-3.5" />, color: 'text-purple-600', bg: 'bg-purple-50' },
  ADDED_NOTE:               { icon: <FileText className="w-3.5 h-3.5" />,     color: 'text-slate-600',  bg: 'bg-slate-100' },
}

function formatEventLabel(eventType: ReviewerActionType): string {
  return eventType
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export function AuditHistory({ events, isLoading }: AuditHistoryProps) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex gap-3">
            <div className="w-7 h-7 rounded-full bg-slate-100 animate-pulse flex-shrink-0" />
            <div className="flex-1 space-y-1.5 pt-1">
              <div className="h-3 bg-slate-100 rounded animate-pulse w-1/2" />
              <div className="h-2.5 bg-slate-50 rounded animate-pulse w-3/4" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-24 text-slate-400 text-sm gap-2">
        <Activity className="w-6 h-6 opacity-40" />
        No audit events
      </div>
    )
  }

  const sorted = [...events].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
  )

  return (
    <div className="relative">
      {/* Vertical connector line */}
      <div className="absolute left-3.5 top-0 bottom-0 w-px bg-slate-200" />

      <div className="space-y-4">
        {sorted.map((event) => {
          const cfg = EVENT_CONFIG[event.event_type] ?? {
            icon: <Activity className="w-3.5 h-3.5" />,
            color: 'text-slate-400',
            bg: 'bg-slate-50',
          }

          return (
            <div key={event.event_id} className="flex gap-3 relative">
              {/* Timeline dot */}
              <div className={clsx(
                'flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center z-10 ring-2 ring-white',
                cfg.bg, cfg.color,
              )}>
                {cfg.icon}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0 pt-0.5">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-800">
                      {formatEventLabel(event.event_type)}
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {event.actor_name}
                      <span className="text-slate-400 ml-1 capitalize">({event.actor_role})</span>
                    </p>
                  </div>
                  <p
                    className="text-xs text-slate-400 flex-shrink-0"
                    title={format(new Date(event.timestamp), 'PPpp')}
                  >
                    {formatDistanceToNow(new Date(event.timestamp), { addSuffix: true })}
                  </p>
                </div>

                {event.note && (
                  <div className={clsx('mt-1.5 p-2 rounded-lg text-xs text-slate-600 leading-relaxed', cfg.bg)}>
                    {event.note}
                  </div>
                )}

                {Object.keys(event.metadata).length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
                    {Object.entries(event.metadata)
                      .filter(([, v]) => v != null && v !== '')
                      .map(([k, v]) => (
                        <span key={k} className="text-xs text-slate-400">
                          <span className="capitalize">{k.replace(/_/g, ' ')}</span>:{' '}
                          <span className="text-slate-600 font-medium">{String(v)}</span>
                        </span>
                      ))}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
