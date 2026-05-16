import { motion } from 'framer-motion'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import { useReviewerLoad } from '../hooks/useDashboardData'

// ─── Custom tooltip ───────────────────────────────────────────────────────────

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div
      className="px-3 py-2.5 rounded-xl text-xs shadow-lg"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      <p className="font-semibold text-[var(--text-1)] mb-1.5">{label}</p>
      {payload.map((entry: any) => (
        <div key={entry.name} className="flex items-center gap-2 py-0.5">
          <span className="w-2 h-2 rounded-full" style={{ background: entry.color }} />
          <span className="text-[var(--text-3)]">{entry.name}</span>
          <span className="ml-auto font-mono font-medium text-[var(--text-1)]">{entry.value}</span>
        </div>
      ))}
    </div>
  )
}

// ─── Custom legend ────────────────────────────────────────────────────────────

const LEGEND_COLORS = {
  Approved: '#10b981',
  'In Review': '#0ea5e9',
  Denied: '#ef4444',
  Pending: '#f59e0b',
}

function CustomLegend() {
  return (
    <div className="flex items-center gap-4 justify-center mt-2">
      {Object.entries(LEGEND_COLORS).map(([name, color]) => (
        <div key={name} className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm" style={{ background: color }} />
          <span className="text-[10px] text-[var(--text-3)]">{name}</span>
        </div>
      ))}
    </div>
  )
}

// ─── Component ────────────────────────────────────────────────────────────────

export function ReviewerWorkload() {
  const { data: load = [] } = useReviewerLoad()

  const chartData = load.map((r) => ({
    name:       r.name.replace('Dr. ', ''),
    Approved:   r.approved,
    'In Review': r.inReview,
    Denied:     r.denied,
    Pending:    r.pending,
  }))

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1, duration: 0.35 }}
      className="rounded-2xl overflow-hidden"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div className="px-5 pt-4 pb-3 border-b border-[var(--border)]">
        <h3 className="text-sm font-semibold text-[var(--text-1)]">Reviewer Workload</h3>
        <p className="text-[11px] text-[var(--text-4)] mt-0.5">Case distribution by reviewer</p>
      </div>

      {/* Chart */}
      <div className="px-2 pt-4 pb-2">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={chartData} margin={{ top: 0, right: 16, left: -16, bottom: 0 }} barSize={8} barGap={2}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="name"
              tick={{ fill: 'var(--text-4)', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: 'var(--text-4)', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
            <Bar dataKey="Approved"   stackId="a" fill="#10b981" radius={[0, 0, 0, 0]} />
            <Bar dataKey="In Review"  stackId="a" fill="#0ea5e9" />
            <Bar dataKey="Denied"     stackId="a" fill="#ef4444" />
            <Bar dataKey="Pending"    stackId="a" fill="#f59e0b" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
        <CustomLegend />
      </div>
    </motion.div>
  )
}
