import { motion, AnimatePresence } from 'framer-motion'
import {
  Search, FileText, Layers, CheckCircle2, BarChart2, Lightbulb,
  ChevronDown, ChevronRight, Clock, Hash, Cpu,
} from 'lucide-react'
import type { ReasoningStep, StepType } from '../hooks/useReasoningData'

// ─── Step config ──────────────────────────────────────────────────────────────

const STEP_CFG: Record<StepType, { color: string; bg: string; Icon: React.ElementType; label: string }> = {
  retrieve:       { color: '#0ea5e9', bg: '#0ea5e910', Icon: Search,       label: 'Retrieve' },
  parse:          { color: '#8b5cf6', bg: '#8b5cf610', Icon: FileText,     label: 'Parse' },
  evidence_gather:{ color: '#a855f7', bg: '#a855f710', Icon: Layers,       label: 'Gather' },
  evaluate:       { color: '#6366f1', bg: '#6366f110', Icon: CheckCircle2, label: 'Evaluate' },
  aggregate:      { color: '#f59e0b', bg: '#f59e0b10', Icon: BarChart2,    label: 'Aggregate' },
  conclude:       { color: '#10b981', bg: '#10b98110', Icon: Lightbulb,    label: 'Conclude' },
}

// ─── Timing bar ───────────────────────────────────────────────────────────────

function LatencyBar({ ms, maxMs, color }: { ms: number; maxMs: number; color: string }) {
  const pct = Math.min((ms / maxMs) * 100, 100)
  return (
    <div className="flex items-center gap-2 mt-2">
      <div className="flex-1 h-1 rounded-full bg-[var(--border)] overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut', delay: 0.1 }}
          style={{ background: color }}
        />
      </div>
      <span className="text-[9px] font-mono tabular-nums text-[var(--text-4)] w-12 text-right">{ms}ms</span>
    </div>
  )
}

// ─── Single step ──────────────────────────────────────────────────────────────

interface StepRowProps {
  step:       ReasoningStep
  isLast:     boolean
  isExpanded: boolean
  isActive:   boolean
  maxLatency: number
  onToggle:   (id: string) => void
  onActivate: (id: string | null) => void
  index:      number
}

function StepRow({ step, isLast, isExpanded, isActive, maxLatency, onToggle, onActivate, index }: StepRowProps) {
  const cfg = STEP_CFG[step.type]
  const { Icon, color, bg } = cfg

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3 }}
      className="flex gap-3"
    >
      {/* Connector column */}
      <div className="flex flex-col items-center" style={{ width: 32, flexShrink: 0 }}>
        <motion.div
          whileHover={{ scale: 1.1 }}
          onClick={() => onActivate(isActive ? null : step.id)}
          className="w-8 h-8 rounded-lg flex items-center justify-center cursor-pointer transition-all"
          style={{
            background: isActive ? bg : 'var(--elevated)',
            border: `1.5px solid ${isActive ? color : 'var(--border)'}`,
            boxShadow: isActive ? `0 0 12px ${color}40` : 'none',
          }}
        >
          <Icon style={{ color, width: 14, height: 14 }} />
        </motion.div>
        {!isLast && (
          <div className="flex-1 w-px mt-1" style={{ background: 'var(--border)', minHeight: 16 }} />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 pb-4 min-w-0">
        <div
          className="rounded-xl border overflow-hidden cursor-pointer transition-all"
          style={{
            border: `1px solid ${isActive ? `${color}50` : 'var(--border)'}`,
            background: isActive ? bg : 'var(--surface)',
          }}
          onClick={() => onToggle(step.id)}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2.5 gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <span
                className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-md"
                style={{ background: bg, color }}
              >
                {cfg.label}
              </span>
              <span className="text-xs font-semibold text-[var(--text-1)] truncate">{step.label}</span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {step.confidence !== undefined && (
                <span
                  className="text-[9px] font-mono tabular-nums px-1.5 py-0.5 rounded-md"
                  style={{
                    background: step.confidence >= 0.9 ? '#10b98115' : step.confidence >= 0.7 ? '#f59e0b15' : '#ef444415',
                    color:      step.confidence >= 0.9 ? '#10b981'   : step.confidence >= 0.7 ? '#f59e0b'   : '#ef4444',
                  }}
                >
                  {(step.confidence * 100).toFixed(0)}%
                </span>
              )}
              {isExpanded ? (
                <ChevronDown className="w-3.5 h-3.5 text-[var(--text-4)]" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5 text-[var(--text-4)]" />
              )}
            </div>
          </div>

          {/* Latency bar always visible */}
          <div className="px-3 pb-2">
            <LatencyBar ms={step.latencyMs} maxMs={maxLatency} color={color} />
          </div>

          {/* Expanded body */}
          <AnimatePresence initial={false}>
            {isExpanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="px-3 pb-3 pt-1 border-t border-[var(--border)] space-y-2.5">
                  <p className="text-[11px] text-[var(--text-3)] leading-relaxed">{step.detail}</p>

                  <div
                    className="rounded-lg px-3 py-2 text-[10px] text-[var(--text-2)] leading-relaxed font-mono"
                    style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
                  >
                    {step.outputSummary}
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <div className="flex items-center gap-1 text-[9px] text-[var(--text-4)]">
                      <Clock className="w-3 h-3" />
                      <span>{step.latencyMs}ms</span>
                    </div>
                    {step.tokenCount > 0 && (
                      <div className="flex items-center gap-1 text-[9px] text-[var(--text-4)]">
                        <Hash className="w-3 h-3" />
                        <span>{step.tokenCount.toLocaleString()} tokens</span>
                      </div>
                    )}
                    <div className="flex items-center gap-1 text-[9px] text-[var(--text-4)]">
                      <Cpu className="w-3 h-3" />
                      <span className="font-mono">{step.model}</span>
                    </div>
                  </div>

                  {step.inputChunks && step.inputChunks.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {step.inputChunks.map((c) => (
                        <span
                          key={c}
                          className="text-[9px] px-1.5 py-0.5 rounded-md font-mono"
                          style={{ background: `${color}15`, color }}
                        >
                          {c}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  steps:          ReasoningStep[]
  activeStepId:   string | null
  expandedStepIds: Set<string>
  onActivate:     (id: string | null) => void
  onToggle:       (id: string) => void
  totalLatencyMs: number
  totalTokens:    number
}

export function ReasoningTimeline({ steps, activeStepId, expandedStepIds, onActivate, onToggle, totalLatencyMs, totalTokens }: Props) {
  const maxLatency = Math.max(...steps.map((s) => s.latencyMs))

  return (
    <div
      className="rounded-2xl overflow-hidden flex flex-col h-full"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 border-b border-[var(--border)] flex items-center justify-between shrink-0"
        style={{ background: 'var(--elevated)' }}
      >
        <span className="text-sm font-semibold text-[var(--text-1)]">Reasoning Timeline</span>
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-mono text-[var(--text-4)]">{totalLatencyMs}ms total</span>
          <span className="text-[10px] font-mono text-[var(--text-4)]">{totalTokens.toLocaleString()} tokens</span>
          <span className="text-[10px] text-[var(--text-4)]">{steps.length} steps</span>
        </div>
      </div>

      {/* Timeline */}
      <div className="flex-1 overflow-y-auto px-4 pt-4 pb-2">
        {steps.map((step, i) => (
          <StepRow
            key={step.id}
            step={step}
            isLast={i === steps.length - 1}
            isExpanded={expandedStepIds.has(step.id)}
            isActive={activeStepId === step.id}
            maxLatency={maxLatency}
            onToggle={onToggle}
            onActivate={onActivate}
            index={i}
          />
        ))}
      </div>
    </div>
  )
}
