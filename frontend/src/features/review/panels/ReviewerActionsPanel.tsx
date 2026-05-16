import { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  CheckCircle2, XCircle, Clock,
  ArrowUpRight, MessageSquare, Mic, MicOff,
  AlertTriangle, User, Bot, ChevronDown,
  Send, RotateCcw, FileText, Clipboard,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ReviewState, AuditEntry } from '../hooks/useCaseReviewData'

// ─── Types ────────────────────────────────────────────────────────────────────

type DecisionType = 'APPROVE' | 'DENY' | 'PEND' | 'OVERRIDE' | 'CLARIFY' | 'ESCALATE'

// ─── Decision button config ───────────────────────────────────────────────────

const DECISIONS: {
  type:    DecisionType
  label:   string
  icon:    React.ElementType
  color:   string
  bg:      string
  border:  string
  glow:    string
  primary: boolean
}[] = [
  {
    type: 'APPROVE', label: 'Approve', icon: CheckCircle2,
    color: '#10b981', bg: 'rgba(16,185,129,0.15)', border: 'rgba(16,185,129,0.4)', glow: 'rgba(16,185,129,0.3)',
    primary: true,
  },
  {
    type: 'DENY', label: 'Deny', icon: XCircle,
    color: '#ef4444', bg: 'rgba(239,68,68,0.15)', border: 'rgba(239,68,68,0.4)', glow: 'rgba(239,68,68,0.3)',
    primary: true,
  },
  {
    type: 'PEND', label: 'Pend', icon: Clock,
    color: '#f59e0b', bg: 'rgba(245,158,11,0.15)', border: 'rgba(245,158,11,0.35)', glow: 'rgba(245,158,11,0.25)',
    primary: false,
  },
  {
    type: 'ESCALATE', label: 'Escalate', icon: ArrowUpRight,
    color: '#8b5cf6', bg: 'rgba(139,92,246,0.15)', border: 'rgba(139,92,246,0.35)', glow: 'rgba(139,92,246,0.25)',
    primary: false,
  },
]

// ─── Audit timeline entry ─────────────────────────────────────────────────────

const AUDIT_ICONS: Record<string, { icon: React.ElementType; color: string }> = {
  AI_PROCESSED:    { icon: Bot,           color: '#8b5cf6' },
  ASSIGNED:        { icon: User,          color: '#0ea5e9' },
  OPENED:          { icon: FileText,      color: '#6b7280' },
  DOCUMENT_VIEWED: { icon: FileText,      color: '#6b7280' },
  NOTE_ADDED:      { icon: MessageSquare, color: '#f59e0b' },
  CLARIFICATION_REQUESTED: { icon: MessageSquare, color: '#f97316' },
  APPROVED:        { icon: CheckCircle2,  color: '#10b981' },
  DENIED:          { icon: XCircle,       color: '#ef4444' },
  ESCALATED:       { icon: ArrowUpRight,  color: '#8b5cf6' },
  PENDED:          { icon: Clock,         color: '#f59e0b' },
}

function timeAgo(ts: Date) {
  const diff = Date.now() - ts.getTime()
  if (diff < 60_000)  return `${Math.floor(diff / 1000)}s ago`
  if (diff < 3600_000) return `${Math.floor(diff / 60000)}m ago`
  return `${Math.floor(diff / 3600000)}h ago`
}

function AuditItem({ entry, isLast }: { entry: AuditEntry; isLast: boolean }) {
  const cfg = AUDIT_ICONS[entry.type] ?? { icon: FileText, color: '#6b7280' }
  return (
    <div className="flex items-start gap-2.5 relative">
      {/* Connector line */}
      {!isLast && (
        <div className="absolute left-3.5 top-5 w-px bg-[var(--border)]" style={{ height: 'calc(100% + 8px)' }} />
      )}
      {/* Icon */}
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 z-10"
        style={{ background: `${cfg.color}15`, border: `1px solid ${cfg.color}30` }}
      >
        <cfg.icon style={{ color: cfg.color, width: 12, height: 12 }} />
      </div>
      {/* Content */}
      <div className="flex-1 min-w-0 pb-3">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] font-medium text-[var(--text-2)]">{entry.actor}</span>
          <span className="text-[9px] text-[var(--text-4)] tabular-nums flex-shrink-0">{timeAgo(entry.ts)}</span>
        </div>
        {entry.note && (
          <p className="text-[10px] text-[var(--text-4)] mt-0.5 leading-relaxed">{entry.note}</p>
        )}
        <span
          className="inline-block mt-0.5 text-[8px] font-mono uppercase px-1.5 py-0.5 rounded"
          style={{ background: `${cfg.color}12`, color: cfg.color }}
        >
          {entry.type.replace(/_/g, ' ')}
        </span>
      </div>
    </div>
  )
}

// ─── Clarification form ───────────────────────────────────────────────────────

function ClarificationForm({ onClose }: { onClose: () => void }) {
  const [text, setText] = useState('')
  const [type, setType] = useState<'patient' | 'records' | 'policy'>('records')

  const types = [
    { id: 'patient' as const, label: 'Patient Info' },
    { id: 'records' as const, label: 'Medical Records' },
    { id: 'policy'  as const, label: 'Policy Question' },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.2 }}
      className="overflow-hidden"
    >
      <div className="pt-3 space-y-3">
        {/* Type selector */}
        <div className="flex items-center gap-1.5">
          {types.map((t) => (
            <button
              key={t.id}
              onClick={() => setType(t.id)}
              className={cn(
                'flex-1 py-1 text-[10px] font-medium rounded-lg border transition-all',
                type === t.id
                  ? 'bg-orange-500/15 border-orange-500/40 text-orange-400'
                  : 'border-[var(--border)] text-[var(--text-4)] hover:border-[var(--text-4)]'
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        {/* Message */}
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Describe what clarification is needed from the provider or patient..."
          rows={3}
          className="w-full text-xs px-3 py-2 rounded-xl resize-none bg-[var(--elevated)] border border-[var(--border)] text-[var(--text-1)] placeholder-[var(--text-4)] focus:outline-none focus:border-orange-500/50 transition-colors"
        />
        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={onClose}
            className="flex-1 py-2 text-xs font-medium rounded-xl border border-[var(--border)] text-[var(--text-3)] hover:bg-[var(--elevated)] transition-colors"
          >
            Cancel
          </button>
          <button
            disabled={text.length < 5}
            className="flex-1 py-2 text-xs font-medium rounded-xl transition-all disabled:opacity-40"
            style={{ background: 'rgba(249,115,22,0.15)', color: '#fb923c', border: '1px solid rgba(249,115,22,0.4)' }}
          >
            <span className="flex items-center justify-center gap-1.5">
              <Send className="w-3 h-3" />
              Send Request
            </span>
          </button>
        </div>
      </div>
    </motion.div>
  )
}

// ─── Escalation form ──────────────────────────────────────────────────────────

function EscalationForm({ onClose }: { onClose: () => void }) {
  const [reason, setReason] = useState('')
  const [tier, setTier]     = useState<'senior' | 'medical_director' | 'external'>('senior')

  const tiers = [
    { id: 'senior' as const,           label: 'Senior Reviewer',     desc: 'Complex clinical question' },
    { id: 'medical_director' as const, label: 'Medical Director',    desc: 'Policy exception required' },
    { id: 'external' as const,         label: 'External Review',     desc: 'IRO / Independent review' },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.2 }}
      className="overflow-hidden"
    >
      <div className="pt-3 space-y-3">
        {/* Tier selection */}
        <div className="space-y-1.5">
          {tiers.map((t) => (
            <button
              key={t.id}
              onClick={() => setTier(t.id)}
              className={cn(
                'w-full flex items-start gap-3 px-3 py-2 rounded-xl border text-left transition-all',
                tier === t.id
                  ? 'bg-violet-500/10 border-violet-500/40'
                  : 'border-[var(--border)] hover:bg-[var(--elevated)]'
              )}
            >
              <div className={cn(
                'w-3.5 h-3.5 rounded-full border-2 flex-shrink-0 mt-0.5 transition-colors',
                tier === t.id ? 'border-violet-500 bg-violet-500' : 'border-[var(--border)]'
              )} />
              <div>
                <p className={cn('text-[11px] font-medium', tier === t.id ? 'text-violet-400' : 'text-[var(--text-2)]')}>
                  {t.label}
                </p>
                <p className="text-[9px] text-[var(--text-4)]">{t.desc}</p>
              </div>
            </button>
          ))}
        </div>
        {/* Reason */}
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Reason for escalation..."
          rows={2}
          className="w-full text-xs px-3 py-2 rounded-xl resize-none bg-[var(--elevated)] border border-[var(--border)] text-[var(--text-1)] placeholder-[var(--text-4)] focus:outline-none focus:border-violet-500/50 transition-colors"
        />
        <div className="flex gap-2">
          <button
            onClick={onClose}
            className="flex-1 py-2 text-xs font-medium rounded-xl border border-[var(--border)] text-[var(--text-3)] hover:bg-[var(--elevated)] transition-colors"
          >
            Cancel
          </button>
          <button
            disabled={reason.length < 5}
            className="flex-1 py-2 text-xs font-medium rounded-xl transition-all disabled:opacity-40"
            style={{ background: 'rgba(139,92,246,0.15)', color: '#a78bfa', border: '1px solid rgba(139,92,246,0.4)' }}
          >
            <span className="flex items-center justify-center gap-1.5">
              <ArrowUpRight className="w-3 h-3" />
              Escalate
            </span>
          </button>
        </div>
      </div>
    </motion.div>
  )
}

// ─── Confirmation overlay ─────────────────────────────────────────────────────

interface ConfirmationProps {
  type:     DecisionType
  notes:    string
  onBack:   () => void
  onSubmit: () => void
  loading:  boolean
}

function ConfirmationView({ type, notes, onBack, onSubmit, loading }: ConfirmationProps) {
  const cfg = {
    APPROVE:   { label: 'Approve',  color: '#10b981', bg: 'rgba(16,185,129,0.12)', icon: CheckCircle2 },
    DENY:      { label: 'Deny',     color: '#ef4444', bg: 'rgba(239,68,68,0.12)',  icon: XCircle },
    PEND:      { label: 'Pend',     color: '#f59e0b', bg: 'rgba(245,158,11,0.12)',icon: Clock },
    OVERRIDE:  { label: 'Override', color: '#0ea5e9', bg: 'rgba(14,165,233,0.12)',icon: RotateCcw },
    CLARIFY:   { label: 'Request Clarification', color: '#f97316', bg: 'rgba(249,115,22,0.12)', icon: MessageSquare },
    ESCALATE:  { label: 'Escalate', color: '#8b5cf6', bg: 'rgba(139,92,246,0.12)',icon: ArrowUpRight },
  }[type]

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      className="space-y-4"
    >
      <div className="text-center">
        <div
          className="w-12 h-12 rounded-2xl mx-auto flex items-center justify-center mb-2"
          style={{ background: cfg.bg }}
        >
          <cfg.icon style={{ color: cfg.color, width: 24, height: 24 }} />
        </div>
        <p className="text-sm font-semibold text-[var(--text-1)]">Confirm Decision</p>
        <p className="text-[11px] text-[var(--text-4)] mt-0.5">
          You are about to <span style={{ color: cfg.color }} className="font-semibold">{cfg.label}</span> this case
        </p>
      </div>

      {notes && (
        <div
          className="px-3 py-2 rounded-xl text-[11px] text-[var(--text-2)]"
          style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
        >
          {notes}
        </div>
      )}

      <div className="flex gap-2 pt-1">
        <button
          onClick={onBack}
          className="flex-1 py-2.5 text-sm font-medium rounded-xl border border-[var(--border)] text-[var(--text-2)] hover:bg-[var(--elevated)] transition-colors"
        >
          Back
        </button>
        <button
          onClick={onSubmit}
          disabled={loading}
          className="flex-1 py-2.5 text-sm font-semibold rounded-xl transition-all disabled:opacity-60"
          style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.color}50`, boxShadow: loading ? 'none' : `0 0 16px ${cfg.color}30` }}
        >
          {loading ? 'Submitting…' : `Confirm ${cfg.label}`}
        </button>
      </div>
    </motion.div>
  )
}

// ─── Main panel ───────────────────────────────────────────────────────────────

interface Props {
  state: ReviewState
}

export function ReviewerActionsPanel({ state }: Props) {
  const { caseData, auditLog } = state

  const [selectedDecision, setSelectedDecision] = useState<DecisionType | null>(null)
  const [notes,             setNotes]            = useState('')
  const [showClarify,       setShowClarify]      = useState(false)
  const [showEscalate,      setShowEscalate]     = useState(false)
  const [confirming,        setConfirming]        = useState(false)
  const [submitting,        setSubmitting]        = useState(false)
  const [submitted,         setSubmitted]         = useState(false)
  const [recording,         setRecording]        = useState(false)
  const [showAudit,         setShowAudit]         = useState(true)
  const notesRef = useRef<HTMLTextAreaElement>(null)

  const recColor = caseData.ai.recommendation
  const aiCfg = {
    APPROVE:     { color: '#10b981', label: 'Approve',      icon: CheckCircle2 },
    DENY:        { color: '#ef4444', label: 'Deny',         icon: XCircle },
    REQUEST_INFO:{ color: '#f59e0b', label: 'Request Info', icon: AlertTriangle },
    ESCALATE:    { color: '#8b5cf6', label: 'Escalate',     icon: ArrowUpRight },
  }[recColor]

  function handleDecisionSelect(type: DecisionType) {
    setSelectedDecision(selectedDecision === type ? null : type)
    setShowClarify(false)
    setShowEscalate(false)
    setConfirming(false)
    setTimeout(() => notesRef.current?.focus(), 100)
  }

  async function handleSubmit() {
    setSubmitting(true)
    await new Promise((r) => setTimeout(r, 1400))
    setSubmitting(false)
    setSubmitted(true)
  }

  if (submitted) {
    const cfg = DECISIONS.find((d) => d.type === selectedDecision) ?? DECISIONS[0]
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-6">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', stiffness: 200, damping: 16 }}
          className="w-16 h-16 rounded-2xl flex items-center justify-center"
          style={{ background: cfg.bg, boxShadow: `0 0 32px ${cfg.glow}` }}
        >
          <cfg.icon style={{ color: cfg.color, width: 32, height: 32 }} />
        </motion.div>
        <div className="text-center">
          <p className="text-base font-bold text-[var(--text-1)]">Decision Submitted</p>
          <p className="text-xs text-[var(--text-4)] mt-1">
            Case {caseData.caseNumber} has been <span style={{ color: cfg.color }}>{cfg.label.toLowerCase()}d</span>
          </p>
        </div>
        <p className="text-[10px] text-[var(--text-4)] text-center">
          Confirmation sent to provider. Audit log updated.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg)' }}>

      {/* Scrollable content area */}
      <div className="flex-1 overflow-y-auto">

        {/* Patient / Provider info header */}
        <div className="px-4 py-3 border-b border-[var(--border)]" style={{ background: 'var(--surface)' }}>
          <div className="grid grid-cols-2 gap-x-3 gap-y-2">
            {[
              { label: 'Patient',    value: caseData.patient.name },
              { label: 'Member ID',  value: caseData.patient.memberId },
              { label: 'Plan',       value: caseData.patient.plan },
              { label: 'Provider',   value: caseData.provider.name.replace(', MD', '') },
              { label: 'CPT',        value: caseData.procedure.cptCode },
              { label: 'Priority',   value: caseData.priority },
            ].map(({ label, value }) => (
              <div key={label}>
                <p className="text-[8px] text-[var(--text-4)] uppercase tracking-wider">{label}</p>
                <p className="text-[10px] font-medium text-[var(--text-1)] truncate">{value}</p>
              </div>
            ))}
          </div>
        </div>

        {/* AI recommendation banner */}
        <div
          className="mx-4 mt-4 rounded-xl px-3 py-2.5 flex items-center gap-3"
          style={{ background: `${aiCfg.color}10`, border: `1px solid ${aiCfg.color}30` }}
        >
          <aiCfg.icon style={{ color: aiCfg.color, width: 18, height: 18, flexShrink: 0 }} />
          <div className="flex-1">
            <p className="text-[10px] text-[var(--text-4)]">AI Recommendation</p>
            <p className="text-sm font-bold" style={{ color: aiCfg.color }}>{aiCfg.label}</p>
          </div>
          <div className="text-right">
            <p className="text-[9px] text-[var(--text-4)]">Confidence</p>
            <p className="text-sm font-bold tabular-nums" style={{ color: aiCfg.color }}>
              {Math.round(caseData.ai.confidence * 100)}%
            </p>
          </div>
        </div>

        {/* ── Decision buttons ──────────────────────────────────────────── */}
        <div className="px-4 mt-4">
          <p className="text-[9px] text-[var(--text-4)] uppercase tracking-wider font-semibold mb-2">Make Decision</p>

          {/* Primary buttons — Approve / Deny */}
          <div className="grid grid-cols-2 gap-2 mb-2">
            {DECISIONS.filter((d) => d.primary).map((d) => (
              <button
                key={d.type}
                onClick={() => handleDecisionSelect(d.type)}
                className="relative flex flex-col items-center gap-1 py-3 rounded-xl font-semibold text-sm transition-all"
                style={{
                  background:  selectedDecision === d.type ? d.bg : 'var(--elevated)',
                  border:      `1px solid ${selectedDecision === d.type ? d.border : 'var(--border)'}`,
                  color:       selectedDecision === d.type ? d.color : 'var(--text-2)',
                  boxShadow:   selectedDecision === d.type ? `0 0 16px ${d.glow}` : 'none',
                }}
              >
                <d.icon style={{ width: 18, height: 18 }} />
                {d.label}
              </button>
            ))}
          </div>

          {/* Secondary buttons — Pend / Escalate */}
          <div className="grid grid-cols-2 gap-2">
            {DECISIONS.filter((d) => !d.primary).map((d) => (
              <button
                key={d.type}
                onClick={() => handleDecisionSelect(d.type)}
                className="flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-medium transition-all"
                style={{
                  background: selectedDecision === d.type ? d.bg : 'var(--elevated)',
                  border:     `1px solid ${selectedDecision === d.type ? d.border : 'var(--border)'}`,
                  color:      selectedDecision === d.type ? d.color : 'var(--text-3)',
                }}
              >
                <d.icon style={{ width: 13, height: 13 }} />
                {d.label}
              </button>
            ))}
          </div>
        </div>

        {/* Override AI toggle */}
        <div className="px-4 mt-2">
          <button
            onClick={() => handleDecisionSelect('OVERRIDE')}
            className={cn(
              'w-full flex items-center justify-between px-3 py-2 rounded-xl border text-xs font-medium transition-all',
              selectedDecision === 'OVERRIDE'
                ? 'bg-cyan-500/10 border-cyan-500/40 text-cyan-400'
                : 'border-[var(--border)] text-[var(--text-4)] hover:bg-[var(--elevated)]'
            )}
          >
            <span className="flex items-center gap-1.5">
              <RotateCcw className="w-3.5 h-3.5" />
              Override AI Recommendation
            </span>
            {selectedDecision === 'OVERRIDE' && (
              <span className="text-[9px] font-bold text-cyan-400">ACTIVE</span>
            )}
          </button>
        </div>

        {/* ── Notes section ──────────────────────────────────────────────── */}
        <div className="px-4 mt-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <MessageSquare className="w-3 h-3 text-[var(--text-4)]" />
              <p className="text-[9px] text-[var(--text-4)] uppercase tracking-wider font-semibold">Reviewer Notes</p>
            </div>
            <div className="flex items-center gap-1.5">
              {/* Voice note toggle */}
              <button
                onClick={() => setRecording((v) => !v)}
                className={cn(
                  'p-1.5 rounded-lg border transition-all',
                  recording
                    ? 'bg-red-500/15 border-red-500/40 text-red-400'
                    : 'border-[var(--border)] text-[var(--text-4)] hover:bg-[var(--elevated)]'
                )}
                title="Voice note"
              >
                {recording ? (
                  <motion.div animate={{ scale: [1, 1.2, 1] }} transition={{ duration: 1, repeat: Infinity }}>
                    <MicOff className="w-3 h-3" />
                  </motion.div>
                ) : (
                  <Mic className="w-3 h-3" />
                )}
              </button>
              <span className="text-[9px] text-[var(--text-4)] tabular-nums">
                {notes.length}/2000
              </span>
            </div>
          </div>

          {recording && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-2 px-3 py-2 rounded-xl flex items-center gap-2"
              style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)' }}
            >
              <motion.div
                className="w-2 h-2 rounded-full bg-red-500"
                animate={{ opacity: [1, 0.2, 1] }}
                transition={{ duration: 0.8, repeat: Infinity }}
              />
              <span className="text-[10px] text-red-400 font-medium">Recording voice note…</span>
            </motion.div>
          )}

          <textarea
            ref={notesRef}
            value={notes}
            onChange={(e) => setNotes(e.target.value.slice(0, 2000))}
            placeholder={selectedDecision
              ? `Add rationale for ${selectedDecision.toLowerCase()} decision...`
              : 'Enter clinical notes, rationale, or reviewer observations...'
            }
            rows={4}
            className="w-full text-xs px-3 py-2.5 rounded-xl resize-none bg-[var(--elevated)] border border-[var(--border)] text-[var(--text-1)] placeholder-[var(--text-4)] focus:outline-none focus:border-cyan-500/50 transition-colors leading-relaxed"
          />
        </div>

        {/* ── Quick action links ─────────────────────────────────────────── */}
        <div className="px-4 mt-3 space-y-1.5">
          {/* Request Clarification */}
          <div
            className="rounded-xl overflow-hidden border"
            style={{ borderColor: showClarify ? 'rgba(249,115,22,0.4)' : 'var(--border)' }}
          >
            <button
              onClick={() => { setShowClarify((v) => !v); setShowEscalate(false) }}
              className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium transition-colors hover:bg-[var(--elevated)]"
            >
              <span className="flex items-center gap-2 text-[var(--text-3)]">
                <MessageSquare className="w-3.5 h-3.5 text-orange-400" />
                Request Clarification
              </span>
              <motion.div animate={{ rotate: showClarify ? 180 : 0 }} transition={{ duration: 0.2 }}>
                <ChevronDown className="w-3.5 h-3.5 text-[var(--text-4)]" />
              </motion.div>
            </button>
            <AnimatePresence>
              {showClarify && (
                <div className="px-3 pb-3 border-t border-[var(--border)]">
                  <ClarificationForm onClose={() => setShowClarify(false)} />
                </div>
              )}
            </AnimatePresence>
          </div>

          {/* Escalation */}
          <div
            className="rounded-xl overflow-hidden border"
            style={{ borderColor: showEscalate ? 'rgba(139,92,246,0.4)' : 'var(--border)' }}
          >
            <button
              onClick={() => { setShowEscalate((v) => !v); setShowClarify(false) }}
              className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium transition-colors hover:bg-[var(--elevated)]"
            >
              <span className="flex items-center gap-2 text-[var(--text-3)]">
                <ArrowUpRight className="w-3.5 h-3.5 text-violet-400" />
                Escalation Workflow
              </span>
              <motion.div animate={{ rotate: showEscalate ? 180 : 0 }} transition={{ duration: 0.2 }}>
                <ChevronDown className="w-3.5 h-3.5 text-[var(--text-4)]" />
              </motion.div>
            </button>
            <AnimatePresence>
              {showEscalate && (
                <div className="px-3 pb-3 border-t border-[var(--border)]">
                  <EscalationForm onClose={() => setShowEscalate(false)} />
                </div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* ── Audit timeline ─────────────────────────────────────────────── */}
        <div className="px-4 mt-4 mb-4">
          <button
            onClick={() => setShowAudit((v) => !v)}
            className="flex items-center justify-between w-full mb-3"
          >
            <div className="flex items-center gap-1.5">
              <Clipboard className="w-3 h-3 text-[var(--text-4)]" />
              <p className="text-[9px] text-[var(--text-4)] uppercase tracking-wider font-semibold">
                Audit Trail ({auditLog.length})
              </p>
            </div>
            <motion.div animate={{ rotate: showAudit ? 180 : 0 }} transition={{ duration: 0.2 }}>
              <ChevronDown className="w-3.5 h-3.5 text-[var(--text-4)]" />
            </motion.div>
          </button>
          <AnimatePresence>
            {showAudit && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                {auditLog.map((entry, i) => (
                  <AuditItem key={entry.id} entry={entry} isLast={i === auditLog.length - 1} />
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Spacer for sticky footer */}
        <div className="h-20" />
      </div>

      {/* ── Sticky submit footer ──────────────────────────────────────── */}
      <div
        className="flex-shrink-0 px-4 py-3 border-t border-[var(--border)]"
        style={{
          background: 'var(--surface)',
          boxShadow: '0 -4px 20px rgba(0,0,0,0.12)',
        }}
      >
        {confirming && selectedDecision ? (
          <ConfirmationView
            type={selectedDecision}
            notes={notes}
            onBack={() => setConfirming(false)}
            onSubmit={handleSubmit}
            loading={submitting}
          />
        ) : (
          <button
            onClick={() => setConfirming(true)}
            disabled={!selectedDecision}
            className="w-full py-3 rounded-xl text-sm font-bold transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            style={selectedDecision ? (() => {
              const cfg = DECISIONS.find((d) => d.type === selectedDecision)
              return cfg ? {
                background:  cfg.bg,
                color:       cfg.color,
                border:      `1px solid ${cfg.border}`,
                boxShadow:   `0 0 20px ${cfg.glow}`,
              } : {}
            })() : {
              background: 'var(--elevated)',
              color: 'var(--text-4)',
              border: '1px solid var(--border)',
            }}
          >
            {selectedDecision
              ? `Review & Submit ${selectedDecision.charAt(0) + selectedDecision.slice(1).toLowerCase()}`
              : 'Select a decision above'
            }
          </button>
        )}
      </div>
    </div>
  )
}
