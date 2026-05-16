import { motion } from 'framer-motion'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import { useClarifications } from '../hooks/useDashboardData'

// ─── Tooltip ──────────────────────────────────────────────────────────────────

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  const total = payload.reduce((s: number, p: any) => s + p.value, 0)
  const config = [
    { key: 'patient', label: 'Patient Info', color: '#8b5cf6' },
    { key: 'records', label: 'Medical Records', color: '#0ea5e9' },
    { key: 'policy',  label: 'Policy Criteria', color: '#f59e0b' },
  ]
  return (
    <div
      className="px-3 py-2.5 rounded-xl text-xs shadow-lg"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      <p className="font-semibold text-[var(--text-1)] mb-1.5">{label} · {total} total</p>
      {config.map(({ key, label: l, color }) => {
        const entry = payload.find((p: any) => p.dataKey === key)
        if (!entry) return null
        return (
          <div key={key} className="flex items-center gap-2 py-0.5">
            <span className="w-2 h-2 rounded-full" style={{ background: color }} />
            <span className="text-[var(--text-3)]">{l}</span>
            <span className="ml-auto font-mono font-medium text-[var(--text-1)]">{entry.value}</span>
          </div>
        )
      })}
    </div>
  )
}

// ─── Component ────────────────────────────────────────────────────────────────

export function ClarificationFrequency() {
  const { data: points = [] } = useClarifications()

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
        <h3 className="text-sm font-semibold text-[var(--text-1)]">Clarification Requests</h3>
        <p className="text-[11px] text-[var(--text-4)] mt-0.5">Daily requests by type — 7 days</p>
      </div>

      <div className="px-2 pt-4 pb-3">
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={points} margin={{ top: 0, right: 16, left: -16, bottom: 0 }} barSize={10} barGap={3}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="date"
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
            <Bar dataKey="patient" name="Patient Info"    fill="#8b5cf6" radius={[3, 3, 0, 0]} />
            <Bar dataKey="records" name="Medical Records" fill="#0ea5e9" radius={[3, 3, 0, 0]} />
            <Bar dataKey="policy"  name="Policy Criteria" fill="#f59e0b" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>

        {/* Legend */}
        <div className="flex items-center gap-4 justify-center mt-3">
          {[
            { label: 'Patient Info',    color: '#8b5cf6' },
            { label: 'Medical Records', color: '#0ea5e9' },
            { label: 'Policy Criteria', color: '#f59e0b' },
          ].map(({ label, color }) => (
            <div key={label} className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ background: color }} />
              <span className="text-[10px] text-[var(--text-3)]">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  )
}
