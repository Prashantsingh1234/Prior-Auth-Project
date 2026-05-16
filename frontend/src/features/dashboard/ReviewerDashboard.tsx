import { motion } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import {
  FileText, Clock, CheckCircle2, XCircle,
  TrendingUp, Brain, AlertTriangle, Zap,
} from 'lucide-react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  Tooltip, CartesianGrid,
} from 'recharts'
import { CaseQueue } from './CaseQueue'
import { cn } from '@/lib/utils'

const VOLUME_DATA = [
  { day: 'Mon', submitted: 24, approved: 18, denied: 4 },
  { day: 'Tue', submitted: 31, approved: 22, denied: 6 },
  { day: 'Wed', submitted: 28, approved: 20, denied: 5 },
  { day: 'Thu', submitted: 35, approved: 27, denied: 7 },
  { day: 'Fri', submitted: 29, approved: 21, denied: 6 },
  { day: 'Sat', submitted: 14, approved: 11, denied: 2 },
  { day: 'Sun', submitted: 9,  approved: 7,  denied: 1 },
]

const METRICS = [
  {
    label: 'Pending Review',
    value: '47',
    delta: '+3 since yesterday',
    up: false,
    icon: FileText,
    color: 'text-brand-400',
    bg: 'bg-brand-500/10',
  },
  {
    label: 'Avg. Review Time',
    value: '3.5s',
    delta: '-0.4s vs last week',
    up: true,
    icon: Zap,
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
  },
  {
    label: 'AI Accuracy',
    value: '94.2%',
    delta: '+1.1% vs last month',
    up: true,
    icon: Brain,
    color: 'text-violet-400',
    bg: 'bg-violet-500/10',
  },
  {
    label: 'Escalations',
    value: '5',
    delta: '-2 vs yesterday',
    up: true,
    icon: AlertTriangle,
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
  },
]

export function ReviewerDashboard() {
  const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.07 } },
  }
  const item = { hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0 } }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-1)]">Case Queue</h1>
          <p className="text-sm text-[var(--text-3)] mt-0.5">
            AI-assisted prior authorization review
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-[var(--text-3)]">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping-slow" />
          Live updates
        </div>
      </motion.div>

      {/* Metric cards */}
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="grid grid-cols-2 xl:grid-cols-4 gap-4"
      >
        {METRICS.map(({ label, value, delta, up, icon: Icon, color, bg }) => (
          <motion.div key={label} variants={item} className="card card-hover p-5">
            <div className="flex items-center justify-between mb-3">
              <div className={cn('w-9 h-9 rounded-lg flex items-center justify-center', bg)}>
                <Icon className={cn('w-4.5 h-4.5', color)} />
              </div>
              <span className={cn('text-xs font-medium', up ? 'text-emerald-400' : 'text-amber-400')}>
                {delta}
              </span>
            </div>
            <p className="text-2xl font-bold text-[var(--text-1)]">{value}</p>
            <p className="text-xs text-[var(--text-3)] mt-0.5">{label}</p>
          </motion.div>
        ))}
      </motion.div>

      {/* Chart + Queue */}
      <div className="grid xl:grid-cols-3 gap-4">
        {/* Volume chart */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="card p-5"
        >
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-sm font-semibold text-[var(--text-1)]">Weekly Volume</p>
              <p className="text-xs text-[var(--text-3)]">Submissions vs decisions</p>
            </div>
            <TrendingUp className="w-4 h-4 text-[var(--text-3)]" />
          </div>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={VOLUME_DATA}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: 'var(--text-3)' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: 'var(--text-3)' }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    background: 'var(--surface)',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                />
                <Line type="monotone" dataKey="submitted" stroke="#6366f1" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="approved" stroke="#10b981" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="denied" stroke="#ef4444" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="flex items-center gap-4 mt-3">
            {[
              { label: 'Submitted', color: '#6366f1' },
              { label: 'Approved',  color: '#10b981' },
              { label: 'Denied',    color: '#ef4444' },
            ].map(({ label, color }) => (
              <div key={label} className="flex items-center gap-1.5">
                <span className="w-2.5 h-0.5 rounded-full" style={{ background: color }} />
                <span className="text-xs text-[var(--text-3)]">{label}</span>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Queue spans 2 cols */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="xl:col-span-2"
        >
          <CaseQueue />
        </motion.div>
      </div>
    </div>
  )
}