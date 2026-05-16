import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  CheckCircle2, XCircle, AlertTriangle, MinusCircle,
  ChevronDown, ExternalLink, Shield, Brain, Sparkles,
  BookOpen, Link2, Activity, Search, GitBranch,
} from 'lucide-react'
import type { ReviewState, PolicyCriterion, Evidence, ReasoningStep, CriterionStatus } from '../hooks/useCaseReviewData'

// ─── Status config ────────────────────────────────────────────────────────────

const STATUS_CFG: Record<CriterionStatus, {
  icon:    React.ElementType
  color:   string
  bg:      string
  border:  string
  label:   string
  barColor: string
}> = {
  MET: {
    icon: CheckCircle2, label: 'PASS',
    color: '#10b981', bg: 'rgba(16,185,129,0.1)', border: 'rgba(16,185,129,0.25)', barColor: '#10b981',
  },
  NOT_MET: {
    icon: XCircle, label: 'FAIL',
    color: '#ef4444', bg: 'rgba(239,68,68,0.1)', border: 'rgba(239,68,68,0.25)', barColor: '#ef4444',
  },
  INSUFFICIENT: {
    icon: AlertTriangle, label: 'INSUFFICIENT',
    color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', border: 'rgba(245,158,11,0.25)', barColor: '#f59e0b',
  },
  NOT_APPLICABLE: {
    icon: MinusCircle, label: 'N/A',
    color: '#6b7280', bg: 'rgba(107,114,128,0.1)', border: 'rgba(107,114,128,0.2)', barColor: '#6b7280',
  },
}

const STEP_CFG: Record<ReasoningStep['type'], { icon: React.ElementType; color: string }> = {
  retrieve: { icon: Search,     color: '#0ea5e9' },
  compare:  { icon: GitBranch,  color: '#8b5cf6' },
  evaluate: { icon: Activity,   color: '#f59e0b' },
  conclude: { icon: CheckCircle2, color: '#10b981' },
}

// ─── Hallucination badge ──────────────────────────────────────────────────────

function HallucinationBadge({ risk }: { risk: 'LOW' | 'MEDIUM' | 'HIGH' }) {
  const cfg = {
    LOW:    { color: '#10b981', bg: 'rgba(16,185,129,0.12)',  label: 'Grounded' },
    MEDIUM: { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', label: 'Review' },
    HIGH:   { color: '#ef4444', bg: 'rgba(239,68,68,0.12)',  label: 'Flagged' },
  }[risk]
  return (
    <div
      className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-semibold"
      style={{ background: cfg.bg, color: cfg.color }}
      title={`Hallucination risk: ${risk}`}
    >
      <Shield className="w-2.5 h-2.5" />
      {cfg.label}
    </div>
  )
}

// ─── Confidence meter ─────────────────────────────────────────────────────────

function ConfidenceMeter({ value, animate: doAnimate = true }: { value: number; animate?: boolean }) {
  const pct   = Math.round(value * 100)
  const color = pct >= 85 ? '#10b981' : pct >= 65 ? '#f59e0b' : '#ef4444'
  const bars  = 10
  const filled = Math.round((pct / 100) * bars)

  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-0.5">
        {Array.from({ length: bars }, (_, i) => (
          <motion.div
            key={i}
            initial={doAnimate ? { scaleY: 0 } : false}
            animate={{ scaleY: 1 }}
            transition={{ delay: i * 0.04, duration: 0.2 }}
            className="w-1.5 rounded-sm"
            style={{
              height: 8 + (i < filled ? 4 : 0),
              background: i < filled ? color : 'var(--border)',
              opacity: i < filled ? 1 : 0.4,
            }}
          />
        ))}
      </div>
      <span className="text-[11px] font-bold tabular-nums" style={{ color }}>
        {pct}%
      </span>
    </div>
  )
}

// ─── Grounding indicator ──────────────────────────────────────────────────────

function GroundingScore({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = pct >= 90 ? '#0ea5e9' : pct >= 75 ? '#8b5cf6' : '#f59e0b'
  return (
    <div className="flex items-center gap-1.5">
      <Link2 className="w-3 h-3" style={{ color }} />
      <div className="flex-1 h-1 rounded-full bg-[var(--border)] overflow-hidden w-16">
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      </div>
      <span className="text-[9px] tabular-nums font-mono" style={{ color }}>
        {pct}% grounded
      </span>
    </div>
  )
}

// ─── Evidence card ────────────────────────────────────────────────────────────

function EvidenceItem({ ev, onHighlight, onClearHighlight, onJumpToPage }: {
  ev:               Evidence
  onHighlight:      (ids: string[]) => void
  onClearHighlight: () => void
  onJumpToPage:     (n: number) => void
}) {
  return (
    <motion.div
      whileHover={{ scale: 1.01 }}
      onMouseEnter={() => ev.entityId && onHighlight([ev.entityId])}
      onMouseLeave={onClearHighlight}
      onClick={() => onJumpToPage(ev.pageIndex)}
      className="group relative px-3 py-2.5 rounded-xl cursor-pointer transition-colors"
      style={{
        background: 'var(--elevated)',
        border: '1px solid var(--border)',
      }}
    >
      <div className="flex items-start gap-2">
        <div
          className="w-1 self-stretch rounded-full flex-shrink-0 mt-0.5"
          style={{ background: '#0ea5e9', minHeight: 12 }}
        />
        <div className="flex-1 min-w-0">
          <blockquote className="text-[11px] text-[var(--text-2)] leading-relaxed italic">
            "{ev.text}"
          </blockquote>
          <div className="flex items-center gap-2 mt-1.5">
            <span className="text-[9px] text-[var(--text-4)] font-medium">{ev.source}</span>
            <button
              onClick={(e) => { e.stopPropagation(); onJumpToPage(ev.pageIndex) }}
              className="flex items-center gap-0.5 text-[9px] text-cyan-400 hover:text-cyan-300 transition-colors opacity-0 group-hover:opacity-100"
            >
              <ExternalLink className="w-2.5 h-2.5" />
              View
            </button>
          </div>
        </div>
        <div className="text-[9px] font-mono text-[var(--text-4)] flex-shrink-0">
          {Math.round(ev.confidence * 100)}%
        </div>
      </div>
    </motion.div>
  )
}

// ─── Reasoning trace ──────────────────────────────────────────────────────────

function ReasoningTrace({ steps }: { steps: ReasoningStep[] }) {
  return (
    <div className="space-y-1.5">
      {steps.map((step) => {
        const cfg = STEP_CFG[step.type]
        return (
          <div key={step.step} className="flex items-start gap-2.5">
            <div
              className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
              style={{ background: `${cfg.color}18` }}
            >
              <cfg.icon style={{ color: cfg.color, width: 10, height: 10 }} />
            </div>
            <p className="text-[11px] text-[var(--text-3)] leading-relaxed flex-1">{step.text}</p>
          </div>
        )
      })}
    </div>
  )
}

// ─── Criterion card ───────────────────────────────────────────────────────────

interface CriterionCardProps {
  criterion:        PolicyCriterion
  expanded:         boolean
  onToggle:         () => void
  onEvidenceHover:  (ids: string[]) => void
  onClearHighlight: () => void
  onJumpToPage:     (n: number) => void
}

function CriterionCard({
  criterion, expanded, onToggle, onEvidenceHover, onClearHighlight, onJumpToPage,
}: CriterionCardProps) {
  const cfg = STATUS_CFG[criterion.status]
  const [showTrace, setShowTrace] = useState(false)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl overflow-hidden"
      style={{
        background: 'var(--surface)',
        border: `1px solid var(--border)`,
        boxShadow: expanded ? '0 4px 24px rgba(0,0,0,0.12)' : 'none',
      }}
    >
      {/* Status bar accent */}
      <div className="h-0.5 w-full" style={{ background: cfg.barColor }} />

      {/* Header — always visible */}
      <button
        onClick={onToggle}
        className="w-full flex items-start gap-3 px-4 py-3.5 text-left hover:bg-[var(--elevated)] transition-colors"
      >
        {/* Status icon */}
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
          style={{ background: cfg.bg, border: `1px solid ${cfg.border}` }}
        >
          <cfg.icon style={{ color: cfg.color, width: 15, height: 15 }} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className="text-[10px] font-bold tracking-wide"
              style={{ color: cfg.color }}
            >
              {cfg.label}
            </span>
            <span className="text-[10px] text-[var(--text-4)] font-mono">{criterion.policyRef}</span>
          </div>
          <p className="text-[12px] font-medium text-[var(--text-1)] mt-0.5 leading-snug">
            {criterion.requirement}
          </p>
          {/* Compact confidence */}
          {!expanded && (
            <div className="mt-2">
              <ConfidenceMeter value={criterion.confidence} animate={false} />
            </div>
          )}
        </div>

        {/* Expand chevron */}
        <motion.div
          animate={{ rotate: expanded ? 180 : 0 }}
          transition={{ duration: 0.2 }}
          className="flex-shrink-0 mt-1"
        >
          <ChevronDown className="w-4 h-4 text-[var(--text-4)]" />
        </motion.div>
      </button>

      {/* Expanded body */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 space-y-4 border-t border-[var(--border)]">

              {/* Confidence + grounding row */}
              <div className="flex items-center justify-between pt-3 flex-wrap gap-3">
                <div>
                  <p className="text-[9px] text-[var(--text-4)] uppercase tracking-wider mb-1.5">AI Confidence</p>
                  <ConfidenceMeter value={criterion.confidence} />
                </div>
                <div>
                  <p className="text-[9px] text-[var(--text-4)] uppercase tracking-wider mb-1.5">Grounding</p>
                  <GroundingScore score={criterion.groundingScore} />
                </div>
                <HallucinationBadge risk={criterion.hallucinationRisk} />
              </div>

              {/* AI Rationale */}
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <Brain className="w-3 h-3 text-violet-400" />
                  <p className="text-[9px] text-[var(--text-4)] uppercase tracking-wider font-semibold">AI Rationale</p>
                </div>
                <p className="text-[11px] text-[var(--text-2)] leading-relaxed">
                  {criterion.rationale}
                </p>
              </div>

              {/* Evidence */}
              {criterion.evidence.length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 mb-2">
                    <BookOpen className="w-3 h-3 text-cyan-400" />
                    <p className="text-[9px] text-[var(--text-4)] uppercase tracking-wider font-semibold">
                      Evidence ({criterion.evidence.length})
                    </p>
                    <span className="text-[9px] text-[var(--text-4)]">· click to view in document</span>
                  </div>
                  <div className="space-y-2">
                    {criterion.evidence.map((ev) => (
                      <EvidenceItem
                        key={ev.id}
                        ev={ev}
                        onHighlight={onEvidenceHover}
                        onClearHighlight={onClearHighlight}
                        onJumpToPage={onJumpToPage}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Reasoning trace toggle */}
              <div>
                <button
                  onClick={() => setShowTrace((v) => !v)}
                  className="flex items-center gap-1.5 text-[10px] text-[var(--text-4)] hover:text-[var(--text-2)] transition-colors"
                >
                  <Sparkles className="w-3 h-3 text-violet-400" />
                  {showTrace ? 'Hide' : 'Show'} reasoning trace
                  <motion.span animate={{ rotate: showTrace ? 180 : 0 }} transition={{ duration: 0.2 }}>
                    <ChevronDown className="w-3 h-3" />
                  </motion.span>
                </button>
                <AnimatePresence>
                  {showTrace && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      className="overflow-hidden mt-3"
                    >
                      <div
                        className="p-3 rounded-xl"
                        style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
                      >
                        <ReasoningTrace steps={criterion.reasoningSteps} />
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// ─── Summary bar ──────────────────────────────────────────────────────────────

function SummaryBar({ criteria, aiConf }: {
  criteria: PolicyCriterion[]; aiConf: number
}) {
  const met   = criteria.filter((c) => c.status === 'MET').length
  const na    = criteria.filter((c) => c.status === 'NOT_APPLICABLE').length
  const total = criteria.length - na
  const pct   = total > 0 ? Math.round((met / total) * 100) : 0

  return (
    <div
      className="px-4 py-3 border-b border-[var(--border)] flex items-center gap-4"
      style={{ background: 'var(--surface)' }}
    >
      {/* Score */}
      <div className="flex items-center gap-2">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold"
          style={{ background: 'rgba(16,185,129,0.15)', color: '#10b981' }}
        >
          {met}/{total}
        </div>
        <div>
          <p className="text-[10px] text-[var(--text-4)]">Criteria Met</p>
          <div className="flex items-center gap-1 mt-0.5">
            <div className="w-20 h-1.5 rounded-full bg-[var(--border)] overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-emerald-500"
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.8, ease: 'easeOut' }}
              />
            </div>
            <span className="text-[9px] text-emerald-400 font-mono">{pct}%</span>
          </div>
        </div>
      </div>

      <div className="w-px h-8 bg-[var(--border)]" />

      {/* AI overall confidence */}
      <div>
        <p className="text-[10px] text-[var(--text-4)]">AI Confidence</p>
        <p className="text-sm font-bold text-violet-400 tabular-nums">{Math.round(aiConf * 100)}%</p>
      </div>

      <div className="w-px h-8 bg-[var(--border)]" />

      {/* Status counts */}
      <div className="flex items-center gap-3">
        {[
          { status: 'MET' as CriterionStatus, cnt: criteria.filter((c) => c.status === 'MET').length },
          { status: 'NOT_MET' as CriterionStatus, cnt: criteria.filter((c) => c.status === 'NOT_MET').length },
          { status: 'INSUFFICIENT' as CriterionStatus, cnt: criteria.filter((c) => c.status === 'INSUFFICIENT').length },
          { status: 'NOT_APPLICABLE' as CriterionStatus, cnt: criteria.filter((c) => c.status === 'NOT_APPLICABLE').length },
        ].filter((x) => x.cnt > 0).map(({ status, cnt }) => {
          const cfg = STATUS_CFG[status]
          return (
            <div key={status} className="flex items-center gap-1">
              <cfg.icon style={{ color: cfg.color, width: 11, height: 11 }} />
              <span className="text-[10px] font-bold tabular-nums" style={{ color: cfg.color }}>{cnt}</span>
              <span className="text-[9px] text-[var(--text-4)]">{cfg.label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Main panel ───────────────────────────────────────────────────────────────

interface Props {
  state: ReviewState
}

export function AIReasoningPanel({ state }: Props) {
  const {
    criteria, caseData, entities,
    expandedCriterionIds,
    toggleCriterion, setActiveCriterion,
    highlightEntity, clearHighlight, setPage,
  } = state

  function handleEvidenceHover(entityIds: string[]) {
    highlightEntity(entityIds)
  }

  function handleJumpToPage(pageIndex: number) {
    setPage(pageIndex)
  }

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg)' }}>

      {/* Panel header */}
      <div
        className="px-4 py-3 border-b border-[var(--border)] flex-shrink-0"
        style={{ background: 'var(--surface)' }}
      >
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: 'rgba(139,92,246,0.15)' }}>
            <Brain className="w-4 h-4 text-violet-400" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-[var(--text-1)]">AI Reasoning Engine</h2>
            <p className="text-[10px] text-[var(--text-4)]">{caseData.ai.modelVersion}</p>
          </div>
          <div className="ml-auto flex items-center gap-1.5 px-2 py-1 rounded-lg" style={{ background: 'rgba(16,185,129,0.1)' }}>
            <motion.div
              className="w-1.5 h-1.5 rounded-full bg-emerald-400"
              animate={{ opacity: [1, 0.4, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
            <span className="text-[9px] font-medium text-emerald-400">Processing complete</span>
          </div>
        </div>
      </div>

      {/* Summary bar */}
      <SummaryBar criteria={criteria} aiConf={caseData.ai.confidence} />

      {/* Criteria list */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {criteria.map((criterion) => (
          <CriterionCard
            key={criterion.id}
            criterion={criterion}
            expanded={expandedCriterionIds.has(criterion.id)}
            onToggle={() => {
              toggleCriterion(criterion.id)
              setActiveCriterion(criterion.id)
            }}
            onEvidenceHover={(entityIds) => {
              // Also find which entities from the document match
              const relatedEntityIds = entities
                .filter((e) => e.criterionIds.includes(criterion.id))
                .map((e) => e.id)
              handleEvidenceHover([...new Set([...entityIds, ...relatedEntityIds])])
            }}
            onClearHighlight={clearHighlight}
            onJumpToPage={handleJumpToPage}
          />
        ))}

        {/* Footer note */}
        <div
          className="rounded-xl p-3 flex items-start gap-2.5"
          style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
        >
          <Shield className="w-4 h-4 text-cyan-400 flex-shrink-0 mt-0.5" />
          <p className="text-[10px] text-[var(--text-4)] leading-relaxed">
            AI recommendations are decision-support tools only. Final authorization decisions remain with the licensed reviewer. All reasoning is fully auditable and grounded in retrieved policy documents.
          </p>
        </div>
      </div>
    </div>
  )
}
