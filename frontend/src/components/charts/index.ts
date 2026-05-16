// Re-export Recharts primitives with our project defaults applied via CSS vars.
// Import these wrappers instead of Recharts directly so chart styles stay consistent.
export {
  ResponsiveContainer, LineChart, Line, AreaChart, Area,
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts'

export const CHART_COLORS = {
  brand:   '#6366f1',
  violet:  '#8b5cf6',
  emerald: '#10b981',
  amber:   '#f59e0b',
  red:     '#ef4444',
  sky:     '#38bdf8',
  slate:   '#94a3b8',
} as const

export const DEFAULT_TOOLTIP_STYLE = {
  contentStyle: {
    background:   'var(--surface)',
    border:       '1px solid var(--border)',
    borderRadius: '8px',
    fontSize:     '12px',
    color:        'var(--text-1)',
    boxShadow:    '0 4px 16px rgba(0,0,0,0.12)',
  },
  itemStyle: { color: 'var(--text-1)' },
  cursor:    { fill: 'var(--elevated)' },
} as const

export const DEFAULT_AXIS_STYLE = {
  tick:     { fontSize: 11, fill: 'var(--text-3)' },
  axisLine: false,
  tickLine: false,
} as const