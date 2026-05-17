import { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  User, Stethoscope, Code2, BookMarked, Pill,
  FlaskConical, Droplets, TrendingUp,
  CheckCircle2, XCircle, Edit3, RotateCcw,
  ChevronDown, AlertTriangle, Cpu, ExternalLink,
  ThumbsUp, ThumbsDown,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ExtractionCardData, ExtractionField, VerificationState, FieldSource } from '../hooks/useDocumentIntelligence'

// ─── Icon map ─────────────────────────────────────────────────────────────────

const CARD_ICONS: Record<string, React.ElementType> = {
  User, Stethoscope, Code2, BookMarked, Pill, FlaskConical, Droplets, TrendingUp,
}

// ─── Source badge ─────────────────────────────────────────────────────────────

const SOURCE_CFG: Record<FieldSource, { label: string; color: string; bg: string }> = {
  ocr_direct:    { label: 'OCR',       color: '#0ea5e9', bg: 'rgba(14,165,233,0.12)'  },
  ai_inferred:   { label: 'AI',        color: '#8b5cf6', bg: 'rgba(139,92,246,0.12)'  },
  pattern_match: { label: 'Pattern',   color: '#10b981', bg: 'rgba(16,185,129,0.12)'  },
  calculated:    { label: 'Computed',  color: '#f59e0b', bg: 'rgba(245,158,11,0.12)'  },
}

function SourceBadge({ source }: { source: FieldSource }) {
  const cfg = SOURCE_CFG[source]
  return (
    <span
      className="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider"
      style={{ background: cfg.bg, color: cfg.color }}
    >
      {cfg.label}
    </span>
  )
}

// ─── Confidence pip ───────────────────────────────────────────────────────────

function ConfidencePip({ value }: { value: number }) {
  const pct   = Math.round(value * 100)
  const color = pct >= 90 ? '#10b981' : pct >= 75 ? '#f59e0b' : '#ef4444'
  return (
    <div className="flex items-center gap-1">
      <div className="flex gap-0.5">
        {[0, 1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="w-1 h-2.5 rounded-sm"
            style={{ background: i < Math.ceil(pct / 20) ? color : 'var(--border)' }}
          />
        ))}
      </div>
      <span className="text-[9px] font-mono tabular-nums" style={{ color }}>{pct}%</span>
    </div>
  )
}

// ─── Status dot ───────────────────────────────────────────────────────────────

function StatusDot({ status }: { status?: 'normal' | 'abnormal' | 'critical' }) {
  if (!status) return null
  const cfg = {
    normal:   { color: '#10b981', label: 'Normal' },
    abnormal: { color: '#f59e0b', label: 'Abnormal' },
    critical: { color: '#ef4444', label: 'Critical' },
  }[status]
  return (
    <span
      className="text-[8px] font-bold px-1.5 py-0.5 rounded-full"
      style={{ background: `${cfg.color}15`, color: cfg.color }}
    >
      {cfg.label}
    </span>
  )
}

// ─── Trend arrow ─────────────────────────────────────────────────────────────

function TrendArrow({ trend }: { trend?: 'up' | 'down' | 'stable' }) {
  if (!trend) return null
  const map = { up: '↑', down: '↓', stable: '→' }
  const color = { up: '#f59e0b', down: '#10b981', stable: '#6b7280' }[trend]
  return <span className="font-bold" style={{ color }}>{map[trend]}</span>
}

// ─── OCR diff view ────────────────────────────────────────────────────────────

function OCRDiff({ raw, corrected }: { raw: string; corrected: string }) {
  return (
    <div className="mt-1 space-y-1">
      <div className="flex items-center gap-1.5 text-[9px]">
        <span className="text-[var(--text-4)]">OCR raw:</span>
        <span className="font-mono line-through text-red-400 opacity-70">{raw}</span>
      </div>
      <div className="flex items-center gap-1.5 text-[9px]">
        <span className="text-[var(--text-4)]">Corrected:</span>
        <span className="font-mono text-emerald-400">{corrected}</span>
      </div>
    </div>
  )
}

// ─── Inline editor ────────────────────────────────────────────────────────────

interface InlineEditorProps {
  field:    ExtractionField
  onSave:   (value: string) => void
  onCancel: () => void
}

function InlineEditor({ field, onSave, onCancel }: InlineEditorProps) {
  const [val, setVal] = useState(field.correction ?? field.value)
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <div className="flex items-center gap-1.5 mt-1">
      <input
        ref={inputRef}
        autoFocus
        value={val}
        onChange={(e) => setVal(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') onSave(val)
          if (e.key === 'Escape') onCancel()
        }}
        className="flex-1 text-xs px-2 py-1 rounded-lg bg-[var(--elevated)] border border-cyan-500/50 text-[var(--text-1)] focus:outline-none font-mono"
      />
      <button onClick={() => onSave(val)} className="p-1 rounded-lg bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 transition-colors">
        <CheckCircle2 className="w-3.5 h-3.5" />
      </button>
      <button onClick={onCancel} className="p-1 rounded-lg bg-[var(--elevated)] text-[var(--text-4)] hover:text-[var(--text-2)] transition-colors">
        <XCircle className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}

// ─── Field row ────────────────────────────────────────────────────────────────

interface FieldRowProps {
  field:    ExtractionField
  onVerify: (state: VerificationState, correction?: string) => void
}

function FieldRow({ field, onVerify }: FieldRowProps) {
  const [editing, setEditing] = useState(false)
  const [showOCR, setShowOCR] = useState(false)

  const verState = field.verified
  const hasOCRDiff = field.rawOCR && field.rawOCR !== field.value

  const rowBg =
    verState === 'confirmed' ? 'rgba(16,185,129,0.05)' :
    verState === 'corrected' ? 'rgba(14,165,233,0.05)' :
    verState === 'rejected'  ? 'rgba(239,68,68,0.05)'  :
    'transparent'

  return (
    <motion.div
      layout
      className="group relative px-3 py-2.5 rounded-xl transition-colors hover:bg-[var(--elevated)]"
      style={{ background: rowBg }}
    >
      <div className="flex items-start gap-2">
        {/* Verification state indicator */}
        <div className="w-1 self-stretch rounded-full flex-shrink-0 mt-0.5" style={{
          background:
            verState === 'confirmed' ? '#10b981' :
            verState === 'corrected' ? '#0ea5e9' :
            verState === 'rejected'  ? '#ef4444' :
            'var(--border)',
          minHeight: 12,
        }} />

        <div className="flex-1 min-w-0">
          {/* Label + source */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[9px] text-[var(--text-4)] font-medium uppercase tracking-wider">
              {field.label}
            </span>
            <SourceBadge source={field.source} />
            {hasOCRDiff && (
              <button
                onClick={() => setShowOCR((v) => !v)}
                className="text-[8px] text-amber-400 hover:text-amber-300 transition-colors flex items-center gap-0.5"
              >
                <AlertTriangle className="w-2.5 h-2.5" />
                OCR diff
              </button>
            )}
          </div>

          {/* Value */}
          {editing ? (
            <InlineEditor
              field={field}
              onSave={(val) => { onVerify('corrected', val); setEditing(false) }}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <div className="flex items-center gap-2 mt-0.5 flex-wrap">
              <span className="text-xs font-semibold text-[var(--text-1)]">
                {field.correction ?? field.value}
                {field.unit && <span className="text-[var(--text-4)] font-normal ml-1">{field.unit}</span>}
              </span>
              <TrendArrow trend={field.trend} />
              <StatusDot status={field.status} />
              {field.referenceRange && (
                <span className="text-[8px] text-[var(--text-4)]">Ref: {field.referenceRange}</span>
              )}
            </div>
          )}

          {/* OCR diff */}
          {showOCR && hasOCRDiff && (
            <OCRDiff raw={field.rawOCR!} corrected={field.value} />
          )}

          {/* Confidence */}
          <div className="mt-1">
            <ConfidencePip value={field.confidence} />
          </div>
        </div>

        {/* Action buttons — revealed on hover */}
        {!editing && (
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
            {verState !== 'confirmed' && (
              <button
                onClick={() => onVerify('confirmed')}
                className="p-1 rounded-lg transition-colors hover:bg-emerald-500/15"
                title="Confirm"
              >
                <ThumbsUp className="w-3 h-3 text-emerald-500" />
              </button>
            )}
            <button
              onClick={() => setEditing(true)}
              className="p-1 rounded-lg transition-colors hover:bg-cyan-500/15"
              title="Edit"
            >
              <Edit3 className="w-3 h-3 text-cyan-400" />
            </button>
            {verState !== 'rejected' && (
              <button
                onClick={() => onVerify('rejected')}
                className="p-1 rounded-lg transition-colors hover:bg-red-500/15"
                title="Reject"
              >
                <ThumbsDown className="w-3 h-3 text-red-400" />
              </button>
            )}
            {verState !== null && (
              <button
                onClick={() => onVerify(null)}
                className="p-1 rounded-lg transition-colors hover:bg-[var(--elevated)]"
                title="Reset"
              >
                <RotateCcw className="w-3 h-3 text-[var(--text-4)]" />
              </button>
            )}
          </div>
        )}
      </div>
    </motion.div>
  )
}

// ─── Card header stats ────────────────────────────────────────────────────────

function CompletionRing({ completeness, color }: { completeness: number; color: string }) {
  const size = 36
  const r    = (size - 4) / 2
  const c    = 2 * Math.PI * r
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--border)" strokeWidth={3} />
        <motion.circle
          cx={size/2} cy={size/2} r={r}
          fill="none" stroke={color} strokeWidth={3} strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c - c * completeness }}
          transition={{ duration: 0.7, ease: 'easeOut' }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-[8px] font-bold" style={{ color }}>
          {Math.round(completeness * 100)}%
        </span>
      </div>
    </div>
  )
}

// ─── Extraction card ──────────────────────────────────────────────────────────

interface CardProps {
  card:      ExtractionCardData
  onVerify:  (cardId: string, fieldId: string, state: VerificationState, correction?: string) => void
  isActive:  boolean
  onActivate: () => void
}

function ExtractionCard({ card, onVerify, isActive, onActivate }: CardProps) {
  const [expanded, setExpanded] = useState(true)
  const Icon = CARD_ICONS[card.iconKey] ?? User

  const confirmed = card.fields.filter((f) => f.verified === 'confirmed').length
  const corrected = card.fields.filter((f) => f.verified === 'corrected').length
  const rejected  = card.fields.filter((f) => f.verified === 'rejected').length
  const pending   = card.fields.filter((f) => f.verified === null).length

  const allReviewed = pending === 0

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 16, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className={cn(
        'rounded-2xl overflow-hidden transition-shadow',
        isActive ? 'shadow-xl' : 'shadow-sm hover:shadow-md',
      )}
      style={{
        background: 'var(--surface)',
        border: `1px solid ${isActive ? card.color + '50' : 'var(--border)'}`,
        boxShadow: isActive ? `0 0 0 1px ${card.color}30, 0 8px 32px ${card.color}15` : undefined,
      }}
    >
      {/* Color bar */}
      <div className="h-0.5" style={{ background: card.color }} />

      {/* Header */}
      <button
        onClick={() => { onActivate(); setExpanded((v) => !v) }}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-[var(--elevated)] transition-colors"
      >
        <div
          className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{ background: `${card.color}18` }}
        >
          <Icon style={{ color: card.color, width: 16, height: 16 }} />
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-[var(--text-1)]">{card.title}</p>
          <p className="text-[9px] text-[var(--text-4)] mt-0.5">
            {card.foundFields}/{card.expectedFields} fields · {Math.round(card.overallConfidence * 100)}% conf
          </p>
        </div>

        {/* Mini review stats */}
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {allReviewed && (
            <motion.span
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="text-[9px] font-bold px-2 py-0.5 rounded-full"
              style={{ background: 'rgba(16,185,129,0.12)', color: '#10b981' }}
            >
              ✓ Done
            </motion.span>
          )}
          <CompletionRing completeness={card.completeness} color={card.color} />
          <motion.div
            animate={{ rotate: expanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
          >
            <ChevronDown className="w-4 h-4 text-[var(--text-4)]" />
          </motion.div>
        </div>
      </button>

      {/* Review status bar */}
      {(confirmed + corrected + rejected) > 0 && (
        <div className="px-4 py-1.5 border-t border-[var(--border)] flex items-center gap-3">
          {confirmed > 0 && (
            <span className="text-[9px] text-emerald-400 flex items-center gap-1">
              <ThumbsUp className="w-2.5 h-2.5" />{confirmed}
            </span>
          )}
          {corrected > 0 && (
            <span className="text-[9px] text-cyan-400 flex items-center gap-1">
              <Edit3 className="w-2.5 h-2.5" />{corrected}
            </span>
          )}
          {rejected > 0 && (
            <span className="text-[9px] text-red-400 flex items-center gap-1">
              <ThumbsDown className="w-2.5 h-2.5" />{rejected}
            </span>
          )}
          {pending > 0 && (
            <span className="text-[9px] text-[var(--text-4)]">{pending} pending</span>
          )}
        </div>
      )}

      {/* Expandable fields */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="border-t border-[var(--border)] px-2 py-2 space-y-0.5">
              {card.fields.map((field) => (
                <FieldRow
                  key={field.id}
                  field={field}
                  onVerify={(state, correction) => onVerify(card.id, field.id, state, correction)}
                />
              ))}
            </div>

            {/* Card footer */}
            <div className="px-4 py-2 border-t border-[var(--border)] flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Cpu className="w-3 h-3 text-[var(--text-4)]" />
                <span className="text-[9px] text-[var(--text-4)]">
                  AI extraction · {card.fields.filter((f) => f.source === 'ai_inferred').length} inferred
                </span>
              </div>
              <button className="flex items-center gap-1 text-[9px] text-[var(--text-4)] hover:text-[var(--text-2)] transition-colors">
                <ExternalLink className="w-2.5 h-2.5" />
                View in document
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// ─── Bulk action bar ──────────────────────────────────────────────────────────

function BulkActionBar({
  cards, onBulkVerify,
}: {
  cards: ExtractionCardData[]
  onBulkVerify: (cardId: string, fieldId: string, state: VerificationState) => void
}) {
  const totalFields = cards.reduce((s, c) => s + c.fields.length, 0)
  const verified    = cards.reduce((s, c) => s + c.fields.filter((f) => f.verified !== null).length, 0)
  const highConf    = cards.reduce((s, c) => s + c.fields.filter((f) => f.confidence >= 0.95).length, 0)

  return (
    <div
      className="flex items-center gap-3 px-4 py-3 rounded-2xl flex-wrap"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      <div>
        <p className="text-sm font-semibold text-[var(--text-1)]">
          {verified}/{totalFields} fields reviewed
        </p>
        <p className="text-[10px] text-[var(--text-4)]">{highConf} high-confidence fields eligible for auto-confirm</p>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <button
          onClick={() => {
            cards.forEach((card) =>
              card.fields.filter((f) => f.confidence >= 0.95 && f.verified === null)
                .forEach((f) => onBulkVerify(card.id, f.id, 'confirmed'))
            )
          }}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-all"
          style={{ background: 'rgba(16,185,129,0.12)', color: '#10b981', border: '1px solid rgba(16,185,129,0.3)' }}
        >
          <ThumbsUp className="w-3 h-3" />
          Auto-confirm high confidence
        </button>
        <button
          onClick={() => {
            cards.forEach((card) =>
              card.fields.filter((f) => f.verified === null)
                .forEach((f) => onBulkVerify(card.id, f.id, 'confirmed'))
            )
          }}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium border border-[var(--border)] text-[var(--text-3)] hover:bg-[var(--elevated)] transition-all"
        >
          Accept all
        </button>
      </div>
    </div>
  )
}

// ─── Main export ──────────────────────────────────────────────────────────────

interface Props {
  cards:       ExtractionCardData[]
  activeCardId: string | null
  onSetActive: (id: string | null) => void
  onVerify:    (cardId: string, fieldId: string, state: VerificationState, correction?: string) => void
}

export function ExtractionCards({ cards, activeCardId, onSetActive, onVerify }: Props) {
  if (cards.length === 0) return null

  return (
    <div className="space-y-4">
      <BulkActionBar cards={cards} onBulkVerify={onVerify} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {cards.map((card) => (
          <ExtractionCard
            key={card.id}
            card={card}
            isActive={activeCardId === card.id}
            onActivate={() => onSetActive(activeCardId === card.id ? null : card.id)}
            onVerify={onVerify}
          />
        ))}
      </div>
    </div>
  )
}
