import { motion } from 'framer-motion'
import { Activity, Zap, Eye } from 'lucide-react'
import { useSystemStats } from '../hooks/useDashboardData'

// ─── Gauge ring ───────────────────────────────────────────────────────────────

function GaugeRing({
  value, max = 1, size = 64, strokeWidth = 5,
  color, label, sublabel,
}: {
  value: number; max?: number; size?: number; strokeWidth?: number
  color: string; label: string; sublabel?: string
}) {
  const r = (size - strokeWidth * 2) / 2
  const circ = 2 * Math.PI * r
  const pct = Math.min(value / max, 1)
  const dash = circ * pct
  const cx = size / 2

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
          <circle cx={cx} cy={cx} r={r} fill="none" stroke="var(--border)" strokeWidth={strokeWidth} />
          <motion.circle
            cx={cx} cy={cx} r={r} fill="none"
            stroke={color} strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={`${circ}`}
            initial={{ strokeDashoffset: circ }}
            animate={{ strokeDashoffset: circ - dash }}
            transition={{ duration: 0.8, ease: 'easeOut' }}
            style={{ filter: `drop-shadow(0 0 4px ${color}66)` }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-[11px] font-bold tabular-nums" style={{ color }}>
            {Math.round(pct * 100)}%
          </span>
        </div>
      </div>
      <div className="text-center">
        <p className="text-[10px] font-medium text-[var(--text-2)]">{label}</p>
        {sublabel && <p className="text-[9px] text-[var(--text-4)]">{sublabel}</p>}
      </div>
    </div>
  )
}

// ─── Latency bar ──────────────────────────────────────────────────────────────

function LatencyBar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = Math.min(value / max, 1) * 100
  return (
    <div className="flex items-center gap-3">
      <span className="text-[10px] text-[var(--text-4)] w-8 flex-shrink-0 font-mono">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-[var(--elevated)] overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ background: color, boxShadow: `0 0 6px ${color}88` }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.7, ease: 'easeOut' }}
        />
      </div>
      <span className="text-[10px] font-mono tabular-nums text-[var(--text-2)] w-14 text-right flex-shrink-0">
        {value.toLocaleString()}ms
      </span>
    </div>
  )
}

// ─── Token usage bar ─────────────────────────────────────────────────────────

function TokenBar({ used, budget }: { used: number; budget: number }) {
  const pct = (used / budget) * 100
  const color = pct > 80 ? '#ef4444' : pct > 60 ? '#f59e0b' : '#10b981'
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-[var(--text-3)]">Token usage today</span>
        <span className="text-[10px] font-mono text-[var(--text-2)] tabular-nums">
          {(used / 1000).toFixed(1)}k / {(budget / 1000).toFixed(0)}k
        </span>
      </div>
      <div className="h-2 rounded-full bg-[var(--elevated)] overflow-hidden">
        <motion.div
          className="h-full rounded-full transition-colors duration-300"
          style={{ background: color, boxShadow: `0 0 8px ${color}66` }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
      </div>
      <p className="text-[9px] text-[var(--text-4)]">{pct.toFixed(1)}% of daily budget</p>
    </div>
  )
}

// ─── Stat pill ────────────────────────────────────────────────────────────────

function StatPill({ icon: Icon, label, value, color }: {
  icon: React.ElementType; label: string; value: string | number; color: string
}) {
  return (
    <div
      className="flex items-center gap-2.5 px-3 py-2 rounded-xl"
      style={{ background: `${color}10`, border: `1px solid ${color}25` }}
    >
      <Icon style={{ color, width: 14, height: 14 }} />
      <div>
        <p className="text-[9px] text-[var(--text-4)]">{label}</p>
        <p className="text-[11px] font-semibold tabular-nums" style={{ color }}>{value}</p>
      </div>
    </div>
  )
}

// ─── Component ────────────────────────────────────────────────────────────────

export function SystemMetrics() {
  const { data: stats } = useSystemStats()

  const s = stats ?? {
    ocrSuccessRate: 0.974, llmLatencyP50: 1200, llmLatencyP95: 2800, llmLatencyP99: 4100,
    policyRetrievalMs: 45, tokenUsageToday: 47832, tokenBudgetDaily: 100_000,
    guardrailTriggers: 4, avgConfidence: 0.847,
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2, duration: 0.35 }}
      className="rounded-2xl overflow-hidden"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div className="px-5 pt-4 pb-3 border-b border-[var(--border)]">
        <h3 className="text-sm font-semibold text-[var(--text-1)]">System Health</h3>
        <p className="text-[11px] text-[var(--text-4)] mt-0.5">OCR · LLM · Guardrails · Tokens</p>
      </div>

      <div className="p-5 space-y-5">
        {/* Gauge row */}
        <div className="flex items-end justify-around gap-2">
          <GaugeRing value={s.ocrSuccessRate} color="#0ea5e9" label="OCR Success" sublabel="extraction rate" />
          <GaugeRing value={s.avgConfidence}  color="#8b5cf6" label="AI Confidence" sublabel="avg confidence" />
          <GaugeRing value={s.tokenUsageToday} max={s.tokenBudgetDaily} color="#f59e0b" label="Token Budget" sublabel="daily used" />
        </div>

        {/* LLM latency */}
        <div className="space-y-2">
          <p className="text-[11px] font-medium text-[var(--text-2)] flex items-center gap-1.5">
            <Zap className="w-3 h-3 text-violet-400" /> LLM Latency
          </p>
          <LatencyBar label="P50" value={s.llmLatencyP50} max={5000} color="#10b981" />
          <LatencyBar label="P95" value={s.llmLatencyP95} max={5000} color="#f59e0b" />
          <LatencyBar label="P99" value={s.llmLatencyP99} max={5000} color="#ef4444" />
        </div>

        {/* Token bar */}
        <TokenBar used={s.tokenUsageToday} budget={s.tokenBudgetDaily} />

        {/* Stat pills */}
        <div className="grid grid-cols-2 gap-2">
          <StatPill icon={Activity}  label="Policy retrieval" value={`${s.policyRetrievalMs}ms`}     color="#0ea5e9" />
          <StatPill icon={Eye}       label="Guardrail triggers" value={s.guardrailTriggers}           color="#f97316" />
        </div>
      </div>
    </motion.div>
  )
}
