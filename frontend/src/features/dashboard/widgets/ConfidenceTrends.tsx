import { motion } from 'framer-motion'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import { useConfidenceTrend } from '../hooks/useDashboardData'

// ─── Tooltip ──────────────────────────────────────────────────────────────────

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null

  const bands = [
    { key: 'high',     label: 'High ≥85%',    color: '#10b981' },
    { key: 'good',     label: 'Good 70-84%',  color: '#0ea5e9' },
    { key: 'medium',   label: 'Medium 55-69%',color: '#f59e0b' },
    { key: 'low',      label: 'Low 40-54%',   color: '#f97316' },
    { key: 'critical', label: 'Critical <40%',color: '#ef4444' },
  ]

  return (
    <div
      className="px-3 py-2.5 rounded-xl text-xs shadow-lg"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      <p className="font-semibold text-[var(--text-1)] mb-2">{label}</p>
      {bands.map(({ key, label: bandLabel, color }) => {
        const entry = payload.find((p: any) => p.dataKey === key)
        if (!entry) return null
        return (
          <div key={key} className="flex items-center gap-2 py-0.5">
            <span className="w-2 h-2 rounded-full" style={{ background: color }} />
            <span className="text-[var(--text-3)]">{bandLabel}</span>
            <span className="ml-auto font-mono font-medium text-[var(--text-1)]">{entry.value}</span>
          </div>
        )
      })}
    </div>
  )
}

// ─── Legend ───────────────────────────────────────────────────────────────────

const BANDS = [
  { key: 'high',     label: '≥85%',  color: '#10b981' },
  { key: 'good',     label: '70–84%',color: '#0ea5e9' },
  { key: 'medium',   label: '55–69%',color: '#f59e0b' },
  { key: 'low',      label: '40–54%',color: '#f97316' },
  { key: 'critical', label: '<40%',  color: '#ef4444' },
]

// ─── Component ────────────────────────────────────────────────────────────────

export function ConfidenceTrends() {
  const { data: trend = [] } = useConfidenceTrend()

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15, duration: 0.35 }}
      className="rounded-2xl overflow-hidden"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div className="px-5 pt-4 pb-3 border-b border-[var(--border)]">
        <h3 className="text-sm font-semibold text-[var(--text-1)]">AI Confidence Distribution</h3>
        <p className="text-[11px] text-[var(--text-4)] mt-0.5">7-day confidence band breakdown</p>
      </div>

      {/* Chart */}
      <div className="px-2 pt-4 pb-3">
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={trend} margin={{ top: 0, right: 16, left: -16, bottom: 0 }} stackOffset="expand">
            <defs>
              {BANDS.map(({ key, color }) => (
                <linearGradient key={key} id={`cg-${key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={color} stopOpacity={0.7} />
                  <stop offset="95%" stopColor={color} stopOpacity={0.3} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fill: 'var(--text-4)', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tickFormatter={(v) => `${Math.round(v * 100)}%`}
              tick={{ fill: 'var(--text-4)', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ stroke: 'var(--border)' }} />
            {BANDS.map(({ key, color }) => (
              <Area
                key={key}
                type="monotone"
                dataKey={key}
                stackId="1"
                stroke={color}
                strokeWidth={1.5}
                fill={`url(#cg-${key})`}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>

        {/* Legend */}
        <div className="flex items-center gap-3 justify-center mt-3 flex-wrap">
          {BANDS.map(({ key, label, color }) => (
            <div key={key} className="flex items-center gap-1.5">
              <span className="w-2.5 h-2 rounded-sm" style={{ background: color }} />
              <span className="text-[10px] text-[var(--text-3)]">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  )
}
