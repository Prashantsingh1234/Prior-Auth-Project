import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Lock, FileUp, UserCheck, Brain, Eye, CheckCircle2, XCircle, ArrowUpRight,
  AlertTriangle, MessageSquare, FileText, Zap, Shield, Download,
  KeyRound, Clock, Activity, ChevronRight, Hash,
} from 'lucide-react'
import type { AuditEntry, AuditEventType, EventCategory } from '../hooks/useAuditData'

// ─── Event styling ────────────────────────────────────────────────────────────

const EVENT_CFG: Record<AuditEventType, { icon: React.ElementType; color: string; label: string }> = {
  SUBMITTED:               { icon: FileUp,         color: '#0ea5e9', label: 'Submitted' },
  ASSIGNED:                { icon: UserCheck,       color: '#6366f1', label: 'Assigned' },
  REVIEWED:                { icon: Eye,             color: '#6b7280', label: 'Reviewed' },
  APPROVED:                { icon: CheckCircle2,    color: '#10b981', label: 'Approved' },
  DENIED:                  { icon: XCircle,         color: '#ef4444', label: 'Denied' },
  ESCALATED:               { icon: ArrowUpRight,    color: '#f97316', label: 'Escalated' },
  PENDED:                  { icon: AlertTriangle,   color: '#f59e0b', label: 'Pended' },
  STATUS_CHANGED:          { icon: Activity,        color: '#6b7280', label: 'Status Changed' },
  AI_PROCESSED:            { icon: Brain,           color: '#8b5cf6', label: 'AI Processed' },
  AI_OUTPUT:               { icon: Brain,           color: '#8b5cf6', label: 'AI Output' },
  AI_OVERRIDE:             { icon: Zap,             color: '#f59e0b', label: 'AI Override' },
  AI_FALLBACK:             { icon: Zap,             color: '#f97316', label: 'AI Fallback' },
  PROMPT_TRACE:            { icon: Brain,           color: '#a855f7', label: 'Prompt Trace' },
  RETRIEVAL_TRACE:         { icon: Brain,           color: '#7c3aed', label: 'Retrieval Trace' },
  CLARIFICATION_REQUESTED: { icon: MessageSquare,   color: '#f59e0b', label: 'Clarification Requested' },
  CLARIFICATION_ANSWERED:  { icon: MessageSquare,   color: '#10b981', label: 'Clarification Answered' },
  CLARIFICATION_ESCALATED: { icon: MessageSquare,   color: '#ef4444', label: 'Clarification Escalated' },
  DOCUMENT_UPLOADED:       { icon: FileText,        color: '#0ea5e9', label: 'Doc Uploaded' },
  DOCUMENT_VIEWED:         { icon: Eye,             color: '#6b7280', label: 'Doc Viewed' },
  DOCUMENT_OCR:            { icon: FileText,        color: '#0ea5e9', label: 'OCR Processed' },
  POLICY_MATCHED:          { icon: Shield,          color: '#8b5cf6', label: 'Policy Matched' },
  POLICY_UPDATED:          { icon: Shield,          color: '#6366f1', label: 'Policy Updated' },
  COMPLIANCE_EXPORT:       { icon: Download,        color: '#10b981', label: 'Compliance Export' },
  ACCESS_GRANTED:          { icon: KeyRound,        color: '#6366f1', label: 'Access Granted' },
  ACCESS_REVOKED:          { icon: KeyRound,        color: '#ef4444', label: 'Access Revoked' },
  SLA_BREACHED:            { icon: Clock,           color: '#ef4444', label: 'SLA Breached' },
  SLA_WARNING:             { icon: Clock,           color: '#f59e0b', label: 'SLA Warning' },
}

const CATEGORY_COLOR: Record<EventCategory, string> = {
  decision:      '#10b981',
  ai:            '#8b5cf6',
  clarification: '#f59e0b',
  document:      '#0ea5e9',
  policy:        '#6366f1',
  system:        '#6b7280',
  compliance:    '#ef4444',
}

// ─── Role badge ───────────────────────────────────────────────────────────────

function RoleBadge({ role }: { role: string }) {
  const colors: Record<string, string> = {
    reviewer: '#10b981', admin: '#6366f1', ai_system: '#8b5cf6', provider: '#0ea5e9', system: '#6b7280',
  }
  const color = colors[role] ?? '#6b7280'
  return (
    <span className="px-1.5 py-0.5 rounded text-[7px] font-bold uppercase tracking-wide"
          style={{ background: `${color}18`, color }}>
      {role.replace('_', ' ')}
    </span>
  )
}

// ─── Immutability indicator ───────────────────────────────────────────────────

function ImmutabilityBadge({ hash }: { hash: string }) {
  const [showHash, setShowHash] = useState(false)
  return (
    <button
      onClick={(e) => { e.stopPropagation(); setShowHash((v) => !v) }}
      className="flex items-center gap-1 px-1.5 py-0.5 rounded transition-all hover:bg-emerald-500/10"
      title="Cryptographic integrity hash — immutable audit record"
    >
      <Lock className="w-2.5 h-2.5 text-emerald-400" />
      <AnimatePresence mode="wait">
        {showHash ? (
          <motion.span
            key="hash"
            initial={{ opacity: 0, width: 0 }}
            animate={{ opacity: 1, width: 'auto' }}
            exit={{ opacity: 0, width: 0 }}
            className="text-[7px] font-mono text-emerald-400 overflow-hidden whitespace-nowrap"
          >
            {hash.slice(0, 16)}…
          </motion.span>
        ) : (
          <motion.span key="label" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                       className="text-[7px] text-emerald-400 font-semibold">IMMUTABLE</motion.span>
        )}
      </AnimatePresence>
    </button>
  )
}

// ─── Metadata table ───────────────────────────────────────────────────────────

function MetaTable({ metadata }: { metadata: Record<string, string | number | boolean> }) {
  const entries = Object.entries(metadata)
  if (entries.length === 0) return null
  return (
    <div className="mt-2 rounded-lg overflow-hidden" style={{ border: '1px solid var(--border)' }}>
      <table className="w-full">
        <tbody>
          {entries.map(([k, v], i) => (
            <tr key={k} style={{ background: i % 2 === 0 ? 'var(--surface)' : 'var(--elevated)' }}>
              <td className="px-2 py-1 text-[8px] font-mono text-[var(--text-4)] whitespace-nowrap w-40">{k}</td>
              <td className="px-2 py-1 text-[8px] font-mono text-[var(--text-2)]">{String(v)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Single timeline entry ────────────────────────────────────────────────────

interface EntryRowProps {
  entry:    AuditEntry
  isActive: boolean
  isLast:   boolean
  onSelect: () => void
}

function EntryRow({ entry, isActive, isLast, onSelect }: EntryRowProps) {
  const cfg   = EVENT_CFG[entry.eventType] ?? { icon: Activity, color: '#6b7280', label: entry.eventType }
  const catColor = CATEGORY_COLOR[entry.category]

  const time  = new Date(entry.occurredAt)
  const timeStr = time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  const hasDetail = !!(entry.promptTrace || entry.retrievalTrace || entry.aiOutput || entry.override)

  return (
    <div className="flex gap-3 group">
      {/* Timeline rail */}
      <div className="flex flex-col items-center shrink-0" style={{ width: 28 }}>
        <motion.div
          className="w-7 h-7 rounded-full flex items-center justify-center relative z-10 shrink-0 cursor-pointer"
          style={{
            background: isActive ? `${cfg.color}30` : `${cfg.color}15`,
            border:     `2px solid ${isActive ? cfg.color : cfg.color + '50'}`,
            boxShadow:  isActive ? `0 0 10px ${cfg.color}40` : 'none',
          }}
          whileHover={{ scale: 1.1 }}
          onClick={onSelect}
        >
          <cfg.icon className="w-3 h-3" style={{ color: cfg.color }} />
        </motion.div>
        {!isLast && <div className="w-px flex-1 mt-1" style={{ background: `linear-gradient(to bottom, ${catColor}40, var(--border))` }} />}
      </div>

      {/* Entry card */}
      <motion.div
        layout
        className="flex-1 mb-3 min-w-0 cursor-pointer rounded-xl transition-all"
        style={{
          background: isActive ? `${cfg.color}08` : 'var(--elevated)',
          border:     `1px solid ${isActive ? cfg.color + '35' : 'var(--border)'}`,
        }}
        whileHover={{ borderColor: cfg.color + '40' }}
        onClick={onSelect}
      >
        {/* Header row */}
        <div className="flex items-center gap-2 px-3 py-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
              <span className="text-[9px] font-bold uppercase tracking-wide" style={{ color: cfg.color }}>{cfg.label}</span>
              <span className="text-[8px] font-mono text-[var(--text-4)] px-1.5 py-0.5 rounded"
                    style={{ background: 'var(--surface)' }}>{entry.caseRef}</span>
              <RoleBadge role={entry.actorRole} />
              {hasDetail && (
                <span className="text-[7px] px-1 py-0.5 rounded font-semibold" style={{ background: '#6366f118', color: '#6366f1' }}>DETAIL</span>
              )}
            </div>
            <p className="text-[10px] text-[var(--text-2)] leading-snug pr-2">{entry.description}</p>
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0">
            <span className="text-[8px] font-mono text-[var(--text-4)]">{timeStr}</span>
            <ImmutabilityBadge hash={entry.integrityHash} />
          </div>
        </div>

        {/* Actor + IP row */}
        <div className="flex items-center gap-3 px-3 pb-2 border-t border-[var(--border)] pt-1.5">
          <span className="text-[8px] text-[var(--text-3)]">{entry.actorName}</span>
          <span className="text-[8px] text-[var(--text-4)]">·</span>
          <span className="text-[8px] font-mono text-[var(--text-4)]">{entry.ipAddress}</span>
          <span className="text-[8px] text-[var(--text-4)] ml-auto flex items-center gap-1">
            <Hash className="w-2.5 h-2.5" />
            {entry.id}
          </span>
          {hasDetail && (
            <ChevronRight
              className="w-3 h-3 text-[var(--text-4)] transition-transform"
              style={{ transform: isActive ? 'rotate(90deg)' : 'none' }}
            />
          )}
        </div>

        {/* Metadata (when active) */}
        <AnimatePresence>
          {isActive && entry.metadata && Object.keys(entry.metadata).length > 0 && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden px-3 pb-3"
            >
              <MetaTable metadata={entry.metadata} />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}

// ─── Day group header ─────────────────────────────────────────────────────────

function DayHeader({ date, count }: { date: string; count: number }) {
  const label = (() => {
    const d = new Date(date)
    const today = new Date()
    const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1)
    if (d.toDateString() === today.toDateString()) return 'Today'
    if (d.toDateString() === yesterday.toDateString()) return 'Yesterday'
    return d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
  })()
  return (
    <div className="flex items-center gap-2 py-2 pl-1 mb-1 sticky top-0 z-10" style={{ background: 'var(--surface)' }}>
      <div className="h-px flex-1" style={{ background: 'var(--border)' }} />
      <span className="text-[9px] font-bold uppercase tracking-widest text-[var(--text-4)] px-2">{label}</span>
      <span className="text-[8px] text-[var(--text-4)] font-mono">{count}</span>
      <div className="h-px flex-1" style={{ background: 'var(--border)' }} />
    </div>
  )
}

// ─── Main timeline ────────────────────────────────────────────────────────────

interface AuditTimelineProps {
  entries:      AuditEntry[]
  selectedId:   string | null
  onSelect:     (id: string) => void
  totalCount:   number
}

export function AuditTimeline({ entries, selectedId, onSelect, totalCount }: AuditTimelineProps) {
  const grouped = useMemo(() => {
    const groups: Array<{ dateKey: string; entries: AuditEntry[] }> = []
    for (const e of entries) {
      const dk = new Date(e.occurredAt).toDateString()
      const g  = groups.find((g) => g.dateKey === dk)
      if (g) g.entries.push(e)
      else groups.push({ dateKey: dk, entries: [e] })
    }
    return groups
  }, [entries])

  return (
    <div className="flex-1 overflow-y-auto px-4 py-3">
      {entries.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16">
          <Activity className="w-8 h-8 text-[var(--text-4)] mb-2" />
          <p className="text-xs text-[var(--text-4)]">No audit entries match the current filters</p>
        </div>
      )}

      {entries.length > 0 && (
        <div className="mb-2 flex items-center gap-2">
          <span className="text-[9px] text-[var(--text-4)]">
            Showing {entries.length} of {totalCount} entries
          </span>
          {entries.length < totalCount && (
            <span className="text-[8px] px-1.5 py-0.5 rounded bg-[#6366f118] text-[#6366f1]">filtered</span>
          )}
        </div>
      )}

      {grouped.map(({ dateKey, entries: dayEntries }) => (
        <div key={dateKey}>
          <DayHeader date={dayEntries[0].occurredAt} count={dayEntries.length} />
          {dayEntries.map((entry, i) => (
            <EntryRow
              key={entry.id}
              entry={entry}
              isActive={selectedId === entry.id}
              isLast={i === dayEntries.length - 1 && dateKey === grouped[grouped.length - 1].dateKey}
              onSelect={() => onSelect(entry.id === selectedId ? '' : entry.id)}
            />
          ))}
        </div>
      ))}
    </div>
  )
}
