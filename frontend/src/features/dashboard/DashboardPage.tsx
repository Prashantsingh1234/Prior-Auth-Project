import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { TrendingUp, Clock, ChevronDown, Zap, Target } from 'lucide-react'
import { useUIStore } from '@/store/uiStore'
import { useKPIMetrics, useSystemStats } from './hooks/useDashboardData'
import { AIPulse }                from '@/components/animations/AIPulse'
import { KPIGrid }                from './widgets/KPIGrid'
import { AIActivityFeed }         from './widgets/AIActivityFeed'
import { ReviewerWorkload }       from './widgets/ReviewerWorkload'
import { ConfidenceTrends }       from './widgets/ConfidenceTrends'
import { SystemMetrics }          from './widgets/SystemMetrics'
import { OutcomeDistribution }    from './widgets/OutcomeDistribution'
import { ClarificationFrequency } from './widgets/ClarificationFrequency'
import { cn } from '@/lib/utils'

// ─── Live indicator ───────────────────────────────────────────────────────────

function LiveBadge() {
  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
      <AIPulse size={6} color="#10b981" rings={2} />
      <span className="text-[10px] font-semibold text-emerald-400 tracking-wide">LIVE</span>
    </div>
  )
}

// ─── Executive metric pill ────────────────────────────────────────────────────

function ExecStat({ icon: Icon, label, value, color, delta }: {
  icon: React.ElementType; label: string; value: string; color: string; delta?: string
}) {
  return (
    <motion.div
      whileHover={{ y: -1 }}
      className="flex items-center gap-2 px-3 py-2 rounded-xl border transition-colors"
      style={{
        background: `${color}0d`,
        borderColor: `${color}22`,
      }}
    >
      <div
        className="w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0"
        style={{ background: `${color}18` }}
      >
        <Icon style={{ color, width: 12, height: 12 }} />
      </div>
      <div>
        <p className="text-[10px] text-[var(--text-4)] leading-none">{label}</p>
        <div className="flex items-center gap-1 mt-0.5">
          <span className="text-[13px] font-bold tabular-nums leading-none" style={{ color }}>{value}</span>
          {delta && <span className="text-[10px] text-emerald-400 font-medium">{delta}</span>}
        </div>
      </div>
    </motion.div>
  )
}

// ─── Section heading ──────────────────────────────────────────────────────────

function SectionHeading({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 mb-4">
      <span className="nav-section-label" style={{ padding: 0 }}>{label}</span>
      <div className="flex-1 h-px bg-[var(--border)]" />
    </div>
  )
}

// ─── Collapsible section (mobile) ─────────────────────────────────────────────

function Section({ title, children, defaultOpen = true }: {
  title: string; children: React.ReactNode; defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between py-2 sm:pointer-events-none"
      >
        <span className="text-xs font-semibold text-[var(--text-3)] uppercase tracking-wider sm:hidden">
          {title}
        </span>
        <ChevronDown className={cn('w-4 h-4 text-[var(--text-4)] transition-transform sm:hidden', !open && '-rotate-90')} />
      </button>
      <motion.div
        initial={false}
        animate={{ height: open ? 'auto' : 0, opacity: open ? 1 : 0 }}
        transition={{ duration: 0.2 }}
        className="overflow-hidden"
      >
        {children}
      </motion.div>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function DashboardPage() {
  const addTab     = useUIStore((s) => s.addTab)
  const { data: kpi } = useKPIMetrics()
  const { data: sys } = useSystemStats()

  useEffect(() => {
    addTab({ title: 'Dashboard', path: '/dashboard', type: 'dashboard', closeable: false })
  }, [addTab])

  const avgMs  = kpi?.avgReviewMs ?? 3500
  const avgSec = (avgMs / 1000).toFixed(1)
  const aiAcc  = kpi?.aiAccuracy ?? 0.942
  const approvalRate = kpi?.approvalRate ?? 0.508

  return (
    <div className="min-h-full space-y-0 max-content">

      {/* ── Mission Control hero header ─────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="hero-mesh px-4 sm:px-6 pt-6 pb-5 border-b border-[var(--border)]"
        style={{ background: 'var(--surface)' }}
      >
        <div className="flex items-start justify-between flex-wrap gap-4">
          {/* Title block */}
          <div>
            <div className="flex items-center gap-2 mb-1">
              <LiveBadge />
              <span className="text-[10px] text-[var(--text-4)] font-medium tracking-widest uppercase">
                Prior Authorization
              </span>
            </div>
            <h1
              className="text-2xl sm:text-3xl font-bold leading-tight text-gradient-brand"
              style={{ fontFamily: 'Manrope, sans-serif', letterSpacing: '-0.02em' }}
            >
              AI Operations Center
            </h1>
            <p className="text-xs sm:text-sm text-[var(--text-3)] mt-1">
              Real-time clinical intelligence · Utilization management platform
            </p>
          </div>

          {/* Executive stats */}
          <div className="flex items-center gap-2 flex-wrap">
            <ExecStat icon={TrendingUp} label="AI Accuracy"  value={`${(aiAcc * 100).toFixed(1)}%`}       color="#8b5cf6" delta="↑ 0.3%" />
            <ExecStat icon={Clock}      label="Avg Review"   value={`${avgSec}s`}                         color="#0ea5e9" />
            <ExecStat icon={Target}     label="Approval Rate" value={`${(approvalRate * 100).toFixed(0)}%`} color="#10b981" />
            <ExecStat icon={Zap}        label="OCR Success"  value={`${((sys?.ocrSuccessRate ?? 0.974) * 100).toFixed(1)}%`} color="#f59e0b" />
          </div>
        </div>
      </motion.div>

      {/* ── Page body ────────────────────────────────────────────────────────── */}
      <div className="p-4 sm:p-6 space-y-6 sm:space-y-8">

        {/* KPI cards */}
        <div>
          <SectionHeading label="Key Performance Indicators" />
          <Section title="Key Metrics">
            <KPIGrid />
          </Section>
        </div>

        {/* Main grid — single col → 3 col */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 sm:gap-6">

          {/* Left / main column */}
          <div className="xl:col-span-2 space-y-6 sm:space-y-8">
            <div>
              <SectionHeading label="AI Confidence Trends" />
              <Section title="Confidence Trends">
                <ConfidenceTrends />
              </Section>
            </div>
            <div>
              <SectionHeading label="Reviewer Workload" />
              <Section title="Reviewer Workload">
                <ReviewerWorkload />
              </Section>
            </div>
            <div>
              <SectionHeading label="Clarification Requests" />
              <Section title="Clarification Frequency">
                <ClarificationFrequency />
              </Section>
            </div>
          </div>

          {/* Right column */}
          <div className="space-y-6 sm:space-y-8">
            <div>
              <SectionHeading label="Decision Outcomes" />
              <Section title="Outcome Distribution">
                <OutcomeDistribution />
              </Section>
            </div>
            <div>
              <SectionHeading label="System Health" />
              <Section title="System Health">
                <SystemMetrics />
              </Section>
            </div>
          </div>
        </div>

        {/* Full-width activity feed */}
        <div>
          <SectionHeading label="AI Activity Feed" />
          <Section title="AI Activity">
            <AIActivityFeed />
          </Section>
        </div>

      </div>
    </div>
  )
}
