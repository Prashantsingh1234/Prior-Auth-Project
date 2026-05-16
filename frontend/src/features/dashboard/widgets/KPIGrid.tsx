import { useEffect } from 'react'
import { motion, useSpring, useTransform } from 'framer-motion'
import {
  FileText, CheckCircle2, XCircle, Clock,
  TrendingUp, TrendingDown, Minus,
} from 'lucide-react'
import { useKPIMetrics, type KPIMetrics } from '../hooks/useDashboardData'

// ─── Animated number ──────────────────────────────────────────────────────────

function AnimatedNumber({ value, format }: { value: number; format?: (n: number) => string }) {
  const spring = useSpring(value, { stiffness: 80, damping: 20 })
  const display = useTransform(spring, (n) =>
    format ? format(n) : Math.round(n).toLocaleString()
  )
  useEffect(() => { spring.set(value) }, [value, spring])
  return <motion.span>{display}</motion.span>
}

// ─── Sparkline ────────────────────────────────────────────────────────────────

function Sparkline({ values, color }: { values: number[]; color: string }) {
  const w = 80
  const h = 28
  const max = Math.max(...values)
  const min = Math.min(...values)
  const range = max - min || 1
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w
    const y = h - ((v - min) / range) * (h - 4) - 2
    return `${x},${y}`
  }).join(' ')
  return (
    <svg width={w} height={h} className="overflow-visible">
      <defs>
        <linearGradient id={`sg-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

// ─── Delta badge ─────────────────────────────────────────────────────────────

function Delta({ value, suffix = '%' }: { value: number; suffix?: string }) {
  if (value === 0) return (
    <span className="inline-flex items-center gap-0.5 text-[10px] text-[var(--text-4)]">
      <Minus className="w-2.5 h-2.5" /> 0{suffix}
    </span>
  )
  const up = value > 0
  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] font-medium ${up ? 'text-emerald-400' : 'text-red-400'}`}>
      {up ? <TrendingUp className="w-2.5 h-2.5" /> : <TrendingDown className="w-2.5 h-2.5" />}
      {up ? '+' : ''}{value}{suffix}
    </span>
  )
}

// ─── KPI Card ─────────────────────────────────────────────────────────────────

interface KPICardProps {
  label:      string
  value:      number
  delta:      number
  icon:       React.ElementType
  iconColor:  string
  glowColor:  string
  sparkData:  number[]
  format?:    (n: number) => string
  sub?:       string
  delay?:     number
}

function KPICard({ label, value, delta, icon: Icon, iconColor, glowColor, sparkData, format, sub, delay = 0 }: KPICardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.35, ease: 'easeOut' }}
      className="relative rounded-2xl p-5 overflow-hidden flex flex-col gap-3 group"
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
      }}
    >
      {/* Subtle glow on hover */}
      <div
        className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none rounded-2xl"
        style={{ background: `radial-gradient(circle at 30% 50%, ${glowColor}08 0%, transparent 70%)` }}
      />

      {/* Header */}
      <div className="flex items-start justify-between">
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{ background: `${iconColor}15` }}
        >
          <Icon className="w-4.5 h-4.5" style={{ color: iconColor, width: 18, height: 18 }} />
        </div>
        <Sparkline values={sparkData} color={glowColor} />
      </div>

      {/* Value */}
      <div>
        <div className="text-2xl font-bold text-[var(--text-1)] tabular-nums leading-none">
          <AnimatedNumber value={value} format={format} />
        </div>
        <div className="mt-1 text-xs text-[var(--text-4)]">{label}</div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between mt-auto">
        <Delta value={delta} />
        {sub && <span className="text-[10px] text-[var(--text-4)]">{sub}</span>}
      </div>
    </motion.div>
  )
}

// ─── Grid ─────────────────────────────────────────────────────────────────────

const SPARK_TOTAL    = [1210, 1223, 1231, 1238, 1241, 1244, 1247]
const SPARK_APPROVED = [608, 614, 618, 621, 625, 629, 634]
const SPARK_DENIED   = [283, 285, 286, 287, 288, 289, 290]
const SPARK_PENDING  = [220, 214, 210, 207, 205, 203, 201]

export function KPIGrid() {
  const { data } = useKPIMetrics()

  const kpi: KPIMetrics = data ?? {
    totalCases: 1247, approvedCases: 634, deniedCases: 290, pendingCases: 201,
    inReviewCases: 34, approvalRate: 0.508, denialRate: 0.232,
    avgReviewMs: 3500, aiAccuracy: 0.942,
    weekDelta: { total: 12, approved: 8, denied: 2, pending: -3 },
  }

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <KPICard
        label="Total Requests"
        value={kpi.totalCases}
        delta={kpi.weekDelta.total}
        icon={FileText}
        iconColor="#0ea5e9"
        glowColor="#0ea5e9"
        sparkData={SPARK_TOTAL}
        sub="this week"
        delay={0}
      />
      <KPICard
        label="Approved"
        value={kpi.approvedCases}
        delta={kpi.weekDelta.approved}
        icon={CheckCircle2}
        iconColor="#10b981"
        glowColor="#10b981"
        sparkData={SPARK_APPROVED}
        sub={`${(kpi.approvalRate * 100).toFixed(1)}% rate`}
        delay={0.05}
      />
      <KPICard
        label="Denied"
        value={kpi.deniedCases}
        delta={kpi.weekDelta.denied}
        icon={XCircle}
        iconColor="#ef4444"
        glowColor="#ef4444"
        sparkData={SPARK_DENIED}
        sub={`${(kpi.denialRate * 100).toFixed(1)}% rate`}
        delay={0.1}
      />
      <KPICard
        label="Pending"
        value={kpi.pendingCases}
        delta={kpi.weekDelta.pending}
        icon={Clock}
        iconColor="#f59e0b"
        glowColor="#f59e0b"
        sparkData={SPARK_PENDING}
        sub={`${kpi.inReviewCases} in review`}
        delay={0.15}
      />
    </div>
  )
}
