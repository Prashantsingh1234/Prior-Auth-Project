import { useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Brain, ScanLine, BookOpen, AlertTriangle,
  Shield, Zap, ArrowUpRight,
} from 'lucide-react'
import { useActivityFeed, type ActivityEvent } from '../hooks/useDashboardData'
import { AIPulse } from '@/components/animations/AIPulse'
import { cn } from '@/lib/utils'

// ─── Config ───────────────────────────────────────────────────────────────────

const TYPE_CONFIG: Record<ActivityEvent['type'], {
  icon:  React.ElementType
  color: string
  bg:    string
}> = {
  ai_complete:   { icon: Brain,          color: '#8b5cf6', bg: 'rgba(139,92,246,0.12)' },
  ocr_complete:  { icon: ScanLine,       color: '#0ea5e9', bg: 'rgba(14,165,233,0.12)' },
  policy_match:  { icon: BookOpen,       color: '#10b981', bg: 'rgba(16,185,129,0.12)' },
  low_confidence:{ icon: AlertTriangle,  color: '#f59e0b', bg: 'rgba(245,158,11,0.12)' },
  recommendation:{ icon: Zap,            color: '#ef4444', bg: 'rgba(239,68,68,0.12)'  },
  guardrail:     { icon: Shield,         color: '#f97316', bg: 'rgba(249,115,22,0.12)' },
  escalated:     { icon: ArrowUpRight,   color: '#a855f7', bg: 'rgba(168,85,247,0.12)' },
}

const SEVERITY_PULSE: Record<ActivityEvent['severity'], string> = {
  info:    '',
  success: '',
  warning: 'ring-1 ring-amber-500/30',
  error:   'ring-1 ring-red-500/30',
}

// ─── Confidence pill ─────────────────────────────────────────────────────────

function ConfidencePill({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 85 ? '#10b981' : pct >= 65 ? '#f59e0b' : '#ef4444'
  return (
    <span
      className="text-[9px] font-mono px-1.5 py-0.5 rounded-full tabular-nums"
      style={{ background: `${color}15`, color }}
    >
      {pct}%
    </span>
  )
}

// ─── Time ago ────────────────────────────────────────────────────────────────

function timeAgo(ts: Date): string {
  const diff = Date.now() - ts.getTime()
  if (diff < 10_000)  return 'just now'
  if (diff < 60_000)  return `${Math.floor(diff / 1000)}s ago`
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)}m ago`
  return `${Math.floor(diff / 3600_000)}h ago`
}

// ─── Event row ────────────────────────────────────────────────────────────────

function EventRow({ event, isNew }: { event: ActivityEvent; isNew: boolean }) {
  const cfg = TYPE_CONFIG[event.type] ?? TYPE_CONFIG.ai_complete

  return (
    <motion.div
      layout
      initial={isNew ? { opacity: 0, x: -20, height: 0 } : false}
      animate={{ opacity: 1, x: 0, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className={cn(
        'flex items-start gap-3 px-4 py-3 border-b border-[var(--border)] last:border-0',
        'hover:bg-[var(--elevated)] transition-colors group cursor-default',
        SEVERITY_PULSE[event.severity],
      )}
    >
      {/* Icon */}
      <div
        className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
        style={{ background: cfg.bg }}
      >
        <cfg.icon style={{ color: cfg.color, width: 14, height: 14 }} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[11px] font-semibold text-[var(--text-1)]">{event.caseId}</span>
          {event.patient && (
            <span className="text-[10px] text-[var(--text-4)]">· {event.patient}</span>
          )}
          {event.confidence != null && <ConfidencePill value={event.confidence} />}
        </div>
        <p className="text-[11px] text-[var(--text-3)] mt-0.5 leading-relaxed">{event.message}</p>
      </div>

      {/* Timestamp */}
      <span className="text-[9px] text-[var(--text-4)] flex-shrink-0 mt-1 tabular-nums">
        {timeAgo(event.timestamp)}
      </span>
    </motion.div>
  )
}

// ─── Feed ─────────────────────────────────────────────────────────────────────

export function AIActivityFeed() {
  const events   = useActivityFeed()
  const prevLen  = useRef(events.length)
  const newIds   = useRef<Set<string>>(new Set())
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (events.length > prevLen.current) {
      const added = events.slice(0, events.length - prevLen.current)
      added.forEach((e) => newIds.current.add(e.id))
      // Auto-scroll to top on new event
      scrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
    }
    prevLen.current = events.length
  }, [events])

  return (
    <div
      className="rounded-2xl overflow-hidden flex flex-col"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <AIPulse size={7} color="#10b981" rings={2} />
          <span className="text-sm font-semibold text-[var(--text-1)]">AI Activity Feed</span>
        </div>
        <span className="text-[10px] text-[var(--text-4)] tabular-nums">
          {events.length} events
        </span>
      </div>

      {/* Events */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto max-h-[420px] scrollbar-thin">
        <AnimatePresence initial={false}>
          {events.map((event) => (
            <EventRow
              key={event.id}
              event={event}
              isNew={newIds.current.has(event.id)}
            />
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}
