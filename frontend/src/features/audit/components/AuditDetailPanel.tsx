import { motion } from 'framer-motion'
import {
  Lock, Shield, Hash, Monitor, Globe, Clock, User,
  CheckCircle2, XCircle, AlertTriangle, Activity,
  Brain, FileText, MessageSquare, Download, KeyRound,
} from 'lucide-react'
import { TraceViewer } from './TraceViewer'
import type { AuditEntry, AuditEventType } from '../hooks/useAuditData'

// ─── Event type color mapping ─────────────────────────────────────────────────

const EVENT_COLOR: Record<AuditEventType, string> = {
  SUBMITTED:               '#0ea5e9',
  ASSIGNED:                '#6366f1',
  REVIEWED:                '#6b7280',
  APPROVED:                '#10b981',
  DENIED:                  '#ef4444',
  ESCALATED:               '#f97316',
  PENDED:                  '#f59e0b',
  STATUS_CHANGED:          '#6b7280',
  AI_PROCESSED:            '#8b5cf6',
  AI_OUTPUT:               '#8b5cf6',
  AI_OVERRIDE:             '#f59e0b',
  AI_FALLBACK:             '#f97316',
  PROMPT_TRACE:            '#a855f7',
  RETRIEVAL_TRACE:         '#7c3aed',
  CLARIFICATION_REQUESTED: '#f59e0b',
  CLARIFICATION_ANSWERED:  '#10b981',
  CLARIFICATION_ESCALATED: '#ef4444',
  DOCUMENT_UPLOADED:       '#0ea5e9',
  DOCUMENT_VIEWED:         '#6b7280',
  DOCUMENT_OCR:            '#0ea5e9',
  POLICY_MATCHED:          '#8b5cf6',
  POLICY_UPDATED:          '#6366f1',
  COMPLIANCE_EXPORT:       '#10b981',
  ACCESS_GRANTED:          '#6366f1',
  ACCESS_REVOKED:          '#ef4444',
  SLA_BREACHED:            '#ef4444',
  SLA_WARNING:             '#f59e0b',
}

const EVENT_ICON: Partial<Record<AuditEventType, React.ElementType>> = {
  APPROVED: CheckCircle2, DENIED: XCircle,
  ESCALATED: AlertTriangle, SLA_BREACHED: Clock, SLA_WARNING: Clock,
  AI_PROCESSED: Brain, PROMPT_TRACE: Brain, RETRIEVAL_TRACE: Brain,
  AI_OVERRIDE: Activity, AI_FALLBACK: Activity,
  DOCUMENT_UPLOADED: FileText, DOCUMENT_VIEWED: FileText, DOCUMENT_OCR: FileText,
  CLARIFICATION_REQUESTED: MessageSquare, CLARIFICATION_ANSWERED: MessageSquare,
  COMPLIANCE_EXPORT: Download, ACCESS_GRANTED: KeyRound, ACCESS_REVOKED: KeyRound,
}

// ─── Integrity proof block ────────────────────────────────────────────────────

function IntegrityProof({ entry }: { entry: AuditEntry }) {
  return (
    <div className="rounded-xl p-3 space-y-2" style={{ background: 'rgba(16,185,129,0.04)', border: '1px solid rgba(16,185,129,0.2)' }}>
      <div className="flex items-center gap-2">
        <motion.div animate={{ opacity: [1, 0.5, 1] }} transition={{ duration: 3, repeat: Infinity }}>
          <Lock className="w-3 h-3 text-emerald-400" />
        </motion.div>
        <span className="text-[9px] font-bold uppercase tracking-wide text-emerald-400">Immutable Record — Integrity Verified</span>
        <Shield className="w-3 h-3 text-emerald-400 ml-auto" />
      </div>
      <div className="space-y-1">
        {[
          { label: 'SHA-256', value: entry.integrityHash },
          { label: 'Event ID', value: entry.id },
        ].map(({ label, value }) => (
          <div key={label} className="flex items-center gap-2">
            <Hash className="w-2.5 h-2.5 text-emerald-400/60 shrink-0" />
            <span className="text-[8px] text-emerald-400/60 w-12 shrink-0">{label}</span>
            <span className="text-[8px] font-mono text-emerald-400 truncate">{value}</span>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-3 pt-1 border-t border-emerald-500/10">
        <span className="text-[7px] text-emerald-400/50">HIPAA §164.312(b) · 21 CFR Part 11 · Non-repudiable</span>
      </div>
    </div>
  )
}

// ─── Context block ────────────────────────────────────────────────────────────

function ContextRow({ icon: Icon, label, value, mono = false }: {
  icon: React.ElementType; label: string; value: string; mono?: boolean
}) {
  return (
    <div className="flex items-center gap-2 py-1.5 border-b border-[var(--border)] last:border-0">
      <Icon className="w-3 h-3 text-[var(--text-4)] shrink-0" />
      <span className="text-[8px] text-[var(--text-4)] w-20 shrink-0">{label}</span>
      <span className={`text-[9px] text-[var(--text-2)] truncate ${mono ? 'font-mono' : ''}`}>{value}</span>
    </div>
  )
}

// ─── Metadata table ───────────────────────────────────────────────────────────

function MetadataGrid({ metadata }: { metadata: Record<string, string | number | boolean> }) {
  const entries = Object.entries(metadata)
  if (entries.length === 0) return null
  return (
    <div>
      <p className="text-[8px] font-bold uppercase tracking-widest text-[var(--text-4)] mb-1.5">Event Metadata</p>
      <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--border)' }}>
        {entries.map(([k, v], i) => (
          <div
            key={k}
            className="flex items-center gap-3 px-3 py-1.5"
            style={{ background: i % 2 === 0 ? 'var(--surface)' : 'var(--elevated)' }}
          >
            <span className="text-[8px] font-mono text-[var(--text-4)] w-36 shrink-0">{k}</span>
            <span className="text-[8px] font-mono text-[var(--text-2)]">{String(v)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Decision outcome band ────────────────────────────────────────────────────

function OutcomeBand({ eventType }: { eventType: AuditEventType }) {
  const bands: Partial<Record<AuditEventType, { label: string; color: string; bg: string }>> = {
    APPROVED:     { label: 'AUTHORIZED', color: '#10b981', bg: '#10b98115' },
    DENIED:       { label: 'DENIED',     color: '#ef4444', bg: '#ef444415' },
    PENDED:       { label: 'PENDED',     color: '#f59e0b', bg: '#f59e0b15' },
    ESCALATED:    { label: 'ESCALATED',  color: '#f97316', bg: '#f9731615' },
    SLA_BREACHED: { label: 'SLA BREACH', color: '#ef4444', bg: '#ef444415' },
    AI_OVERRIDE:  { label: 'OVERRIDE',   color: '#f59e0b', bg: '#f59e0b15' },
  }
  const band = bands[eventType]
  if (!band) return null
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex items-center justify-center gap-2 py-2 rounded-xl"
      style={{ background: band.bg, border: `1px solid ${band.color}40` }}
    >
      <span className="text-xs font-bold tracking-widest" style={{ color: band.color }}>{band.label}</span>
    </motion.div>
  )
}

// ─── Main detail panel ────────────────────────────────────────────────────────

interface AuditDetailPanelProps {
  entry: AuditEntry
}

export function AuditDetailPanel({ entry }: AuditDetailPanelProps) {
  const color   = EVENT_COLOR[entry.eventType] ?? '#6b7280'
  const Icon    = EVENT_ICON[entry.eventType] ?? Activity
  const time    = new Date(entry.occurredAt)

  return (
    <motion.div
      key={entry.id}
      initial={{ opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -8 }}
      transition={{ duration: 0.15 }}
      className="flex flex-col h-full overflow-y-auto"
    >
      {/* Entry header */}
      <div className="px-5 pt-5 pb-4 shrink-0 border-b border-[var(--border)]" style={{ background: 'var(--elevated)' }}>
        <div className="flex items-start gap-3 mb-3">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
            style={{ background: `${color}20`, border: `1.5px solid ${color}50` }}
          >
            <Icon className="w-5 h-5" style={{ color }} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="text-[10px] font-bold uppercase tracking-wide" style={{ color }}>{entry.eventType.replace(/_/g, ' ')}</span>
              <span className="text-[8px] font-mono px-1.5 py-0.5 rounded" style={{ background: `${color}15`, color }}>{entry.caseRef}</span>
            </div>
            <p className="text-sm font-semibold text-[var(--text-1)] leading-snug">{entry.description}</p>
          </div>
        </div>
        <OutcomeBand eventType={entry.eventType} />
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {/* Context */}
        <div className="rounded-xl px-3 py-2" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
          <ContextRow icon={User}    label="Actor"      value={`${entry.actorName} (${entry.actorRole.replace('_', ' ')})`} />
          <ContextRow icon={Clock}   label="Timestamp"  value={time.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'long' })} mono />
          <ContextRow icon={Globe}   label="IP Address" value={entry.ipAddress} mono />
          <ContextRow icon={Monitor} label="User Agent" value={entry.userAgent.slice(0, 48) + '…'} />
          <ContextRow icon={Hash}    label="Entry ID"   value={entry.id} mono />
        </div>

        {/* Outcome / metadata */}
        {entry.metadata && Object.keys(entry.metadata).length > 0 && (
          <MetadataGrid metadata={entry.metadata} />
        )}

        {/* Trace viewer — inline expanded */}
        {(entry.promptTrace || entry.retrievalTrace || entry.aiOutput || entry.override) && (
          <TraceViewer entry={entry} />
        )}

        {/* Integrity proof */}
        <IntegrityProof entry={entry} />
      </div>
    </motion.div>
  )
}
