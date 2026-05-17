import { motion } from 'framer-motion'
import {
  Send, MessageSquare, CheckCircle2, ArrowUpCircle, AlertTriangle, Cpu, Building2, User, Bot,
} from 'lucide-react'
import type { TimelineEvent, MessageAuthor } from '../hooks/useClarificationManager'

// ─── Event config ─────────────────────────────────────────────────────────────

const EVENT_CFG: Record<string, { color: string; bg: string; Icon: React.ElementType }> = {
  sent:      { color: '#6366f1', bg: '#6366f115', Icon: Send },
  responded: { color: '#10b981', bg: '#10b98115', Icon: MessageSquare },
  reviewed:  { color: '#0ea5e9', bg: '#0ea5e915', Icon: CheckCircle2 },
  escalated: { color: '#ef4444', bg: '#ef444415', Icon: ArrowUpCircle },
  resolved:  { color: '#10b981', bg: '#10b98115', Icon: CheckCircle2 },
  attempt:   { color: '#f59e0b', bg: '#f59e0b15', Icon: AlertTriangle },
  system:    { color: '#6b7280', bg: '#6b728015', Icon: Cpu },
}

const ACTOR_ICON: Record<MessageAuthor, React.ElementType> = {
  ai:       Bot,
  reviewer: User,
  provider: Building2,
  system:   Cpu,
}

const ACTOR_COLOR: Record<MessageAuthor, string> = {
  ai:       '#8b5cf6',
  reviewer: '#6366f1',
  provider: '#10b981',
  system:   '#6b7280',
}

function formatShort(date: Date) {
  const now  = new Date()
  const diff = (now.getTime() - date.getTime()) / 1000
  if (diff < 3600)   return `${Math.round(diff / 60)}m ago`
  if (diff < 86400)  return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
}

// ─── Event dot ────────────────────────────────────────────────────────────────

interface EventProps {
  event:   TimelineEvent
  isLast:  boolean
  index:   number
}

function EventDot({ event, isLast, index }: EventProps) {
  const cfg      = EVENT_CFG[event.type] ?? EVENT_CFG.system
  const ActorIcon = ACTOR_ICON[event.actor]
  const actorColor = ACTOR_COLOR[event.actor]

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.06, duration: 0.25 }}
      className="flex gap-3 relative"
    >
      {/* Connector */}
      <div className="flex flex-col items-center" style={{ width: 28, flexShrink: 0 }}>
        <div
          className="w-7 h-7 rounded-xl flex items-center justify-center shrink-0 z-10"
          style={{ background: cfg.bg, border: `1.5px solid ${cfg.color}40` }}
        >
          <cfg.Icon style={{ color: cfg.color, width: 12, height: 12 }} />
        </div>
        {!isLast && (
          <div className="w-px flex-1 mt-1" style={{ background: 'var(--border)', minHeight: 12 }} />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 pb-3 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold text-[var(--text-1)] leading-tight">{event.label}</p>
            <p className="text-[10px] text-[var(--text-4)] mt-0.5 leading-snug">{event.detail}</p>
          </div>
          <span className="text-[9px] font-mono text-[var(--text-4)] whitespace-nowrap shrink-0">
            {formatShort(event.timestamp)}
          </span>
        </div>

        <div className="flex items-center gap-1.5 mt-1">
          <ActorIcon style={{ color: actorColor, width: 9, height: 9 }} />
          <span className="text-[9px]" style={{ color: actorColor }}>
            {event.actor === 'ai' ? 'AI System' : event.actor === 'reviewer' ? 'Reviewer' : event.actor === 'provider' ? 'Provider' : 'System'}
          </span>
          {event.threadId && (
            <span className="text-[8px] font-mono text-[var(--text-4)]">· {event.threadId}</span>
          )}
        </div>
      </div>
    </motion.div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  events: TimelineEvent[]
}

export function ClarificationTimeline({ events }: Props) {
  const sorted = [...events].sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())

  const counts = {
    sent:      events.filter((e) => e.type === 'sent').length,
    responded: events.filter((e) => e.type === 'responded').length,
    resolved:  events.filter((e) => e.type === 'resolved').length,
    escalated: events.filter((e) => e.type === 'escalated').length,
  }

  return (
    <div
      className="rounded-2xl overflow-hidden flex flex-col"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 border-b border-[var(--border)] shrink-0"
        style={{ background: 'var(--elevated)' }}
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-bold text-[var(--text-1)]">Clarification History</span>
          <span className="text-[10px] font-mono text-[var(--text-4)]">{events.length} events</span>
        </div>

        {/* Mini stats */}
        <div className="flex gap-1.5">
          {[
            { label: 'Sent',     value: counts.sent,      color: '#6366f1' },
            { label: 'Received', value: counts.responded, color: '#10b981' },
            { label: 'Resolved', value: counts.resolved,  color: '#0ea5e9' },
          ].map((s) => (
            <div
              key={s.label}
              className="flex-1 text-center py-1.5 rounded-lg"
              style={{ background: `${s.color}10`, border: `1px solid ${s.color}20` }}
            >
              <p className="text-sm font-bold tabular-nums" style={{ color: s.color }}>{s.value}</p>
              <p className="text-[8px] text-[var(--text-4)]">{s.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Events */}
      <div className="flex-1 overflow-y-auto p-4">
        {sorted.map((event, i) => (
          <EventDot
            key={event.id}
            event={event}
            isLast={i === sorted.length - 1}
            index={i}
          />
        ))}
      </div>
    </div>
  )
}
