import { motion } from 'framer-motion'
import { Bot, Zap, AlertTriangle, CheckCircle2, ToggleLeft, ToggleRight, TrendingUp } from 'lucide-react'
import type { RoutingRule, QueueCase, EscalationRecord, OverrideRecord } from '../hooks/useReviewerWorkflow'

// ─── Routing rule card ────────────────────────────────────────────────────────

function RuleCard({ rule, onToggle }: { rule: RoutingRule; onToggle: (id: string) => void }) {
  const Toggle = rule.enabled ? ToggleRight : ToggleLeft
  return (
    <motion.div
      layout
      className="rounded-xl overflow-hidden transition-all"
      style={{
        border:   `1px solid ${rule.enabled ? `${rule.color}35` : 'var(--border)'}`,
        opacity:  rule.enabled ? 1 : 0.5,
      }}
    >
      <div
        className="px-3 py-2 flex items-start gap-2.5"
        style={{ background: rule.enabled ? `${rule.color}08` : 'var(--elevated)' }}
      >
        <div className="w-1.5 h-1.5 rounded-full shrink-0 mt-1.5" style={{ background: rule.color }} />
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <p className="text-[11px] font-semibold text-[var(--text-1)] leading-tight">{rule.name}</p>
            <button
              onClick={() => onToggle(rule.id)}
              className="shrink-0 transition-colors"
              style={{ color: rule.enabled ? rule.color : 'var(--text-4)' }}
            >
              <Toggle className="w-4 h-4" />
            </button>
          </div>
          <p className="text-[9px] text-[var(--text-4)] mt-0.5">IF: {rule.condition}</p>
          <p className="text-[9px] mt-0.5" style={{ color: rule.color }}>→ {rule.action}</p>
          <div className="flex items-center gap-2 mt-1.5">
            <span className="text-[8px] font-mono text-[var(--text-4)]">P{rule.priority}</span>
            {rule.enabled && (
              <span
                className="text-[8px] font-bold px-1.5 py-0.5 rounded-md"
                style={{ background: `${rule.color}15`, color: rule.color }}
              >
                {rule.triggeredToday}× today
              </span>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  )
}

// ─── AI copilot suggestions ───────────────────────────────────────────────────

function CopilotSuggestions({ cases }: { cases: QueueCase[] }) {
  const highConf   = cases.filter((c) => c.aiConfidence >= 0.9 && c.status === 'unassigned')
  const lowConf    = cases.filter((c) => c.aiConfidence < 0.6 && c.status === 'unassigned')
  const statUnass  = cases.filter((c) => c.urgency === 'stat' && c.status === 'unassigned')
  const overdue    = cases.filter((c) => c.slaStatus === 'breached')

  const suggestions: Array<{ icon: React.ElementType; color: string; title: string; detail: string; count: number }> = []

  if (statUnass.length > 0)  suggestions.push({ icon: AlertTriangle, color: '#ef4444', title: 'STAT cases unassigned', detail: `${statUnass.length} critical cases need immediate assignment`, count: statUnass.length })
  if (overdue.length > 0)    suggestions.push({ icon: AlertTriangle, color: '#ef4444', title: 'SLA breached',          detail: `${overdue.length} cases past SLA deadline`, count: overdue.length })
  if (highConf.length >= 3)  suggestions.push({ icon: Zap,           color: '#10b981', title: 'Batch assign available', detail: `${highConf.length} high-confidence approvals ready for fast-track`, count: highConf.length })
  if (lowConf.length > 0)    suggestions.push({ icon: Bot,           color: '#f59e0b', title: 'Low confidence flagged', detail: `${lowConf.length} cases below 60% confidence need senior review`, count: lowConf.length })

  if (suggestions.length === 0) {
    return (
      <div className="flex items-center gap-2 px-3 py-2.5 rounded-xl" style={{ background: '#10b98108', border: '1px solid #10b98125' }}>
        <CheckCircle2 className="w-3.5 h-3.5 text-[#10b981] shrink-0" />
        <span className="text-[10px] text-[#10b981]">Queue is healthy — no immediate actions required.</span>
      </div>
    )
  }

  return (
    <div className="space-y-1.5">
      {suggestions.map((s, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: 8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.06 }}
          className="flex items-start gap-2.5 rounded-xl px-3 py-2.5 cursor-pointer hover:brightness-110 transition-all"
          style={{ background: `${s.color}10`, border: `1px solid ${s.color}25` }}
        >
          <s.icon className="w-3.5 h-3.5 shrink-0 mt-0.5" style={{ color: s.color }} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <p className="text-[10px] font-bold" style={{ color: s.color }}>{s.title}</p>
              <span
                className="text-[9px] font-bold px-1.5 py-0.5 rounded-full"
                style={{ background: `${s.color}20`, color: s.color }}
              >
                {s.count}
              </span>
            </div>
            <p className="text-[9px] text-[var(--text-3)] mt-0.5">{s.detail}</p>
          </div>
        </motion.div>
      ))}
    </div>
  )
}

// ─── Confidence distribution ──────────────────────────────────────────────────

function ConfidenceDistribution({ cases }: { cases: QueueCase[] }) {
  const bands = [
    { label: '≥90%',  color: '#10b981', count: cases.filter((c) => c.aiConfidence >= 0.9).length },
    { label: '75–90%', color: '#0ea5e9', count: cases.filter((c) => c.aiConfidence >= 0.75 && c.aiConfidence < 0.9).length },
    { label: '55–75%', color: '#f59e0b', count: cases.filter((c) => c.aiConfidence >= 0.55 && c.aiConfidence < 0.75).length },
    { label: '<55%',  color: '#ef4444', count: cases.filter((c) => c.aiConfidence < 0.55).length },
  ]
  const max = Math.max(...bands.map((b) => b.count), 1)

  return (
    <div>
      <p className="text-[9px] uppercase tracking-widest font-bold text-[var(--text-4)] mb-2">Confidence Distribution</p>
      <div className="space-y-1.5">
        {bands.map((b) => (
          <div key={b.label} className="flex items-center gap-2">
            <span className="text-[9px] font-mono text-[var(--text-4)] w-12 shrink-0">{b.label}</span>
            <div className="flex-1 h-2 rounded-full bg-[var(--border)] overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${(b.count / max) * 100}%` }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
                style={{ background: b.color }}
              />
            </div>
            <span className="text-[9px] font-bold tabular-nums w-4" style={{ color: b.color }}>{b.count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Escalation list ──────────────────────────────────────────────────────────

function EscalationList({ escalations }: { escalations: EscalationRecord[] }) {
  const open = escalations.filter((e) => e.status === 'open')
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="text-[9px] uppercase tracking-widest font-bold text-[var(--text-4)]">Open Escalations</p>
        {open.length > 0 && (
          <span className="text-[8px] font-bold px-1.5 py-0.5 rounded-full bg-[#ef444415] text-[#ef4444]">{open.length}</span>
        )}
      </div>
      <div className="space-y-1.5">
        {open.map((e) => (
          <div
            key={e.id}
            className="rounded-xl px-3 py-2.5"
            style={{ background: '#ef444408', border: '1px solid #ef444430' }}
          >
            <div className="flex items-center justify-between gap-2 mb-0.5">
              <span className="text-[10px] font-bold text-[#ef4444]">{e.caseNum}</span>
              <span className="text-[8px] font-bold px-1 py-0.5 rounded-md bg-[#ef444420] text-[#ef4444]">
                L{e.level}
              </span>
            </div>
            <p className="text-[10px] text-[var(--text-2)] font-semibold">{e.patientName}</p>
            <p className="text-[9px] text-[var(--text-4)] mt-0.5 leading-snug">{e.reason}</p>
            <p className="text-[8px] text-[var(--text-4)] mt-1">→ {e.to}</p>
          </div>
        ))}
        {open.length === 0 && (
          <div className="text-center py-3">
            <CheckCircle2 className="w-4 h-4 text-[#10b981] mx-auto mb-1" />
            <p className="text-[10px] text-[var(--text-4)]">No open escalations</p>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Override log ─────────────────────────────────────────────────────────────

function OverrideLog({ overrides }: { overrides: OverrideRecord[] }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="text-[9px] uppercase tracking-widest font-bold text-[var(--text-4)]">Recent Overrides</p>
        <div className="flex items-center gap-1">
          <TrendingUp className="w-3 h-3 text-[#f59e0b]" />
          <span className="text-[9px] text-[var(--text-4)]">{overrides.length} in 48h</span>
        </div>
      </div>
      <div className="space-y-1.5">
        {overrides.slice(0, 3).map((ov) => {
          const fromColor = ov.aiRecommendation === 'deny' ? '#ef4444' : ov.aiRecommendation === 'approve' ? '#10b981' : '#f59e0b'
          const toColor   = ov.reviewerDecision  === 'deny' ? '#ef4444' : ov.reviewerDecision === 'approve' ? '#10b981' : '#f59e0b'
          return (
            <div
              key={ov.id}
              className="rounded-xl px-3 py-2.5"
              style={{ background: ov.flaggedForReview ? '#f59e0b08' : 'var(--elevated)', border: `1px solid ${ov.flaggedForReview ? '#f59e0b35' : 'var(--border)'}` }}
            >
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-[9px] font-bold capitalize px-1.5 py-0.5 rounded-md" style={{ background: `${fromColor}15`, color: fromColor }}>{ov.aiRecommendation}</span>
                <span className="text-[9px] text-[var(--text-4)]">→</span>
                <span className="text-[9px] font-bold capitalize px-1.5 py-0.5 rounded-md" style={{ background: `${toColor}15`, color: toColor }}>{ov.reviewerDecision}</span>
                {ov.flaggedForReview && <AlertTriangle className="w-3 h-3 text-[#f59e0b] ml-auto" />}
              </div>
              <p className="text-[9px] text-[var(--text-3)] leading-snug mt-0.5 line-clamp-2">{ov.reason}</p>
              <p className="text-[8px] text-[var(--text-4)] mt-1">{ov.reviewerName}</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  routingRules: RoutingRule[]
  cases:        QueueCase[]
  escalations:  EscalationRecord[]
  overrides:    OverrideRecord[]
  onToggleRule: (id: string) => void
}

export function AIRoutingPanel({ routingRules, cases, escalations, overrides, onToggleRule }: Props) {
  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* AI Copilot header */}
      <div
        className="px-4 py-3 border-b border-[var(--border)] shrink-0"
        style={{ background: 'var(--elevated)' }}
      >
        <div className="flex items-center gap-2">
          <motion.div
            className="w-2 h-2 rounded-full bg-[#8b5cf6]"
            animate={{ opacity: [1, 0.4, 1], scale: [1, 0.9, 1] }}
            transition={{ duration: 1.8, repeat: Infinity }}
          />
          <span className="text-xs font-bold text-[var(--text-1)]">AI Copilot</span>
          <span className="text-[9px] text-[var(--text-4)] ml-1">Active</span>
        </div>
      </div>

      <div className="flex-1 p-3 space-y-4">
        {/* Copilot suggestions */}
        <section>
          <p className="text-[9px] uppercase tracking-widest font-bold text-[var(--text-4)] mb-2">Recommended Actions</p>
          <CopilotSuggestions cases={cases} />
        </section>

        {/* Confidence distribution */}
        <section
          className="rounded-xl p-3"
          style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
        >
          <ConfidenceDistribution cases={cases} />
        </section>

        {/* Routing rules */}
        <section>
          <div className="flex items-center justify-between mb-2">
            <p className="text-[9px] uppercase tracking-widest font-bold text-[var(--text-4)]">Routing Rules</p>
            <span className="text-[8px] text-[var(--text-4)]">{routingRules.filter((r) => r.enabled).length}/{routingRules.length} active</span>
          </div>
          <div className="space-y-1.5">
            {routingRules.map((r) => (
              <RuleCard key={r.id} rule={r} onToggle={onToggleRule} />
            ))}
          </div>
        </section>

        {/* Escalations */}
        <section
          className="rounded-xl p-3"
          style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
        >
          <EscalationList escalations={escalations} />
        </section>

        {/* Overrides */}
        <section
          className="rounded-xl p-3"
          style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
        >
          <OverrideLog overrides={overrides} />
        </section>
      </div>
    </div>
  )
}
