import { motion, AnimatePresence } from 'framer-motion'
import {
  FileText, Image, FlaskConical, Stethoscope, ClipboardList,
  CheckCircle2, Clock, AlertTriangle, MinusCircle, ChevronDown, ChevronUp,
} from 'lucide-react'
import { useState } from 'react'
import type { MissingEvidence, EvidenceStatus } from '../hooks/useClarificationManager'

// ─── Config ───────────────────────────────────────────────────────────────────

const TYPE_CFG: Record<string, { color: string; Icon: React.ElementType }> = {
  document:       { color: '#0ea5e9', Icon: FileText },
  lab:            { color: '#10b981', Icon: FlaskConical },
  imaging:        { color: '#8b5cf6', Icon: Image },
  clinical_note:  { color: '#6366f1', Icon: Stethoscope },
  specialist_note:{ color: '#a855f7', Icon: ClipboardList },
}

const STATUS_CFG: Record<EvidenceStatus, { color: string; bg: string; label: string; Icon: React.ElementType }> = {
  received:     { color: '#10b981', bg: '#10b98115', label: 'Received',     Icon: CheckCircle2 },
  pending:      { color: '#f59e0b', bg: '#f59e0b15', label: 'Pending',      Icon: Clock },
  overdue:      { color: '#ef4444', bg: '#ef444415', label: 'Overdue',      Icon: AlertTriangle },
  waived:       { color: '#6b7280', bg: '#6b728015', label: 'Waived',       Icon: MinusCircle },
  not_required: { color: '#6b7280', bg: '#6b728015', label: 'Not Required', Icon: MinusCircle },
}

// ─── Evidence item ────────────────────────────────────────────────────────────

interface ItemProps {
  item:     MissingEvidence
  onMark:   (id: string) => void
}

function EvidenceItem({ item, onMark }: ItemProps) {
  const typeCfg   = TYPE_CFG[item.type] ?? TYPE_CFG.document
  const statusCfg = STATUS_CFG[item.status]
  const { Icon: TypeIcon }   = typeCfg
  const { Icon: StatusIcon } = statusCfg

  const canMark = item.status === 'pending' || item.status === 'overdue'

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      className="flex items-start gap-2.5 px-3 py-2.5 rounded-xl transition-all group"
      style={{
        background: 'var(--elevated)',
        border: `1px solid ${item.status === 'overdue' ? '#ef444430' : item.status === 'received' ? '#10b98120' : 'var(--border)'}`,
        opacity: item.status === 'waived' || item.status === 'not_required' ? 0.55 : 1,
      }}
    >
      {/* Type icon */}
      <div
        className="w-6 h-6 rounded-md flex items-center justify-center shrink-0 mt-0.5"
        style={{ background: `${typeCfg.color}15` }}
      >
        <TypeIcon style={{ color: typeCfg.color, width: 11, height: 11 }} />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-1">
          <span className={`text-[11px] font-semibold leading-tight ${item.status === 'received' ? 'line-through text-[var(--text-4)]' : 'text-[var(--text-1)]'}`}>
            {item.label}
          </span>
          <div
            className="flex items-center gap-1 px-1.5 py-0.5 rounded-md shrink-0"
            style={{ background: statusCfg.bg }}
          >
            <StatusIcon style={{ color: statusCfg.color, width: 8, height: 8 }} />
            <span className="text-[8px] font-bold uppercase tracking-wide" style={{ color: statusCfg.color }}>
              {statusCfg.label}
            </span>
          </div>
        </div>

        <p className="text-[9px] text-[var(--text-4)] mt-0.5 leading-snug">{item.description}</p>

        <div className="flex items-center justify-between mt-1.5">
          <div className="flex items-center gap-2">
            {item.status === 'received' && item.receivedAt && (
              <span className="text-[8px] text-[#10b981]">
                Received {item.receivedAt.toLocaleDateString([], { month: 'short', day: 'numeric' })}
              </span>
            )}
            {(item.status === 'pending' || item.status === 'overdue') && (
              <span className="text-[8px]" style={{ color: item.status === 'overdue' ? '#ef4444' : '#f59e0b' }}>
                {item.daysWaiting}d waiting
              </span>
            )}
            {item.required && item.status !== 'received' && item.status !== 'waived' && (
              <span className="text-[8px] font-bold text-[#ef4444]">Required</span>
            )}
          </div>

          {canMark && (
            <button
              onClick={() => onMark(item.id)}
              className="text-[8px] font-semibold px-2 py-0.5 rounded-md opacity-0 group-hover:opacity-100 transition-all"
              style={{ background: '#10b98115', color: '#10b981', border: '1px solid #10b98130' }}
            >
              Mark received
            </button>
          )}
        </div>
      </div>
    </motion.div>
  )
}

// ─── Summary ring ─────────────────────────────────────────────────────────────

function CompletionRing({ received, total }: { received: number; total: number }) {
  const pct   = total > 0 ? (received / total) * 100 : 0
  const r     = 22
  const circ  = 2 * Math.PI * r
  const dash  = (pct / 100) * circ
  const color = pct === 100 ? '#10b981' : pct >= 60 ? '#f59e0b' : '#ef4444'

  return (
    <div className="relative w-14 h-14 shrink-0">
      <svg viewBox="0 0 52 52" className="w-full h-full -rotate-90">
        <circle cx="26" cy="26" r={r} fill="none" strokeWidth="4" stroke="var(--border)" />
        <motion.circle
          cx="26" cy="26" r={r} fill="none"
          strokeWidth="4" stroke={color}
          strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: circ - dash }}
          transition={{ duration: 1, ease: 'easeOut', delay: 0.2 }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-xs font-bold tabular-nums" style={{ color }}>{received}</span>
        <span className="text-[7px] text-[var(--text-4)]">/{total}</span>
      </div>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  evidence: MissingEvidence[]
  onMark:   (id: string) => void
}

export function MissingEvidenceTracker({ evidence, onMark }: Props) {
  const [collapsed, setCollapsed] = useState(false)

  const required   = evidence.filter((e) => e.required)
  const received   = required.filter((e) => e.status === 'received' || e.status === 'waived').length
  const total      = required.length
  const overdue    = evidence.filter((e) => e.status === 'overdue').length
  const pending    = evidence.filter((e) => e.status === 'pending').length

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 border-b border-[var(--border)] cursor-pointer"
        style={{ background: 'var(--elevated)' }}
        onClick={() => setCollapsed((v) => !v)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CompletionRing received={received} total={total} />
            <div>
              <span className="text-xs font-bold text-[var(--text-1)]">Missing Evidence</span>
              <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                {overdue > 0 && (
                  <span className="text-[8px] font-bold px-1.5 py-0.5 rounded-full bg-[#ef444415] text-[#ef4444]">
                    {overdue} overdue
                  </span>
                )}
                {pending > 0 && (
                  <span className="text-[8px] font-bold px-1.5 py-0.5 rounded-full bg-[#f59e0b15] text-[#f59e0b]">
                    {pending} pending
                  </span>
                )}
                {received === total && (
                  <span className="text-[8px] font-bold px-1.5 py-0.5 rounded-full bg-[#10b98115] text-[#10b981]">
                    All received
                  </span>
                )}
              </div>
            </div>
          </div>
          {collapsed
            ? <ChevronDown className="w-4 h-4 text-[var(--text-4)]" />
            : <ChevronUp   className="w-4 h-4 text-[var(--text-4)]" />
          }
        </div>
      </div>

      {/* Item list */}
      <AnimatePresence initial={false}>
        {!collapsed && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="p-3 space-y-1.5">
              {/* Required items first */}
              {required.map((item) => (
                <EvidenceItem key={item.id} item={item} onMark={onMark} />
              ))}
              {/* Optional items */}
              {evidence.filter((e) => !e.required).length > 0 && (
                <>
                  <p className="text-[9px] text-[var(--text-4)] uppercase tracking-widest font-bold pt-1 pl-1">
                    Optional
                  </p>
                  {evidence.filter((e) => !e.required).map((item) => (
                    <EvidenceItem key={item.id} item={item} onMark={onMark} />
                  ))}
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
