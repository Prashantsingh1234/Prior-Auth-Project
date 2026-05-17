import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ChevronRight, ChevronDown, Search, Filter, AlertTriangle,
  CheckCircle2, Clock, Zap, Bot, Database, FileText, Link2, BarChart2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AITrace, TraceSpan } from '../hooks/useMonitoringData'

// ─── Span type config ─────────────────────────────────────────────────────────

const SPAN_CFG: Record<TraceSpan['type'], { color: string; icon: React.ElementType; label: string }> = {
  llm:       { color: '#6366f1', icon: Bot,       label: 'LLM' },
  retrieval: { color: '#0ea5e9', icon: Database,   label: 'Retrieval' },
  ocr:       { color: '#f59e0b', icon: FileText,   label: 'OCR' },
  tool:      { color: '#10b981', icon: Link2,      label: 'Tool' },
  chain:     { color: '#8b5cf6', icon: Zap,        label: 'Chain' },
  eval:      { color: '#14b8a6', icon: BarChart2,  label: 'Eval' },
}

// ─── Waterfall bar ────────────────────────────────────────────────────────────

function SpanWaterfall({ spans, totalMs }: { spans: TraceSpan[]; totalMs: number }) {
  const [hovered, setHovered] = useState<string | null>(null)

  return (
    <div className="space-y-1">
      {spans.map((span) => {
        const cfg   = SPAN_CFG[span.type]
        const left  = (span.startMs / totalMs) * 100
        const width = Math.max((span.durationMs / totalMs) * 100, 1.5)
        const isHov = hovered === span.id

        return (
          <div
            key={span.id}
            className="flex items-center gap-2 group cursor-pointer"
            onMouseEnter={() => setHovered(span.id)}
            onMouseLeave={() => setHovered(null)}
          >
            {/* Label */}
            <div className="w-36 shrink-0 flex items-center gap-1.5">
              <cfg.icon className="w-3 h-3 shrink-0" style={{ color: cfg.color }} />
              <span className="text-[9px] font-mono text-[var(--text-3)] truncate">{span.name}</span>
            </div>

            {/* Track */}
            <div className="flex-1 h-5 relative rounded-sm overflow-hidden" style={{ background: 'var(--surface)' }}>
              <motion.div
                className="absolute top-0 h-full rounded-sm"
                style={{
                  left:    `${left}%`,
                  width:   `${width}%`,
                  background: `${cfg.color}${isHov ? 'dd' : '80'}`,
                  border:  `1px solid ${cfg.color}${isHov ? 'ff' : '40'}`,
                }}
                whileHover={{ filter: 'brightness(1.2)' }}
              >
                {width > 8 && (
                  <span className="absolute inset-y-0 left-1 flex items-center text-[8px] font-mono text-white/80">
                    {span.durationMs}ms
                  </span>
                )}
              </motion.div>

              {/* Status dot */}
              {span.status !== 'success' && (
                <div
                  className="absolute right-1 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full"
                  style={{ background: span.status === 'error' ? '#ef4444' : '#f59e0b' }}
                />
              )}
            </div>

            {/* Duration */}
            <span className="w-12 text-right text-[9px] font-mono text-[var(--text-4)]">
              {span.durationMs}ms
            </span>
          </div>
        )
      })}

      {/* Total bar */}
      <div className="flex items-center gap-2 pt-1 border-t border-[var(--border)]">
        <div className="w-36 shrink-0 text-[9px] text-[var(--text-4)] font-semibold uppercase tracking-wide pl-4">Total</div>
        <div className="flex-1" />
        <span className="w-12 text-right text-[10px] font-bold font-mono text-[var(--text-1)]">
          {totalMs}ms
        </span>
      </div>
    </div>
  )
}

// ─── Trace detail panel ───────────────────────────────────────────────────────

const STATUS_CFG = {
  success: { icon: CheckCircle2, color: '#10b981', label: 'Success' },
  warning: { icon: AlertTriangle, color: '#f59e0b', label: 'Warning' },
  error:   { icon: AlertTriangle, color: '#ef4444', label: 'Error' },
}

const DECISION_COLOR: Record<string, string> = {
  APPROVE: '#10b981',
  DENY:    '#ef4444',
  PEND:    '#f59e0b',
}

function TraceDetail({ trace }: { trace: AITrace }) {
  const [expanded, setExpanded] = useState(false)
  const sCfg = STATUS_CFG[trace.status]

  return (
    <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-bold text-[var(--text-1)] font-mono">{trace.id}</p>
          <p className="text-[10px] text-[var(--text-4)]">{trace.caseRef} · {new Date(trace.triggeredAt).toLocaleString()}</p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="px-2 py-0.5 rounded text-[10px] font-bold"
            style={{ background: `${DECISION_COLOR[trace.decision] ?? '#6b7280'}20`, color: DECISION_COLOR[trace.decision] ?? '#6b7280' }}
          >
            {trace.decision}
          </span>
          <div className="flex items-center gap-1" style={{ color: sCfg.color }}>
            <sCfg.icon className="w-3.5 h-3.5" />
            <span className="text-[10px] font-semibold">{sCfg.label}</span>
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: 'Total Time',  value: `${trace.totalMs}ms`,             color: '#6366f1' },
          { label: 'Confidence',  value: `${trace.confidence}%`,            color: trace.confidence >= 80 ? '#10b981' : '#f59e0b' },
          { label: 'Grounding',   value: `${trace.groundingScore}%`,        color: trace.groundingScore >= 85 ? '#10b981' : '#f59e0b' },
          { label: 'Input Tokens', value: trace.inputTokens.toLocaleString(), color: '#8b5cf6' },
          { label: 'Output Tokens', value: trace.outputTokens.toLocaleString(), color: '#a855f7' },
          { label: 'Model',       value: trace.model.replace('claude-', ''), color: '#0ea5e9' },
        ].map((kpi) => (
          <div key={kpi.label} className="rounded-lg p-2"
               style={{ background: 'var(--surface)', border: `1px solid ${kpi.color}20` }}>
            <p className="text-[8px] text-[var(--text-4)] uppercase tracking-wide">{kpi.label}</p>
            <p className="text-xs font-bold font-mono mt-0.5" style={{ color: kpi.color }}>{kpi.value}</p>
          </div>
        ))}
      </div>

      {/* Flags */}
      {(trace.hallucinationFlag || trace.fallbackUsed) && (
        <div className="flex items-center gap-2">
          {trace.hallucinationFlag && (
            <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-semibold bg-red-500/10 text-red-400 border border-red-500/20">
              <AlertTriangle className="w-2.5 h-2.5" />
              Hallucination Detected
            </span>
          )}
          {trace.fallbackUsed && (
            <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Zap className="w-2.5 h-2.5" />
              Fallback Model Used
            </span>
          )}
        </div>
      )}

      {/* Waterfall */}
      <div className="rounded-xl p-4" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
        <div className="flex items-center justify-between mb-3">
          <span className="text-[10px] font-bold text-[var(--text-2)] uppercase tracking-wide">Execution Waterfall</span>
          <span className="text-[9px] text-[var(--text-4)]">{trace.spans.length} spans</span>
        </div>
        <SpanWaterfall spans={trace.spans} totalMs={trace.totalMs} />
      </div>

      {/* Span metadata */}
      <div>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-1 text-[10px] text-[var(--text-3)] hover:text-[var(--text-1)] transition-colors mb-2"
        >
          {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          Span Metadata
        </button>
        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="space-y-1.5">
                {trace.spans.filter((s) => s.metadata && Object.keys(s.metadata).length > 0).map((span) => (
                  <div key={span.id} className="rounded-lg px-3 py-2"
                       style={{ background: 'var(--surface)', border: `1px solid ${SPAN_CFG[span.type].color}20` }}>
                    <p className="text-[9px] font-mono font-bold" style={{ color: SPAN_CFG[span.type].color }}>{span.name}</p>
                    <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1">
                      {Object.entries(span.metadata ?? {}).map(([k, v]) => (
                        <span key={k} className="text-[9px] font-mono text-[var(--text-4)]">
                          <span className="text-[var(--text-3)]">{k}:</span> {v}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

// ─── Trace list ───────────────────────────────────────────────────────────────

interface TraceRowProps {
  trace:    AITrace
  isActive: boolean
  onSelect: () => void
}

function TraceRow({ trace, isActive, onSelect }: TraceRowProps) {
  const sCfg = STATUS_CFG[trace.status]
  const ago  = Math.round((Date.now() - new Date(trace.triggeredAt).getTime()) / 60000)

  return (
    <motion.button
      whileHover={{ x: 2 }}
      onClick={onSelect}
      className={cn(
        'w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors',
        isActive ? 'bg-[var(--elevated)]' : 'hover:bg-[var(--elevated)]/50',
      )}
    >
      <sCfg.icon className="w-3.5 h-3.5 shrink-0" style={{ color: sCfg.color }} />
      <div className="flex-1 min-w-0">
        <p className="text-[10px] font-mono text-[var(--text-1)] truncate">{trace.id}</p>
        <p className="text-[9px] text-[var(--text-4)]">{trace.caseRef} · {ago}m ago</p>
      </div>
      <div className="shrink-0 flex flex-col items-end gap-0.5">
        <span
          className="text-[9px] font-bold font-mono"
          style={{ color: DECISION_COLOR[trace.decision] ?? '#6b7280' }}
        >
          {trace.decision}
        </span>
        <span className="text-[8px] font-mono text-[var(--text-4)]">{trace.totalMs}ms</span>
      </div>
      {isActive && (
        <motion.div
          layoutId="trace-indicator"
          className="absolute right-0 top-1/2 -translate-y-1/2 w-0.5 h-6 rounded-full bg-[#6366f1]"
        />
      )}
    </motion.button>
  )
}

// ─── Main explorer ────────────────────────────────────────────────────────────

interface AITraceExplorerProps {
  traces:       AITrace[]
  selectedTrace: AITrace | null
  onSelect:     (t: AITrace) => void
}

export function AITraceExplorer({ traces, selectedTrace, onSelect }: AITraceExplorerProps) {
  const [search, setSearch]     = useState('')
  const [filter, setFilter]     = useState<AITrace['status'] | 'all'>('all')

  const filtered = useMemo(() =>
    traces.filter((t) => {
      if (filter !== 'all' && t.status !== filter) return false
      if (search && !t.id.includes(search) && !t.caseRef.toLowerCase().includes(search.toLowerCase())) return false
      return true
    }),
    [traces, filter, search],
  )

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      {/* List panel */}
      <div
        className="w-72 shrink-0 flex flex-col border-r border-[var(--border)]"
        style={{ background: 'var(--surface)' }}
      >
        {/* Search + filter */}
        <div className="p-3 space-y-2 border-b border-[var(--border)]">
          <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
            <Search className="w-3 h-3 text-[var(--text-4)]" />
            <input
              className="flex-1 bg-transparent text-xs text-[var(--text-1)] placeholder:text-[var(--text-4)] outline-none"
              placeholder="Search traces…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-1">
            <Filter className="w-3 h-3 text-[var(--text-4)]" />
            {(['all', 'success', 'warning', 'error'] as const).map((s) => (
              <button
                key={s}
                onClick={() => setFilter(s)}
                className={cn(
                  'px-2 py-0.5 rounded text-[9px] font-semibold capitalize transition-colors',
                  filter === s ? 'bg-[#6366f1] text-white' : 'text-[var(--text-4)] hover:text-[var(--text-2)]',
                )}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Trace rows */}
        <div className="flex-1 overflow-y-auto relative divide-y divide-[var(--border)]">
          {filtered.map((t) => (
            <div key={t.id} className="relative">
              <TraceRow
                trace={t}
                isActive={selectedTrace?.id === t.id}
                onSelect={() => onSelect(t)}
              />
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="p-6 text-center text-[10px] text-[var(--text-4)]">No traces match</div>
          )}
        </div>

        {/* Footer count */}
        <div className="px-3 py-2 border-t border-[var(--border)] flex items-center gap-1">
          <Clock className="w-3 h-3 text-[var(--text-4)]" />
          <span className="text-[9px] text-[var(--text-4)]">{filtered.length} of {traces.length} traces</span>
        </div>
      </div>

      {/* Detail panel */}
      <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
        <AnimatePresence mode="wait">
          {selectedTrace ? (
            <motion.div
              key={selectedTrace.id}
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              transition={{ duration: 0.15 }}
              className="flex-1 min-h-0 flex flex-col"
            >
              <TraceDetail trace={selectedTrace} />
            </motion.div>
          ) : (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex-1 flex items-center justify-center"
            >
              <div className="text-center">
                <Bot className="w-8 h-8 text-[var(--text-4)] mx-auto mb-2" />
                <p className="text-xs text-[var(--text-4)]">Select a trace to inspect</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
