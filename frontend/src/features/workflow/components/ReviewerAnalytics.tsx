import { motion } from 'framer-motion'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import type { ReviewerMetric } from '../hooks/useReviewerWorkflow'

// ─── Sparkline ────────────────────────────────────────────────────────────────

function Sparkline({ data, color }: { data: number[]; color: string }) {
  const max = Math.max(...data, 1)
  const W   = 60
  const H   = 20
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * W},${H - (v / max) * H}`)
  const areaPoints = `0,${H} ${pts.join(' ')} ${W},${H}`

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
      <defs>
        <linearGradient id={`sg-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor={color} stopOpacity={0.25} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <polygon points={areaPoints} fill={`url(#sg-${color.replace('#', '')})`} />
      <polyline points={pts.join(' ')} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  )
}

// ─── Metric card ──────────────────────────────────────────────────────────────

function MetricKpi({
  label, value, suffix = '', trend, color,
}: {
  label: string; value: number; suffix?: string; trend: 'up' | 'down' | 'flat'; color: string
}) {
  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus
  const trendColor = trend === 'up' ? '#10b981' : trend === 'down' ? '#ef4444' : '#6b7280'
  return (
    <div className="text-center">
      <p className="text-[8px] uppercase tracking-widest font-bold text-[var(--text-4)]">{label}</p>
      <div className="flex items-center justify-center gap-1 mt-0.5">
        <span className="text-sm font-bold tabular-nums font-mono" style={{ color }}>{value}{suffix}</span>
        <TrendIcon className="w-3 h-3" style={{ color: trendColor }} />
      </div>
    </div>
  )
}

// ─── Reviewer row ─────────────────────────────────────────────────────────────

function ReviewerRow({ metric, index }: { metric: ReviewerMetric; index: number }) {
  const trend = metric.throughputTrend
  const delta = trend[trend.length - 1] - trend[0]
  const trendDir = delta > 0 ? 'up' : delta < 0 ? 'down' : 'flat'

  return (
    <motion.div
      initial={{ opacity: 0, x: 8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.06 }}
      className="rounded-xl p-3"
      style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2.5">
        <div className="flex items-center gap-2">
          <div
            className="w-6 h-6 rounded-lg flex items-center justify-center text-[9px] font-bold"
            style={{ background: `${metric.color}20`, color: metric.color }}
          >
            {metric.name.split(' ')[1][0]}{metric.name.split(' ')[2]?.[0] ?? ''}
          </div>
          <span className="text-[11px] font-bold text-[var(--text-1)]">{metric.name}</span>
        </div>
        <Sparkline data={metric.throughputTrend} color={metric.color} />
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-4 gap-1 mb-2.5">
        <MetricKpi label="Today" value={metric.today}       suffix=""   trend={trendDir}  color={metric.color} />
        <MetricKpi label="Week"  value={metric.week}        suffix=""   trend="flat"      color="var(--text-2)" />
        <MetricKpi label="Avg"   value={metric.avgMins}     suffix="m"  trend="flat"      color="var(--text-2)" />
        <MetricKpi label="Acc."  value={metric.accuracy}    suffix="%"  trend={metric.accuracy >= 96 ? 'up' : 'flat'} color={metric.accuracy >= 96 ? '#10b981' : '#f59e0b'} />
      </div>

      {/* Accuracy + Override bars */}
      <div className="space-y-1.5">
        <div>
          <div className="flex justify-between mb-0.5">
            <span className="text-[8px] text-[var(--text-4)]">Accuracy</span>
            <span className="text-[8px] font-mono" style={{ color: metric.accuracy >= 96 ? '#10b981' : '#f59e0b' }}>{metric.accuracy}%</span>
          </div>
          <div className="h-1 rounded-full bg-[var(--border)] overflow-hidden">
            <motion.div
              className="h-full rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${metric.accuracy}%` }}
              transition={{ duration: 0.6, ease: 'easeOut', delay: index * 0.05 }}
              style={{ background: metric.accuracy >= 96 ? '#10b981' : '#f59e0b' }}
            />
          </div>
        </div>
        <div>
          <div className="flex justify-between mb-0.5">
            <span className="text-[8px] text-[var(--text-4)]">Override rate</span>
            <span className="text-[8px] font-mono" style={{ color: metric.overrideRate <= 6 ? '#10b981' : metric.overrideRate <= 10 ? '#f59e0b' : '#ef4444' }}>
              {metric.overrideRate}%
            </span>
          </div>
          <div className="h-1 rounded-full bg-[var(--border)] overflow-hidden">
            <motion.div
              className="h-full rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(metric.overrideRate * 5, 100)}%` }}
              transition={{ duration: 0.6, ease: 'easeOut', delay: index * 0.05 }}
              style={{ background: metric.overrideRate <= 6 ? '#10b981' : metric.overrideRate <= 10 ? '#f59e0b' : '#ef4444' }}
            />
          </div>
        </div>
      </div>

      {metric.slaBreaches > 0 && (
        <div className="mt-2 flex items-center gap-1.5 px-2 py-1 rounded-lg" style={{ background: '#ef444412', border: '1px solid #ef444430' }}>
          <span className="text-[8px] font-bold text-[#ef4444]">{metric.slaBreaches} SLA breach{metric.slaBreaches > 1 ? 'es' : ''} this week</span>
        </div>
      )}
    </motion.div>
  )
}

// ─── Throughput chart ─────────────────────────────────────────────────────────

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function ThroughputChart({ metrics }: { metrics: ReviewerMetric[] }) {
  const data = DAYS.map((day, i) => {
    const entry: Record<string, number | string> = { day }
    metrics.forEach((m) => { entry[m.name.split(' ')[1]] = m.throughputTrend[i] ?? 0 })
    return entry
  })

  return (
    <div>
      <p className="text-[9px] uppercase tracking-widest font-bold text-[var(--text-4)] mb-3">Team Throughput — 7 Days</p>
      <ResponsiveContainer width="100%" height={100}>
        <BarChart data={data} barSize={8} barCategoryGap="30%">
          <XAxis dataKey="day" tick={{ fontSize: 9, fill: 'var(--text-4)' }} axisLine={false} tickLine={false} />
          <YAxis hide />
          <Tooltip
            contentStyle={{ background: 'var(--elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 10 }}
            cursor={{ fill: 'var(--border)', opacity: 0.5 }}
          />
          {metrics.map((m) => (
            <Bar key={m.reviewerId} dataKey={m.name.split(' ')[1]} stackId="a" fill={m.color} radius={[0, 0, 0, 0]}>
              {data.map((_, i) => <Cell key={i} fill={m.color} opacity={0.8} />)}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  metrics: ReviewerMetric[]
}

export function ReviewerAnalytics({ metrics }: Props) {
  const totalToday    = metrics.reduce((s, m) => s + m.today, 0)
  const avgAccuracy   = (metrics.reduce((s, m) => s + m.accuracy, 0) / metrics.length).toFixed(1)
  const avgOverride   = (metrics.reduce((s, m) => s + m.overrideRate, 0) / metrics.length).toFixed(1)
  const totalBreaches = metrics.reduce((s, m) => s + m.slaBreaches, 0)

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[var(--border)] shrink-0" style={{ background: 'var(--elevated)' }}>
        <span className="text-xs font-bold text-[var(--text-1)]">Reviewer Analytics</span>
      </div>

      <div className="flex-1 p-3 space-y-4">
        {/* Summary KPIs */}
        <div className="grid grid-cols-4 gap-2">
          {[
            { label: 'Reviews Today', value: totalToday, color: '#6366f1' },
            { label: 'Avg Accuracy',  value: `${avgAccuracy}%`, color: '#10b981' },
            { label: 'Override Rate', value: `${avgOverride}%`, color: '#f59e0b' },
            { label: 'SLA Breaches',  value: totalBreaches, color: totalBreaches > 0 ? '#ef4444' : '#10b981' },
          ].map((k) => (
            <div
              key={k.label}
              className="rounded-xl p-2.5 text-center"
              style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
            >
              <p className="text-[7px] uppercase tracking-widest font-bold text-[var(--text-4)]">{k.label}</p>
              <p className="text-sm font-bold tabular-nums font-mono mt-0.5" style={{ color: k.color }}>{k.value}</p>
            </div>
          ))}
        </div>

        {/* Throughput chart */}
        <div className="rounded-xl p-3" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
          <ThroughputChart metrics={metrics} />
        </div>

        {/* Per-reviewer rows */}
        <div className="space-y-2">
          <p className="text-[9px] uppercase tracking-widest font-bold text-[var(--text-4)]">Individual Performance</p>
          {metrics.map((m, i) => (
            <ReviewerRow key={m.reviewerId} metric={m} index={i} />
          ))}
        </div>
      </div>
    </div>
  )
}
