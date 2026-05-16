import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { RefreshCw, TrendingUp, Clock } from 'lucide-react'
import { useUIStore } from '@/store/uiStore'
import { useKPIMetrics, useSystemStats } from './hooks/useDashboardData'
import { KPIGrid }                from './widgets/KPIGrid'
import { AIActivityFeed }         from './widgets/AIActivityFeed'
import { ReviewerWorkload }       from './widgets/ReviewerWorkload'
import { ConfidenceTrends }       from './widgets/ConfidenceTrends'
import { SystemMetrics }          from './widgets/SystemMetrics'
import { OutcomeDistribution }    from './widgets/OutcomeDistribution'
import { ClarificationFrequency } from './widgets/ClarificationFrequency'

// ─── Live indicator ───────────────────────────────────────────────────────────

function LiveBadge() {
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
      <span className="text-[10px] font-medium text-emerald-400">LIVE</span>
    </div>
  )
}

// ─── Header stat ─────────────────────────────────────────────────────────────

function HeaderStat({ icon: Icon, label, value, color }: {
  icon: React.ElementType; label: string; value: string; color: string
}) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl" style={{ background: 'var(--elevated)' }}>
      <Icon style={{ color, width: 13, height: 13 }} />
      <span className="text-[10px] text-[var(--text-4)]">{label}</span>
      <span className="text-[11px] font-semibold tabular-nums" style={{ color }}>{value}</span>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function DashboardPage() {
  const addTab     = useUIStore((s) => s.addTab)
  const { data: kpi } = useKPIMetrics()
  const { data: sys } = useSystemStats()

  // Register dashboard tab
  useEffect(() => {
    addTab({
      title: 'Dashboard',
      path: '/dashboard',
      type: 'dashboard',
      closeable: false,
    })
  }, [addTab])

  const avgMs  = kpi?.avgReviewMs ?? 3500
  const avgSec = (avgMs / 1000).toFixed(1)
  const aiAcc  = kpi?.aiAccuracy ?? 0.942

  return (
    <div className="min-h-full p-6 space-y-6">

      {/* Page header */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-start justify-between flex-wrap gap-4"
      >
        <div>
          <h1 className="text-xl font-bold text-[var(--text-1)]">Operations Dashboard</h1>
          <p className="text-sm text-[var(--text-4)] mt-0.5">
            Prior Authorization · Real-time overview
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <LiveBadge />
          <HeaderStat icon={TrendingUp} label="AI Accuracy"  value={`${(aiAcc * 100).toFixed(1)}%`}  color="#8b5cf6" />
          <HeaderStat icon={Clock}      label="Avg Review"   value={`${avgSec}s`}                     color="#0ea5e9" />
          <HeaderStat icon={RefreshCw}  label="OCR Rate"     value={`${((sys?.ocrSuccessRate ?? 0.974) * 100).toFixed(1)}%`} color="#10b981" />
        </div>
      </motion.div>

      {/* KPI cards */}
      <KPIGrid />

      {/* Main grid — two columns */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

        {/* Left column — 2/3 width */}
        <div className="xl:col-span-2 space-y-6">
          <ConfidenceTrends />
          <ReviewerWorkload />
          <ClarificationFrequency />
        </div>

        {/* Right column — 1/3 width */}
        <div className="space-y-6">
          <OutcomeDistribution />
          <SystemMetrics />
        </div>
      </div>

      {/* Full-width activity feed */}
      <AIActivityFeed />

    </div>
  )
}
