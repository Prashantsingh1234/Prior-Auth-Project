import { motion } from 'framer-motion'
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar,
  PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  AreaChart, Area,
} from 'recharts'
import { Brain, TrendingUp, Clock, Target, Zap, ShieldCheck } from 'lucide-react'
import { cn } from '@/lib/utils'

const ACCURACY_DATA = [
  { month: 'Oct', accuracy: 91.2, human: 89.4 },
  { month: 'Nov', accuracy: 92.1, human: 90.1 },
  { month: 'Dec', accuracy: 91.8, human: 89.9 },
  { month: 'Jan', accuracy: 93.4, human: 90.6 },
  { month: 'Feb', accuracy: 94.1, human: 91.2 },
  { month: 'Mar', accuracy: 94.2, human: 91.4 },
]

const VOLUME_DATA = [
  { week: 'W1',  submitted: 140, aiProcessed: 138, humanReviewed: 112 },
  { week: 'W2',  submitted: 165, aiProcessed: 163, humanReviewed: 128 },
  { week: 'W3',  submitted: 152, aiProcessed: 150, humanReviewed: 119 },
  { week: 'W4',  submitted: 178, aiProcessed: 176, humanReviewed: 142 },
  { week: 'W5',  submitted: 191, aiProcessed: 190, humanReviewed: 155 },
  { week: 'W6',  submitted: 185, aiProcessed: 184, humanReviewed: 148 },
]

const LATENCY_DATA = [
  { name: 'OCR', p50: 1.2, p95: 2.8, p99: 4.1 },
  { name: 'Extract', p50: 0.6, p95: 1.2, p99: 1.9 },
  { name: 'Retrieval', p50: 0.4, p95: 0.9, p99: 1.4 },
  { name: 'LLM', p50: 1.5, p95: 3.2, p99: 5.0 },
  { name: 'Total', p50: 3.5, p95: 7.2, p99: 11.3 },
]

const OUTCOME_PIE = [
  { name: 'Approved',    value: 62, color: '#10b981' },
  { name: 'Denied',      value: 21, color: '#ef4444' },
  { name: 'Pending Info',value: 11, color: '#f59e0b' },
  { name: 'Escalated',   value: 6,  color: '#8b5cf6' },
]

const CONFIDENCE_DIST = [
  { range: '0-60%', count: 8 },
  { range: '60-70%', count: 14 },
  { range: '70-80%', count: 31 },
  { range: '80-90%', count: 67 },
  { range: '90-95%', count: 84 },
  { range: '95-100%', count: 45 },
]

const KPI = [
  { label: 'AI Accuracy',     value: '94.2%',  delta: '+1.1%',  up: true,  icon: Brain,      color: 'text-violet-400', bg: 'bg-violet-500/10' },
  { label: 'Avg Latency',     value: '3.5s',   delta: '-0.4s',  up: true,  icon: Zap,        color: 'text-brand-400',  bg: 'bg-brand-500/10' },
  { label: 'Override Rate',   value: '12.3%',  delta: '-2.1%',  up: true,  icon: Target,     color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  { label: 'Time-to-Decision', value: '4.2h',  delta: '-1.1h',  up: true,  icon: Clock,      color: 'text-amber-400',  bg: 'bg-amber-500/10' },
  { label: 'Cases This Month', value: '1,247', delta: '+18%',   up: true,  icon: TrendingUp, color: 'text-sky-400',    bg: 'bg-sky-500/10' },
  { label: 'Compliance Score', value: '99.8%', delta: '+0.1%',  up: true,  icon: ShieldCheck, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
]

const TOOLTIP_STYLE = {
  contentStyle: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: '8px',
    fontSize: '12px',
    color: 'var(--text-1)',
  },
}

export function AIAnalyticsDashboard() {
  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-xl font-semibold text-[var(--text-1)]">AI Performance Analytics</h1>
        <p className="text-sm text-[var(--text-3)] mt-0.5">Last 6 months — updated hourly</p>
      </motion.div>

      {/* KPI grid */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.05 }}
        className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3"
      >
        {KPI.map(({ label, value, delta, up, icon: Icon, color, bg }, i) => (
          <motion.div
            key={label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
            className="card p-4"
          >
            <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center mb-3', bg)}>
              <Icon className={cn('w-4 h-4', color)} />
            </div>
            <p className="text-xl font-bold text-[var(--text-1)]">{value}</p>
            <p className="text-xs text-[var(--text-3)] mt-0.5 leading-snug">{label}</p>
            <p className={cn('text-xs font-medium mt-1', up ? 'text-emerald-400' : 'text-red-400')}>{delta}</p>
          </motion.div>
        ))}
      </motion.div>

      {/* Row 1: Accuracy trend + Outcome distribution */}
      <div className="grid xl:grid-cols-3 gap-4">
        {/* Accuracy trend */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="xl:col-span-2 card p-5"
        >
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-sm font-semibold text-[var(--text-1)]">AI vs Human Accuracy</p>
              <p className="text-xs text-[var(--text-3)]">Agreement rate with final decisions</p>
            </div>
          </div>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={ACCURACY_DATA}>
                <defs>
                  <linearGradient id="aiGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="humanGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: 'var(--text-3)' }} axisLine={false} tickLine={false} />
                <YAxis domain={[88, 96]} tick={{ fontSize: 11, fill: 'var(--text-3)' }} axisLine={false} tickLine={false} unit="%" />
                <Tooltip {...TOOLTIP_STYLE} formatter={(v: any) => [`${v}%`]} />
                <Legend iconType="circle" iconSize={8} />
                <Area type="monotone" dataKey="accuracy" name="AI" stroke="#6366f1" fill="url(#aiGrad)" strokeWidth={2} dot={{ r: 3, fill: '#6366f1' }} />
                <Area type="monotone" dataKey="human" name="Human" stroke="#10b981" fill="url(#humanGrad)" strokeWidth={2} dot={{ r: 3, fill: '#10b981' }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Outcome pie */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="card p-5"
        >
          <p className="text-sm font-semibold text-[var(--text-1)] mb-1">Decision Outcomes</p>
          <p className="text-xs text-[var(--text-3)] mb-4">All cases this month</p>
          <div className="h-40 flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={OUTCOME_PIE}
                  cx="50%" cy="50%"
                  innerRadius={42} outerRadius={68}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {OUTCOME_PIE.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip {...TOOLTIP_STYLE} formatter={(v: any) => [`${v}%`]} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="grid grid-cols-2 gap-1.5 mt-2">
            {OUTCOME_PIE.map(({ name, value, color }) => (
              <div key={name} className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
                <span className="text-xs text-[var(--text-3)] truncate">{name}</span>
                <span className="text-xs font-semibold text-[var(--text-1)] ml-auto">{value}%</span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Row 2: Volume + Latency + Confidence dist */}
      <div className="grid xl:grid-cols-3 gap-4">
        {/* Volume */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="card p-5"
        >
          <p className="text-sm font-semibold text-[var(--text-1)] mb-1">Weekly Case Volume</p>
          <p className="text-xs text-[var(--text-3)] mb-4">Submissions vs AI processed vs reviewed</p>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={VOLUME_DATA} barGap={2}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="week" tick={{ fontSize: 11, fill: 'var(--text-3)' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: 'var(--text-3)' }} axisLine={false} tickLine={false} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Bar dataKey="submitted" name="Submitted" fill="#6366f1" radius={[2, 2, 0, 0]} />
                <Bar dataKey="aiProcessed" name="AI Processed" fill="#8b5cf6" radius={[2, 2, 0, 0]} />
                <Bar dataKey="humanReviewed" name="Reviewed" fill="#10b981" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Latency */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="card p-5"
        >
          <p className="text-sm font-semibold text-[var(--text-1)] mb-1">Workflow Latency</p>
          <p className="text-xs text-[var(--text-3)] mb-4">P50 / P95 / P99 in seconds</p>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={LATENCY_DATA} layout="vertical" barGap={2}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: 'var(--text-3)' }} axisLine={false} tickLine={false} unit="s" />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: 'var(--text-3)' }} axisLine={false} tickLine={false} width={55} />
                <Tooltip {...TOOLTIP_STYLE} formatter={(v: any) => [`${v}s`]} />
                <Bar dataKey="p50" name="P50" fill="#6366f1" radius={[0, 2, 2, 0]} />
                <Bar dataKey="p95" name="P95" fill="#8b5cf6" radius={[0, 2, 2, 0]} />
                <Bar dataKey="p99" name="P99" fill="#a78bfa" radius={[0, 2, 2, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Confidence distribution */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="card p-5"
        >
          <p className="text-sm font-semibold text-[var(--text-1)] mb-1">Confidence Distribution</p>
          <p className="text-xs text-[var(--text-3)] mb-4">AI confidence score buckets</p>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={CONFIDENCE_DIST}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="range" tick={{ fontSize: 10, fill: 'var(--text-3)' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: 'var(--text-3)' }} axisLine={false} tickLine={false} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Bar dataKey="count" name="Cases" radius={[3, 3, 0, 0]}>
                  {CONFIDENCE_DIST.map((entry, i) => (
                    <Cell
                      key={i}
                      fill={
                        entry.range.startsWith('0') || entry.range.startsWith('6') ? '#ef4444'
                        : entry.range.startsWith('7') ? '#f59e0b'
                        : '#10b981'
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>
      </div>
    </div>
  )
}