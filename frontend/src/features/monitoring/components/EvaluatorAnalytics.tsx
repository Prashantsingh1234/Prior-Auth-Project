import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  BarChart, Bar, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
  RadialBarChart, RadialBar,
} from 'recharts'
import { TrendingUp, TrendingDown, Minus, ChevronDown, ChevronRight } from 'lucide-react'
import type { EvaluatorScore } from '../hooks/useMonitoringData'

// ─── Score ring ───────────────────────────────────────────────────────────────

function ScoreRing({ score, color }: { score: number; color: string }) {
  const r  = 22
  const cx = 28
  const cy = 28
  const circumference = 2 * Math.PI * r
  const dashOffset = circumference * (1 - score / 100)

  return (
    <svg width={56} height={56} className="shrink-0">
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--surface)" strokeWidth={4} />
      <motion.circle
        cx={cx} cy={cy} r={r}
        fill="none"
        stroke={color}
        strokeWidth={4}
        strokeLinecap="round"
        strokeDasharray={circumference}
        initial={{ strokeDashoffset: circumference }}
        animate={{ strokeDashoffset: dashOffset }}
        transition={{ duration: 1, ease: 'easeOut', delay: 0.1 }}
        transform={`rotate(-90 ${cx} ${cy})`}
      />
      <text x={cx} y={cy + 4} textAnchor="middle" fontSize={10} fontWeight="bold" fill={color} fontFamily="monospace">
        {Math.round(score)}
      </text>
    </svg>
  )
}

// ─── Breakdown bar ────────────────────────────────────────────────────────────

function BreakdownBar({ breakdown, total }: {
  breakdown: Array<{ label: string; count: number; color: string }>;
  total: number;
}) {
  return (
    <div className="w-full h-3 flex rounded-full overflow-hidden">
      {breakdown.map((b, i) => (
        <motion.div
          key={b.label}
          initial={{ width: 0 }}
          animate={{ width: `${(b.count / total) * 100}%` }}
          transition={{ duration: 0.7, delay: i * 0.1, ease: 'easeOut' }}
          title={`${b.label}: ${b.count}`}
          style={{ background: b.color, minWidth: b.count > 0 ? 2 : 0 }}
        />
      ))}
    </div>
  )
}

// ─── Evaluator card ───────────────────────────────────────────────────────────

function EvaluatorCard({ ev }: { ev: EvaluatorScore }) {
  const [open, setOpen] = useState(false)
  const total = ev.breakdown.reduce((s, b) => s + b.count, 0)

  const trendColor = ev.trend > 0.5 ? '#10b981' : ev.trend < -0.5 ? '#ef4444' : '#6b7280'
  const TrendIcon  = ev.trend > 0.5 ? TrendingUp : ev.trend < -0.5 ? TrendingDown : Minus

  const scoreColor = ev.score >= 90 ? '#10b981' : ev.score >= 80 ? '#6366f1' : ev.score >= 70 ? '#f59e0b' : '#ef4444'

  const barData = ev.breakdown.map((b) => ({ name: b.label, v: b.count, color: b.color }))

  return (
    <motion.div
      layout
      className="rounded-xl overflow-hidden"
      style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
    >
      <button
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-[var(--surface)]/40 transition-colors"
        onClick={() => setOpen((v) => !v)}
      >
        <ScoreRing score={ev.score} color={scoreColor} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs font-bold text-[var(--text-1)]">{ev.criterion}</p>
            <div className="flex items-center gap-1.5">
              <TrendIcon className="w-3 h-3" style={{ color: trendColor }} />
              <span className="text-[9px] font-mono" style={{ color: trendColor }}>
                {ev.trend >= 0 ? '+' : ''}{ev.trend.toFixed(1)}%
              </span>
            </div>
          </div>
          <BreakdownBar breakdown={ev.breakdown} total={total} />
          <div className="flex items-center justify-between mt-1.5">
            <span className="text-[9px] text-[var(--text-4)]">Pass rate: <span className="font-semibold text-[var(--text-2)]">{ev.passRate}%</span></span>
            <span className="text-[9px] text-[var(--text-4)]">{ev.sampleCount} samples</span>
          </div>
        </div>

        {open ? <ChevronDown className="w-3.5 h-3.5 text-[var(--text-4)] shrink-0" /> : <ChevronRight className="w-3.5 h-3.5 text-[var(--text-4)] shrink-0" />}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 border-t border-[var(--border)] pt-3">
              <div className="grid grid-cols-2 gap-4">
                {/* Count breakdown bar chart */}
                <div>
                  <p className="text-[9px] text-[var(--text-4)] uppercase tracking-wide mb-2">Result Breakdown</p>
                  <div className="h-28">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={barData} margin={{ top: 2, right: 4, left: 4, bottom: 2 }}>
                        <XAxis dataKey="name" tick={{ fontSize: 8, fill: 'var(--text-4)' }} />
                        <YAxis tick={{ fontSize: 8, fill: 'var(--text-4)' }} width={24} />
                        <Bar dataKey="v" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                          {barData.map((d, i) => <Cell key={i} fill={d.color} />)}
                        </Bar>
                        <Tooltip
                          formatter={(v: number) => [v, 'Count']}
                          contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', fontSize: 9 }}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Radial gauge */}
                <div>
                  <p className="text-[9px] text-[var(--text-4)] uppercase tracking-wide mb-2">Pass Rate</p>
                  <div className="h-28 flex items-center justify-center">
                    <div className="relative">
                      <ResponsiveContainer width={112} height={112}>
                        <RadialBarChart
                          innerRadius={32}
                          outerRadius={52}
                          startAngle={180}
                          endAngle={0}
                          data={[{ v: ev.passRate, fill: scoreColor }]}
                        >
                          <RadialBar dataKey="v" cornerRadius={4} />
                        </RadialBarChart>
                      </ResponsiveContainer>
                      <div className="absolute inset-0 flex items-end justify-center pb-3">
                        <span className="text-sm font-bold font-mono" style={{ color: scoreColor }}>{ev.passRate}%</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Per-category stats */}
              <div className="flex items-center gap-4 mt-2">
                {ev.breakdown.map((b) => (
                  <div key={b.label} className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-sm inline-block" style={{ background: b.color }} />
                    <span className="text-[9px] text-[var(--text-3)]">{b.label}</span>
                    <span className="text-[9px] font-mono font-semibold text-[var(--text-1)]">{b.count}</span>
                    <span className="text-[8px] text-[var(--text-4)]">({((b.count / total) * 100).toFixed(0)}%)</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// ─── Summary row ──────────────────────────────────────────────────────────────

function OverallSummary({ evaluators }: { evaluators: EvaluatorScore[] }) {
  const avgScore   = evaluators.reduce((s, e) => s + e.score, 0) / evaluators.length
  const avgPass    = evaluators.reduce((s, e) => s + e.passRate, 0) / evaluators.length
  const totalFails = evaluators.reduce((s, e) => s + (e.breakdown.find((b) => b.label === 'Fail')?.count ?? 0), 0)
  const improving  = evaluators.filter((e) => e.trend > 0).length

  const items = [
    { label: 'Overall Score', value: avgScore.toFixed(1), unit: '%', color: '#6366f1' },
    { label: 'Avg Pass Rate', value: avgPass.toFixed(1),  unit: '%', color: '#10b981' },
    { label: 'Total Failures', value: totalFails.toString(), unit: '', color: '#ef4444' },
    { label: 'Improving Criteria', value: `${improving}/${evaluators.length}`, unit: '', color: '#f59e0b' },
  ]

  return (
    <div className="grid grid-cols-4 gap-3 mb-4">
      {items.map((item) => (
        <div
          key={item.label}
          className="rounded-xl px-4 py-3"
          style={{ background: 'var(--elevated)', border: `1px solid ${item.color}20` }}
        >
          <p className="text-[9px] uppercase tracking-wide font-semibold text-[var(--text-4)]">{item.label}</p>
          <p className="text-lg font-bold font-mono mt-0.5" style={{ color: item.color }}>
            {item.value}<span className="text-xs ml-0.5">{item.unit}</span>
          </p>
        </div>
      ))}
    </div>
  )
}

// ─── Main ─────────────────────────────────────────────────────────────────────

interface EvaluatorAnalyticsProps {
  evaluators: EvaluatorScore[]
}

export function EvaluatorAnalytics({ evaluators }: EvaluatorAnalyticsProps) {
  return (
    <div className="flex-1 overflow-y-auto p-4">
      <OverallSummary evaluators={evaluators} />
      <div className="space-y-3">
        {evaluators.map((ev) => (
          <EvaluatorCard key={ev.criterion} ev={ev} />
        ))}
      </div>
    </div>
  )
}
