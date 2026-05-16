import { motion } from 'framer-motion'
import {
  FileUp, UserCheck, Brain, Eye, CheckCircle2,
  XCircle, MessageSquare, ArrowUpRight, AlertTriangle,
} from 'lucide-react'
import { formatDateTime } from '@/lib/utils'
import { cn } from '@/lib/utils'

type AuditEventType =
  | 'SUBMITTED' | 'ASSIGNED' | 'AI_PROCESSED' | 'REVIEWED'
  | 'APPROVED' | 'DENIED' | 'ESCALATED' | 'PENDED' | 'CLARIFICATION_REQUESTED'

const EVENT_CFG: Record<AuditEventType, { icon: React.ElementType; color: string; bg: string }> = {
  SUBMITTED:                { icon: FileUp,           color: 'text-brand-400',   bg: 'bg-brand-500/15' },
  ASSIGNED:                 { icon: UserCheck,         color: 'text-sky-400',     bg: 'bg-sky-500/15' },
  AI_PROCESSED:             { icon: Brain,             color: 'text-violet-400',  bg: 'bg-violet-500/15' },
  REVIEWED:                 { icon: Eye,               color: 'text-slate-400',   bg: 'bg-slate-500/15' },
  APPROVED:                 { icon: CheckCircle2,      color: 'text-emerald-400', bg: 'bg-emerald-500/15' },
  DENIED:                   { icon: XCircle,           color: 'text-red-400',     bg: 'bg-red-500/15' },
  ESCALATED:                { icon: ArrowUpRight,      color: 'text-violet-400',  bg: 'bg-violet-500/15' },
  PENDED:                   { icon: AlertTriangle,     color: 'text-amber-400',   bg: 'bg-amber-500/15' },
  CLARIFICATION_REQUESTED:  { icon: MessageSquare,     color: 'text-orange-400',  bg: 'bg-orange-500/15' },
}

interface AuditEvent {
  id: string
  eventType: AuditEventType
  description: string
  actorId: string
  actorRole: string
  actorName: string
  occurredAt: string
  metadata?: Record<string, any>
}

const MOCK_EVENTS: AuditEvent[] = [
  {
    id: 'ae1',
    eventType: 'SUBMITTED',
    description: 'PA request submitted for total knee arthroplasty (CPT 27447)',
    actorId: 'prov-001',
    actorRole: 'provider',
    actorName: 'Dr. Robert Stein',
    occurredAt: new Date(Date.now() - 3600000 * 4).toISOString(),
    metadata: { documents: 4, cpt: '27447', icd: ['M17.11', 'M25.361'] },
  },
  {
    id: 'ae2',
    eventType: 'AI_PROCESSED',
    description: 'AI workflow completed: OCR → Extraction → Retrieval → Reasoning',
    actorId: 'system',
    actorRole: 'system',
    actorName: 'AI Engine',
    occurredAt: new Date(Date.now() - 3600000 * 3.95).toISOString(),
    metadata: { duration_ms: 3420, model: 'gpt-4o', recommendation: 'APPROVE', confidence: 0.91 },
  },
  {
    id: 'ae3',
    eventType: 'CLARIFICATION_REQUESTED',
    description: 'AI requested pre-operative cardiac evaluation documentation',
    actorId: 'system',
    actorRole: 'system',
    actorName: 'AI Engine',
    occurredAt: new Date(Date.now() - 3600000 * 3.5).toISOString(),
  },
  {
    id: 'ae4',
    eventType: 'ASSIGNED',
    description: 'Case assigned to Dr. Sarah Chen for review',
    actorId: 'admin-001',
    actorRole: 'admin',
    actorName: 'Admin',
    occurredAt: new Date(Date.now() - 3600000 * 2).toISOString(),
    metadata: { reviewer: 'Dr. Sarah Chen' },
  },
  {
    id: 'ae5',
    eventType: 'REVIEWED',
    description: 'Reviewer opened case workspace',
    actorId: 'rev-001',
    actorRole: 'reviewer',
    actorName: 'Dr. Sarah Chen',
    occurredAt: new Date(Date.now() - 3600000).toISOString(),
  },
]

export function AuditHistory() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[var(--text-1)]">Audit Trail</h3>
        <span className="text-xs text-[var(--text-3)]">{MOCK_EVENTS.length} events</span>
      </div>

      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-4 top-5 bottom-5 w-px bg-[var(--border)]" />

        <div className="space-y-4">
          {MOCK_EVENTS.map((event, i) => {
            const cfg = EVENT_CFG[event.eventType]
            const Icon = cfg.icon
            return (
              <motion.div
                key={event.id}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.07 }}
                className="flex items-start gap-4"
              >
                {/* Icon */}
                <div className={cn('w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 border-2 border-[var(--surface)] z-10', cfg.bg)}>
                  <Icon className={cn('w-3.5 h-3.5', cfg.color)} />
                </div>

                {/* Content */}
                <div className="flex-1 pt-1 min-w-0">
                  <p className="text-sm text-[var(--text-1)] leading-snug">{event.description}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-[var(--text-3)]">{event.actorName}</span>
                    <span className="text-xs text-[var(--text-3)]">·</span>
                    <span className="text-xs text-[var(--text-3)]">{formatDateTime(event.occurredAt)}</span>
                  </div>
                  {event.metadata && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {Object.entries(event.metadata).map(([k, v]) => (
                        <span key={k} className="text-xs px-2 py-0.5 rounded-full bg-[var(--elevated)] text-[var(--text-3)] border border-[var(--border)]">
                          {k}: {Array.isArray(v) ? v.join(', ') : String(v)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </motion.div>
            )
          })}
        </div>
      </div>
    </div>
  )
}