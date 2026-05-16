import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  PieChart, Pie, Cell, Tooltip,
  ResponsiveContainer, Sector,
} from 'recharts'
import { useOutcomes } from '../hooks/useDashboardData'

// ─── Active sector ────────────────────────────────────────────────────────────

function ActiveShape(props: any) {
  const {
    cx, cy, innerRadius, outerRadius, startAngle, endAngle,
    fill, payload, percent, value,
  } = props

  return (
    <g>
      <text x={cx} y={cy - 10} textAnchor="middle" fill="var(--text-1)" className="text-base font-bold">
        {value.toLocaleString()}
      </text>
      <text x={cx} y={cy + 10} textAnchor="middle" fill="var(--text-4)" fontSize={11}>
        {payload.name}
      </text>
      <text x={cx} y={cy + 26} textAnchor="middle" fill={fill} fontSize={10} fontWeight={600}>
        {(percent * 100).toFixed(1)}%
      </text>
      <Sector
        cx={cx} cy={cy}
        innerRadius={innerRadius}
        outerRadius={outerRadius + 8}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
      />
      <Sector
        cx={cx} cy={cy}
        innerRadius={outerRadius + 12}
        outerRadius={outerRadius + 14}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
      />
    </g>
  )
}

// ─── Tooltip ──────────────────────────────────────────────────────────────────

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const d = payload[0]
  return (
    <div
      className="px-3 py-2 rounded-xl text-xs shadow-lg"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      <span className="font-semibold" style={{ color: d.payload.color }}>{d.name}</span>
      <span className="ml-2 text-[var(--text-1)] font-mono">{d.value.toLocaleString()}</span>
      <span className="ml-1.5 text-[var(--text-4)]">({(d.payload.percent * 100).toFixed(1)}%)</span>
    </div>
  )
}

// ─── Component ────────────────────────────────────────────────────────────────

export function OutcomeDistribution() {
  const { data: outcomes = [] } = useOutcomes()
  const [activeIdx, setActiveIdx] = useState(0)

  const total = outcomes.reduce((s, o) => s + o.value, 0)
  const enriched = outcomes.map((o) => ({ ...o, percent: o.value / total }))

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
        <h3 className="text-sm font-semibold text-[var(--text-1)]">Outcome Distribution</h3>
        <p className="text-[11px] text-[var(--text-4)] mt-0.5">{total.toLocaleString()} total decisions</p>
      </div>

      <div className="flex flex-col items-center gap-3 px-4 pt-4 pb-5">
        <ResponsiveContainer width="100%" height={200}>
          <PieChart>
            <Pie
              activeIndex={activeIdx}
              activeShape={ActiveShape}
              data={enriched}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={80}
              dataKey="value"
              onMouseEnter={(_, idx) => setActiveIdx(idx)}
            >
              {enriched.map((entry, i) => (
                <Cell key={i} fill={entry.color} stroke="none" />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>

        {/* Legend */}
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 w-full">
          {enriched.map((o, i) => (
            <button
              key={o.name}
              onClick={() => setActiveIdx(i)}
              className="flex items-center gap-2 text-left transition-opacity hover:opacity-100"
              style={{ opacity: activeIdx === i ? 1 : 0.6 }}
            >
              <span
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{ background: o.color, boxShadow: activeIdx === i ? `0 0 6px ${o.color}` : 'none' }}
              />
              <div>
                <p className="text-[10px] font-medium text-[var(--text-2)]">{o.name}</p>
                <p className="text-[9px] text-[var(--text-4)] tabular-nums">
                  {o.value.toLocaleString()} · {(o.percent * 100).toFixed(1)}%
                </p>
              </div>
            </button>
          ))}
        </div>
      </div>
    </motion.div>
  )
}
