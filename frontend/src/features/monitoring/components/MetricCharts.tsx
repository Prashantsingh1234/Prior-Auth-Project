import { useMemo } from 'react'
import {
  AreaChart, Area, LineChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import type { LiveMetrics, MetricPoint } from '../hooks/useMonitoringData'

// ─── Chart config ─────────────────────────────────────────────────────────────

interface ChartConfig {
  key:       keyof LiveMetrics
  label:     string
  unit:      string
  color:     string
  goodDir:   'up' | 'down'
  goodBelow?: number
  goodAbove?: number
  format?:   (v: number) => string
}

const CHARTS: ChartConfig[] = [
  { key: 'hallucinationRate',  label: 'Hallucination Rate',   unit: '%',   color: '#ef4444', goodDir: 'down', goodBelow: 3 },
  { key: 'groundingScore',     label: 'Grounding Score',      unit: '%',   color: '#10b981', goodDir: 'up',   goodAbove: 88 },
  { key: 'retrievalQuality',   label: 'Retrieval Quality',    unit: '%',   color: '#6366f1', goodDir: 'up',   goodAbove: 90 },
  { key: 'ocrAccuracy',        label: 'OCR Accuracy',         unit: '%',   color: '#0ea5e9', goodDir: 'up',   goodAbove: 96 },
  { key: 'clarificationFreq',  label: 'Clarification Freq.',  unit: '%',   color: '#f59e0b', goodDir: 'down', goodBelow: 12 },
  { key: 'modelLatency',       label: 'Model Latency',        unit: 'ms',  color: '#8b5cf6', goodDir: 'down', goodBelow: 1500, format: (v) => `${Math.round(v)}ms` },
  { key: 'tokenUsage',         label: 'Tokens / Request',     unit: '',    color: '#a855f7', goodDir: 'down', format: (v) => `${Math.round(v)}` },
  { key: 'fallbackFrequency',  label: 'Fallback Frequency',   unit: '%',   color: '#f97316', goodDir: 'down', goodBelow: 4 },
  { key: 'queueBacklog',       label: 'Queue Backlog',        unit: '',    color: '#64748b', goodDir: 'down', goodBelow: 20, format: (v) => Math.round(v).toString() },
  { key: 'reviewerAgreement',  label: 'Reviewer Agreement',   unit: '%',   color: '#14b8a6', goodDir: 'up',   goodAbove: 87 },
]

// ─── Custom tooltip ───────────────────────────────────────────────────────────

function ChartTooltip({ active, payload, unit, format }: {
  active?: boolean; payload?: Array<{ value: number }>; unit: string; format?: (v: number) => string
}) {
  if (!active || !payload?.[0]) return null
  const v = payload[0].value
  return (
    <div className="px-2 py-1 rounded-md text-xs font-mono"
         style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-1)' }}>
      {format ? format(v) : `${v.toFixed(1)}${unit}`}
    </div>
  )
}

// ─── Single metric card ───────────────────────────────────────────────────────

interface MetricCardProps {
  config: ChartConfig
  data:   MetricPoint[]
}

function MetricCard({ config, data }: MetricCardProps) {
  const { label, unit, color, goodDir, goodBelow, goodAbove, format } = config

  const latest = data[data.length - 1]?.v ?? 0
  const prev   = data[Math.max(0, data.length - 6)]?.v ?? latest
  const delta  = latest - prev

  const isGood = goodDir === 'down'
    ? (goodBelow !== undefined ? latest <= goodBelow : true)
    : (goodAbove !== undefined ? latest >= goodAbove : true)

  const statusColor = isGood ? '#10b981' : Math.abs(delta) < 0.5 ? '#f59e0b' : '#ef4444'

  const chartData = useMemo(() =>
    data.map((p) => ({ v: p.v })),
    [data],
  )

  const displayVal = format ? format(latest) : `${latest.toFixed(unit === 'ms' ? 0 : 1)}${unit}`

  return (
    <motion.div
      layout
      className="rounded-xl p-3 flex flex-col gap-2 relative overflow-hidden"
      style={{ background: 'var(--elevated)', border: `1px solid ${color}20` }}
    >
      {/* Glow */}
      {!isGood && (
        <motion.div
          className="absolute inset-0 rounded-xl"
          animate={{ opacity: [0, 0.06, 0] }}
          transition={{ duration: 2, repeat: Infinity }}
          style={{ background: '#ef4444' }}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between relative z-10">
        <span className="text-[10px] font-semibold text-[var(--text-3)] uppercase tracking-wide">{label}</span>
        <div className="flex items-center gap-1">
          {Math.abs(delta) < 0.1
            ? <Minus className="w-2.5 h-2.5" style={{ color: '#6b7280' }} />
            : delta < 0
              ? <TrendingDown className="w-2.5 h-2.5" style={{ color: goodDir === 'down' ? '#10b981' : '#ef4444' }} />
              : <TrendingUp   className="w-2.5 h-2.5" style={{ color: goodDir === 'up'   ? '#10b981' : '#ef4444' }} />
          }
          <span className="text-[9px] font-mono" style={{ color: statusColor }}>
            {delta >= 0 ? '+' : ''}{delta.toFixed(1)}{unit === 'ms' ? 'ms' : unit}
          </span>
        </div>
      </div>

      {/* Value */}
      <div className="relative z-10">
        <span className="text-xl font-bold tabular-nums font-mono" style={{ color }}>
          {displayVal}
        </span>
        <div className="w-1.5 h-1.5 rounded-full inline-block ml-1.5 mb-0.5"
             style={{ background: statusColor }} />
      </div>

      {/* Sparkline */}
      <div className="h-16 relative z-10 -mx-1">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
            <defs>
              <linearGradient id={`grad-${config.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"   stopColor={color} stopOpacity={0.3} />
                <stop offset="95%"  stopColor={color} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <Area
              type="monotone"
              dataKey="v"
              stroke={color}
              strokeWidth={1.5}
              fill={`url(#grad-${config.key})`}
              dot={false}
              isAnimationActive={false}
            />
            <Tooltip content={<ChartTooltip unit={unit} format={format} />} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  )
}

// ─── Combined latency line chart ──────────────────────────────────────────────

function LatencyDetailChart({ data }: { data: MetricPoint[] }) {
  const chartData = useMemo(() =>
    data.slice(-30).map((p, i) => ({ i, v: p.v, p95: p.v * 1.54 })),
    [data],
  )
  return (
    <div
      className="rounded-xl p-4 col-span-2"
      style={{ background: 'var(--elevated)', border: '1px solid #8b5cf620' }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] font-semibold text-[var(--text-2)]">Model Latency — Avg vs P95</span>
        <div className="flex items-center gap-3 text-[9px] text-[var(--text-4)]">
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 rounded inline-block bg-[#8b5cf6]" /> Avg</span>
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 rounded inline-block bg-[#ef4444]" /> P95</span>
        </div>
      </div>
      <div className="h-28">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 2, right: 4, left: 4, bottom: 2 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" strokeOpacity={0.4} />
            <XAxis dataKey="i" hide />
            <YAxis
              tickFormatter={(v) => `${Math.round(v)}ms`}
              tick={{ fontSize: 8, fill: 'var(--text-4)' }}
              width={44}
            />
            <Tooltip
              formatter={(v: number) => [`${Math.round(v)}ms`]}
              contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', fontSize: 10 }}
            />
            <Line type="monotone" dataKey="v"   stroke="#8b5cf6" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="p95" stroke="#ef4444" strokeWidth={1.5} strokeDasharray="4 2" dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ─── Main grid ────────────────────────────────────────────────────────────────

interface MetricChartsProps {
  metrics: LiveMetrics
}

export function MetricCharts({ metrics }: MetricChartsProps) {
  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 gap-3 mb-4">
        {CHARTS.map((cfg) => (
          <MetricCard key={cfg.key} config={cfg} data={metrics[cfg.key]} />
        ))}
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <LatencyDetailChart data={metrics.modelLatency} />
      </div>
    </div>
  )
}
