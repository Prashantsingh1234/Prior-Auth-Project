import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Brain, Database, ChevronDown, ChevronRight, Copy, Check,
  Zap, AlertTriangle, CheckCircle2, Lock, Shield,
} from 'lucide-react'
import type { AuditEntry, PromptTrace, RetrievalTrace, AIDecisionOutput } from '../hooks/useAuditData'

// ─── Token usage bar ──────────────────────────────────────────────────────────

function TokenBar({ input, output }: { input: number; output: number }) {
  const total = input + output
  const inPct = (input / total) * 100
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 flex rounded-full overflow-hidden">
        <div className="h-full bg-[#6366f1]" style={{ width: `${inPct}%` }} />
        <div className="h-full bg-[#8b5cf6]" style={{ width: `${100 - inPct}%` }} />
      </div>
      <span className="text-[8px] font-mono text-[var(--text-4)]">{total.toLocaleString()} total</span>
    </div>
  )
}

// ─── Prompt section ───────────────────────────────────────────────────────────

function PromptBlock({ label, text, color }: { label: string; text: string; color: string }) {
  const [expanded, setExpanded] = useState(false)
  const [copied, setCopied]     = useState(false)
  const preview = text.slice(0, 180)
  const hasMore = text.length > 180

  function copy() {
    navigator.clipboard.writeText(text).catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="rounded-xl overflow-hidden" style={{ border: `1px solid ${color}25` }}>
      <div className="flex items-center justify-between px-3 py-2" style={{ background: `${color}10` }}>
        <span className="text-[9px] font-bold uppercase tracking-wide" style={{ color }}>{label}</span>
        <button onClick={copy} className="flex items-center gap-1 text-[8px] transition-colors" style={{ color: copied ? '#10b981' : 'var(--text-4)' }}>
          {copied ? <Check className="w-2.5 h-2.5" /> : <Copy className="w-2.5 h-2.5" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <div className="px-3 py-2" style={{ background: 'var(--surface)' }}>
        <p className="text-[9px] font-mono text-[var(--text-2)] leading-relaxed whitespace-pre-wrap">
          {expanded ? text : preview}{hasMore && !expanded && '…'}
        </p>
        {hasMore && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex items-center gap-1 mt-1.5 text-[8px] transition-colors"
            style={{ color: '#6366f1' }}
          >
            {expanded ? <ChevronDown className="w-2.5 h-2.5" /> : <ChevronRight className="w-2.5 h-2.5" />}
            {expanded ? 'Collapse' : `Show ${text.length - 180} more chars`}
          </button>
        )}
      </div>
    </div>
  )
}

// ─── Prompt trace panel ───────────────────────────────────────────────────────

function PromptTracePanel({ trace }: { trace: PromptTrace }) {
  return (
    <div className="space-y-3">
      {/* KPIs */}
      <div className="grid grid-cols-4 gap-2">
        {[
          { label: 'Model',   value: trace.model.replace('claude-', ''), color: '#6366f1' },
          { label: 'Latency', value: `${trace.latencyMs}ms`,             color: trace.latencyMs > 2000 ? '#ef4444' : '#10b981' },
          { label: 'Grounding', value: `${(trace.groundingScore * 100).toFixed(0)}%`, color: trace.groundingScore >= 0.85 ? '#10b981' : '#f59e0b' },
          { label: 'Cost',    value: `$${trace.cost.toFixed(4)}`,        color: '#8b5cf6' },
        ].map((k) => (
          <div key={k.label} className="rounded-lg p-2 text-center" style={{ background: 'var(--surface)', border: `1px solid ${k.color}20` }}>
            <p className="text-[7px] text-[var(--text-4)] uppercase tracking-wide">{k.label}</p>
            <p className="text-[10px] font-bold font-mono mt-0.5" style={{ color: k.color }}>{k.value}</p>
          </div>
        ))}
      </div>

      {/* Token usage */}
      <div className="rounded-xl p-3 space-y-2" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
        <div className="flex items-center justify-between">
          <span className="text-[9px] font-bold text-[var(--text-3)] uppercase tracking-wide">Token Usage</span>
          <span className="text-[8px] font-mono text-[var(--text-4)]">temp={trace.temperature}</span>
        </div>
        <TokenBar input={trace.inputTokens} output={trace.outputTokens} />
        <div className="flex items-center gap-4 text-[8px]">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-[#6366f1] inline-block" />Input: {trace.inputTokens.toLocaleString()}</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-[#8b5cf6] inline-block" />Output: {trace.outputTokens.toLocaleString()}</span>
        </div>
      </div>

      {/* Hallucination flag */}
      {trace.hallucinationFlag && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-xl" style={{ background: '#ef444410', border: '1px solid #ef444440' }}>
          <AlertTriangle className="w-3 h-3 text-red-400 shrink-0" />
          <span className="text-[9px] text-red-400 font-semibold">Hallucination flag raised for this trace</span>
        </div>
      )}

      {/* Prompt blocks */}
      <PromptBlock label="System Prompt" text={trace.systemPrompt} color="#6b7280" />
      <PromptBlock label="User Prompt"   text={trace.userPrompt}   color="#6366f1" />
      <PromptBlock label="Completion"    text={trace.completion}   color="#10b981" />
    </div>
  )
}

// ─── Retrieval trace panel ────────────────────────────────────────────────────

function RetrievalTracePanel({ trace }: { trace: RetrievalTrace }) {
  const usedChunks = trace.chunks.filter((c) => c.used)
  const filtered   = trace.chunks.filter((c) => !c.used)

  return (
    <div className="space-y-3">
      {/* Stats */}
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: 'Retrieved', value: trace.totalChunks, color: '#6366f1' },
          { label: 'Used',      value: usedChunks.length, color: '#10b981' },
          { label: 'Threshold', value: trace.threshold,   color: '#f59e0b' },
        ].map((s) => (
          <div key={s.label} className="rounded-lg p-2 text-center" style={{ background: 'var(--surface)', border: `1px solid ${s.color}20` }}>
            <p className="text-[7px] text-[var(--text-4)] uppercase tracking-wide">{s.label}</p>
            <p className="text-[11px] font-bold font-mono mt-0.5" style={{ color: s.color }}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* Query */}
      <div className="rounded-xl p-3" style={{ background: 'var(--surface)', border: '1px solid #6366f125' }}>
        <p className="text-[8px] font-bold uppercase tracking-wide text-[#6366f1] mb-1">Embedding Query</p>
        <p className="text-[9px] font-mono text-[var(--text-2)] italic">"{trace.query}"</p>
      </div>

      {/* Chunks */}
      <div>
        <p className="text-[8px] font-bold uppercase tracking-widest text-[var(--text-4)] mb-1.5">Chunks Used ({usedChunks.length})</p>
        <div className="space-y-1.5">
          {usedChunks.map((chunk) => {
            const barColor = chunk.score >= 0.90 ? '#10b981' : chunk.score >= 0.80 ? '#6366f1' : '#f59e0b'
            return (
              <div key={chunk.id} className="rounded-xl p-2.5" style={{ background: 'var(--surface)', border: `1px solid ${barColor}25` }}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[8px] font-semibold text-[var(--text-3)]">{chunk.policyName} <span className="font-mono text-[var(--text-4)]">{chunk.sectionRef}</span></span>
                  <div className="flex items-center gap-1.5">
                    <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--elevated)' }}>
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${chunk.score * 100}%` }}
                        transition={{ duration: 0.5 }}
                        className="h-full rounded-full"
                        style={{ background: barColor }}
                      />
                    </div>
                    <span className="text-[8px] font-mono font-bold" style={{ color: barColor }}>{(chunk.score * 100).toFixed(0)}%</span>
                    <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400" />
                  </div>
                </div>
                <p className="text-[8px] text-[var(--text-3)] leading-relaxed line-clamp-2">{chunk.text}</p>
              </div>
            )
          })}
        </div>
      </div>

      {filtered.length > 0 && (
        <div>
          <p className="text-[8px] font-bold uppercase tracking-widest text-[var(--text-4)] mb-1.5">Filtered Out ({filtered.length})</p>
          <div className="space-y-1">
            {filtered.map((chunk) => (
              <div key={chunk.id} className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg opacity-50" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
                <span className="text-[8px] font-mono text-[var(--text-4)]">{chunk.sectionRef}</span>
                <span className="text-[8px] text-[var(--text-4)] truncate flex-1">{chunk.text.slice(0, 60)}…</span>
                <span className="text-[8px] font-mono text-[var(--text-4)]">{(chunk.score * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── AI decision output panel ─────────────────────────────────────────────────

function AIOutputPanel({ output }: { output: AIDecisionOutput }) {
  const recColor = { APPROVE: '#10b981', DENY: '#ef4444', PEND: '#f59e0b', ESCALATE: '#f97316' }[output.recommendation] ?? '#6b7280'
  const statusColor = { MET: '#10b981', NOT_MET: '#ef4444', INSUFFICIENT: '#f59e0b' }

  return (
    <div className="space-y-3">
      {/* Decision header */}
      <div className="rounded-xl p-4 flex items-center justify-between" style={{ background: `${recColor}10`, border: `1px solid ${recColor}30` }}>
        <div>
          <p className="text-[8px] text-[var(--text-4)] uppercase tracking-wide">AI Recommendation</p>
          <p className="text-xl font-bold font-mono mt-0.5" style={{ color: recColor }}>{output.recommendation}</p>
        </div>
        <div className="text-right">
          <p className="text-[8px] text-[var(--text-4)] uppercase tracking-wide">Confidence</p>
          <p className="text-xl font-bold font-mono mt-0.5" style={{ color: recColor }}>{(output.confidence * 100).toFixed(0)}%</p>
        </div>
      </div>

      {/* Model chain */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[8px] text-[var(--text-4)]">Model chain:</span>
        {output.modelChain.map((m, i) => (
          <span key={m} className="flex items-center gap-1">
            <span className="text-[8px] font-mono px-1.5 py-0.5 rounded" style={{ background: '#6366f115', color: '#6366f1' }}>{m.replace('claude-', '').replace('text-', '')}</span>
            {i < output.modelChain.length - 1 && <span className="text-[8px] text-[var(--text-4)]">→</span>}
          </span>
        ))}
      </div>

      {/* Rationale */}
      <div className="rounded-xl p-3" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
        <p className="text-[8px] font-bold uppercase tracking-wide text-[var(--text-4)] mb-1.5">AI Rationale</p>
        <p className="text-[9px] text-[var(--text-2)] leading-relaxed">{output.rationale}</p>
      </div>

      {/* Criteria */}
      <div>
        <p className="text-[8px] font-bold uppercase tracking-widest text-[var(--text-4)] mb-1.5">Criteria Evaluation</p>
        <div className="space-y-1.5">
          {output.criteriaResults.map((r, i) => {
            const color = statusColor[r.status]
            return (
              <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-xl" style={{ background: 'var(--elevated)', border: `1px solid ${color}20` }}>
                <div className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
                <span className="flex-1 text-[9px] text-[var(--text-2)]">{r.criterion}</span>
                <span className="text-[8px] font-bold" style={{ color }}>{r.status.replace('_', ' ')}</span>
                <span className="text-[8px] font-mono text-[var(--text-4)]">{(r.confidence * 100).toFixed(0)}%</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ─── Override panel ───────────────────────────────────────────────────────────

function OverridePanel({ override }: { override: NonNullable<AuditEntry['override']> }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <div className="flex-1 rounded-xl p-3 text-center" style={{ background: '#ef444415', border: '1px solid #ef444430' }}>
          <p className="text-[8px] text-[var(--text-4)] uppercase tracking-wide mb-1">AI Decision</p>
          <p className="text-sm font-bold text-red-400">{override.aiDecision}</p>
        </div>
        <Zap className="w-4 h-4 text-[var(--text-4)] shrink-0" />
        <div className="flex-1 rounded-xl p-3 text-center" style={{ background: '#10b98115', border: '1px solid #10b98130' }}>
          <p className="text-[8px] text-[var(--text-4)] uppercase tracking-wide mb-1">Reviewer Decision</p>
          <p className="text-sm font-bold text-emerald-400">{override.reviewerDecision}</p>
        </div>
      </div>
      <div className="rounded-xl p-3" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
        <p className="text-[8px] font-bold uppercase tracking-wide text-[var(--text-4)] mb-1.5">Override Rationale</p>
        <p className="text-[9px] text-[var(--text-2)] leading-relaxed">{override.reason}</p>
      </div>
      {override.flaggedForReview && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-xl" style={{ background: '#f59e0b10', border: '1px solid #f59e0b30' }}>
          <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0" />
          <span className="text-[9px] text-amber-400 font-semibold">This override has been flagged for secondary review</span>
        </div>
      )}
    </div>
  )
}

// ─── Main trace viewer ────────────────────────────────────────────────────────

type TraceTab = 'prompt' | 'retrieval' | 'output' | 'override'

interface TraceViewerProps {
  entry: AuditEntry
}

export function TraceViewer({ entry }: TraceViewerProps) {
  const allTabs: Array<{ id: TraceTab; label: string; icon: React.ElementType; available: boolean }> = [
    { id: 'prompt',    label: 'Prompt Trace',    icon: Brain,    available: !!entry.promptTrace },
    { id: 'retrieval', label: 'Retrieval Trace', icon: Database, available: !!entry.retrievalTrace },
    { id: 'output',    label: 'AI Output',       icon: Brain,    available: !!entry.aiOutput },
    { id: 'override',  label: 'Override',        icon: Zap,      available: !!entry.override },
  ]
  const tabs = allTabs.filter((t) => t.available) as Array<{ id: TraceTab; label: string; icon: React.ElementType }>

  const [activeTab, setActiveTab] = useState<TraceTab>(tabs[0]?.id ?? 'prompt')

  if (tabs.length === 0) return null

  return (
    <div className="mt-3 rounded-xl overflow-hidden" style={{ border: '1px solid #6366f130', background: '#6366f105' }}>
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--border)]" style={{ background: '#6366f108' }}>
        <Lock className="w-3 h-3 text-emerald-400" />
        <span className="text-[9px] font-bold text-[var(--text-2)] uppercase tracking-wide">Immutable Trace Record</span>
        <Shield className="w-3 h-3 text-[var(--text-4)] ml-auto" />
        <span className="text-[8px] font-mono text-[var(--text-4)]">HIPAA-compliant · non-repudiable</span>
      </div>

      {/* Tabs */}
      {tabs.length > 1 && (
        <div className="flex gap-1 px-3 pt-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[9px] font-semibold transition-all"
              style={{
                background: activeTab === tab.id ? 'var(--elevated)' : 'transparent',
                color:      activeTab === tab.id ? 'var(--text-1)' : 'var(--text-4)',
                border:     `1px solid ${activeTab === tab.id ? 'var(--border)' : 'transparent'}`,
              }}
            >
              <tab.icon className="w-3 h-3" />
              {tab.label}
            </button>
          ))}
        </div>
      )}

      {/* Content */}
      <div className="p-3">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.12 }}
          >
            {activeTab === 'prompt'    && entry.promptTrace    && <PromptTracePanel    trace={entry.promptTrace} />}
            {activeTab === 'retrieval' && entry.retrievalTrace && <RetrievalTracePanel trace={entry.retrievalTrace} />}
            {activeTab === 'output'    && entry.aiOutput       && <AIOutputPanel       output={entry.aiOutput} />}
            {activeTab === 'override'  && entry.override       && <OverridePanel       override={entry.override} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}
