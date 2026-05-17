import { motion } from 'framer-motion'
import { Cpu, Zap, Hash, DollarSign, ArrowRight, Database } from 'lucide-react'
import type { ModelExecution, RAGChain } from '../hooks/useReasoningData'

// ─── Config ───────────────────────────────────────────────────────────────────

const PROVIDER_COLORS: Record<string, string> = {
  Anthropic: '#8b5cf6',
  OpenAI:    '#10b981',
}

const ROLE_COLORS: Record<string, string> = {
  'RAG Embedding':        '#0ea5e9',
  'Extraction & Parsing': '#a855f7',
  'Criterion Evaluation': '#6366f1',
}

// ─── Latency bar ──────────────────────────────────────────────────────────────

function LatencyBar({ ms, maxMs, color }: { ms: number; maxMs: number; color: string }) {
  const pct = (ms / maxMs) * 100
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-[var(--border)] overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.7, ease: 'easeOut', delay: 0.2 }}
          style={{ background: color }}
        />
      </div>
      <span className="text-[10px] font-mono tabular-nums text-[var(--text-3)] w-14 text-right">{ms}ms</span>
    </div>
  )
}

// ─── Token breakdown ──────────────────────────────────────────────────────────

function TokenBar({ input, output, color }: { input: number; output: number; color: string }) {
  const total    = input + output
  const inputPct = (input / total) * 100
  return (
    <div>
      <div className="h-2 rounded-full overflow-hidden flex" style={{ background: 'var(--border)' }}>
        <motion.div
          className="h-full"
          initial={{ width: 0 }}
          animate={{ width: `${inputPct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut', delay: 0.3 }}
          style={{ background: `${color}90` }}
        />
        <motion.div
          className="h-full flex-1"
          style={{ background: color }}
        />
      </div>
      <div className="flex justify-between mt-1">
        <span className="text-[9px] text-[var(--text-4)]">in: {input.toLocaleString()}</span>
        <span className="text-[9px] text-[var(--text-4)]">out: {output.toLocaleString()}</span>
      </div>
    </div>
  )
}

// ─── Model card ───────────────────────────────────────────────────────────────

function ModelCard({ exec, maxLatency, index }: { exec: ModelExecution; maxLatency: number; index: number }) {
  const providerColor = PROVIDER_COLORS[exec.provider] ?? '#6b7280'
  const roleColor     = ROLE_COLORS[exec.role] ?? '#6b7280'

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1, duration: 0.3 }}
      className="rounded-xl p-3 space-y-2.5"
      style={{
        background: `${roleColor}08`,
        border: `1px solid ${roleColor}30`,
      }}
    >
      {/* Model header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
            <span
              className="text-[9px] font-bold px-1.5 py-0.5 rounded-md uppercase tracking-wide"
              style={{ background: `${providerColor}20`, color: providerColor }}
            >
              {exec.provider}
            </span>
            {exec.isFallback && (
              <span className="text-[9px] px-1.5 py-0.5 rounded-md bg-[#f59e0b20] text-[#f59e0b] font-semibold">
                FALLBACK
              </span>
            )}
          </div>
          <p className="text-xs font-bold text-[var(--text-1)] font-mono leading-tight">{exec.model}</p>
          <p className="text-[10px] text-[var(--text-4)] mt-0.5" style={{ color: roleColor }}>{exec.role}</p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-[10px] font-mono text-[var(--text-4)]">${exec.totalCost.toFixed(4)}</p>
        </div>
      </div>

      {/* Latency bar */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-[9px] uppercase tracking-wide text-[var(--text-4)]">Latency</span>
        </div>
        <LatencyBar ms={exec.latencyMs} maxMs={maxLatency} color={roleColor} />
      </div>

      {/* Token bar (only for models that use tokens) */}
      {exec.inputTokens > 0 && (
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[9px] uppercase tracking-wide text-[var(--text-4)]">Tokens</span>
            <span className="text-[9px] font-mono text-[var(--text-3)]">
              {(exec.inputTokens + exec.outputTokens).toLocaleString()} total
            </span>
          </div>
          <TokenBar input={exec.inputTokens} output={exec.outputTokens} color={roleColor} />
        </div>
      )}

      {/* Steps pills */}
      <div className="flex flex-wrap gap-1">
        {exec.steps.map((s) => (
          <span
            key={s}
            className="text-[9px] font-mono px-1.5 py-0.5 rounded-md"
            style={{ background: `${roleColor}15`, color: roleColor }}
          >
            {s}
          </span>
        ))}
      </div>
    </motion.div>
  )
}

// ─── RAG chain panel ──────────────────────────────────────────────────────────

function RAGPanel({ rag }: { rag: RAGChain }) {
  const filtered = rag.retrieved - rag.filtered
  const pct      = (rag.filtered / rag.retrieved) * 100

  return (
    <div
      className="rounded-xl p-3 space-y-2.5"
      style={{ background: '#0ea5e908', border: '1px solid #0ea5e930' }}
    >
      <div className="flex items-center gap-2 mb-1">
        <Database className="w-3.5 h-3.5 text-[#0ea5e9]" />
        <span className="text-xs font-semibold text-[var(--text-1)]">RAG Pipeline</span>
        <span className="text-[9px] font-mono text-[#0ea5e9] ml-auto">{rag.latencyMs}ms</span>
      </div>

      <div
        className="rounded-lg p-2 text-[9px] font-mono text-[var(--text-3)] break-all leading-relaxed"
        style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
      >
        {rag.query}
      </div>

      <div className="grid grid-cols-2 gap-2">
        {[
          { label: 'Retrieved', value: rag.retrieved, color: '#6b7280' },
          { label: 'Filtered',  value: rag.filtered,  color: '#0ea5e9' },
          { label: 'Pruned',    value: filtered,       color: '#f59e0b' },
          { label: 'Threshold', value: `sim ≥ ${rag.threshold}`, color: '#8b5cf6', raw: true },
        ].map((item) => (
          <div
            key={item.label}
            className="rounded-lg px-2 py-1.5 flex flex-col"
            style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
          >
            <span className="text-[8px] text-[var(--text-4)] uppercase tracking-wide">{item.label}</span>
            <span
              className="text-sm font-bold tabular-nums font-mono mt-0.5"
              style={{ color: item.color }}
            >
              {item.raw ? item.value : item.value}
            </span>
          </div>
        ))}
      </div>

      {/* Filter funnel bar */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-[9px] text-[var(--text-4)]">Filter rate</span>
          <span className="text-[9px] font-mono text-[#0ea5e9]">{pct.toFixed(0)}% passed</span>
        </div>
        <div className="h-1.5 rounded-full bg-[var(--border)] overflow-hidden">
          <motion.div
            className="h-full rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
            style={{ background: 'linear-gradient(90deg, #0ea5e9, #8b5cf6)' }}
          />
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        <Cpu className="w-3 h-3 text-[var(--text-4)]" />
        <span className="text-[9px] font-mono text-[var(--text-4)]">{rag.embedModel}</span>
      </div>
    </div>
  )
}

// ─── Summary stats ────────────────────────────────────────────────────────────

function SummaryRow({ label, value, icon: Icon, color }: { label: string; value: string; icon: React.ElementType; color: string }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-1.5">
        <Icon className="w-3 h-3" style={{ color }} />
        <span className="text-[10px] text-[var(--text-3)]">{label}</span>
      </div>
      <span className="text-[10px] font-mono font-semibold text-[var(--text-1)]">{value}</span>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  modelChain:     ModelExecution[]
  ragChain:       RAGChain
  totalLatencyMs: number
  totalTokens:    number
}

export function AIChainPanel({ modelChain, ragChain, totalLatencyMs, totalTokens }: Props) {
  const maxLatency  = Math.max(...modelChain.map((m) => m.latencyMs))
  const totalCost   = modelChain.reduce((s, m) => s + m.totalCost, 0)

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
        <span className="text-sm font-semibold text-[var(--text-1)]">AI Execution Chain</span>
        <div className="flex items-center gap-1">
          <ArrowRight className="w-3.5 h-3.5 text-[var(--text-4)]" />
          <span className="text-[10px] text-[var(--text-4)]">{modelChain.length} models</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {/* Summary strip */}
        <div
          className="rounded-xl p-3 space-y-1.5"
          style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
        >
          <SummaryRow label="Total latency"  value={`${totalLatencyMs}ms`} icon={Zap}         color="#f59e0b" />
          <SummaryRow label="Total tokens"   value={totalTokens.toLocaleString()} icon={Hash} color="#8b5cf6" />
          <SummaryRow label="Estimated cost" value={`$${totalCost.toFixed(4)}`}  icon={DollarSign} color="#10b981" />
        </div>

        {/* RAG chain */}
        <RAGPanel rag={ragChain} />

        {/* Model chain — connected by arrows */}
        <div className="space-y-2">
          {modelChain.map((exec, i) => (
            <div key={exec.model} className="space-y-1">
              <ModelCard exec={exec} maxLatency={maxLatency} index={i} />
              {i < modelChain.length - 1 && (
                <div className="flex items-center justify-center">
                  <ArrowRight className="w-3.5 h-3.5 text-[var(--text-4)] rotate-90" />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
