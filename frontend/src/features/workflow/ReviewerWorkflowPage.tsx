import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Activity, Bot, BarChart3, AlertTriangle,
  CheckCircle2, Clock, Users, Zap, Radio,
  ChevronLeft, ChevronRight,
} from 'lucide-react'
import { useReviewerWorkflow } from './hooks/useReviewerWorkflow'
import { ReviewerRoster }    from './components/ReviewerRoster'
import { CaseQueue }         from './components/CaseQueue'
import { AIRoutingPanel }    from './components/AIRoutingPanel'
import { ReviewerAnalytics } from './components/ReviewerAnalytics'

// ─── Right panel tabs ─────────────────────────────────────────────────────────

type RightTab = 'copilot' | 'analytics'

const RIGHT_TABS: Array<{ id: RightTab; label: string; icon: React.ElementType }> = [
  { id: 'copilot',   label: 'AI Copilot', icon: Bot },
  { id: 'analytics', label: 'Analytics',  icon: BarChart3 },
]

// ─── Mission control stat ─────────────────────────────────────────────────────

function MCStat({
  icon: Icon, label, value, color, pulse = false,
}: { icon: React.ElementType; label: string; value: string | number; color: string; pulse?: boolean }) {
  return (
    <div
      className="flex items-center gap-2 px-3 py-2 rounded-xl relative overflow-hidden"
      style={{ background: `${color}10`, border: `1px solid ${color}25` }}
    >
      {pulse && (
        <motion.div
          className="absolute inset-0 rounded-xl"
          animate={{ opacity: [0, 0.15, 0] }}
          transition={{ duration: 2, repeat: Infinity }}
          style={{ background: color }}
        />
      )}
      <Icon style={{ color, width: 13, height: 13 }} className="shrink-0 relative z-10" />
      <div className="relative z-10">
        <p className="text-[7px] uppercase tracking-widest font-bold text-[var(--text-4)] leading-none">{label}</p>
        <p className="text-sm font-bold tabular-nums font-mono leading-tight mt-0.5" style={{ color }}>{value}</p>
      </div>
    </div>
  )
}

// ─── Live ticker ──────────────────────────────────────────────────────────────

function LiveTicker({ stats }: { stats: ReturnType<typeof useReviewerWorkflow>['stats'] }) {
  const items = [
    `${stats.throughputToday} reviews completed today`,
    `${stats.unassigned} cases awaiting assignment`,
    `${stats.slaBreached} SLA breach${stats.slaBreached !== 1 ? 'es' : ''}`,
    `AI processing: ACTIVE`,
    `${stats.openEscalations} open escalation${stats.openEscalations !== 1 ? 's' : ''}`,
    `Avg priority score: ${stats.avgAIScore}`,
  ]

  return (
    <div className="flex items-center gap-1 overflow-hidden">
      <div className="flex items-center gap-1.5 shrink-0">
        <motion.div
          className="w-1.5 h-1.5 rounded-full bg-[#10b981]"
          animate={{ opacity: [1, 0.3, 1] }}
          transition={{ duration: 0.8, repeat: Infinity }}
        />
        <span className="text-[9px] font-bold uppercase tracking-wider text-[#10b981]">LIVE</span>
      </div>
      <div className="overflow-hidden flex-1">
        <motion.div
          className="flex gap-8 whitespace-nowrap"
          animate={{ x: ['0%', '-50%'] }}
          transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
        >
          {[...items, ...items].map((item, i) => (
            <span key={i} className="text-[9px] text-[var(--text-4)]">
              <span className="text-[var(--text-4)] mr-2">·</span>
              {item}
            </span>
          ))}
        </motion.div>
      </div>
    </div>
  )
}

// ─── Panel resizer ────────────────────────────────────────────────────────────

function usePanelDrag(initial: number, min: number, max: number) {
  const [width, setWidth] = useState(initial)
  function startDrag(e: React.MouseEvent, containerRef: { current: HTMLDivElement | null }) {
    e.preventDefault()
    const startX = e.clientX; const startW = width
    function onMove(ev: MouseEvent) {
      if (!containerRef.current) return
      const totalW = containerRef.current.offsetWidth
      setWidth(Math.min(max, Math.max(min, startW + ((ev.clientX - startX) / totalW) * 100)))
    }
    const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp) }
    document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp)
  }
  return { width, startDrag }
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function ReviewerWorkflowPage() {
  const wf = useReviewerWorkflow()
  const [selectedReviewer, setSelectedReviewer] = useState<string | null>(null)
  const [rightTab, setRightTab] = useState<RightTab>('copilot')
  const [rosterOpen, setRosterOpen] = useState(true)
  const containerRef = { current: null as HTMLDivElement | null }
  const leftDrag  = usePanelDrag(20, 15, 30)
  const rightDrag = usePanelDrag(26, 20, 38)

  const { stats, filteredCases } = wf

  // Quick assign unassigned to selected reviewer
  function handleQuickAssign(reviewerId: string) {
    const unassigned = filteredCases.filter((c) => c.status === 'unassigned').slice(0, 1)
    unassigned.forEach((c) => wf.assignCase(c.id, reviewerId))
  }

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden">

      {/* ── Mission Control Header ──────────────────────────────────────────── */}
      <div
        className="shrink-0 border-b border-[var(--border)]"
        style={{ background: 'var(--elevated)' }}
      >
        {/* Top row */}
        <div className="flex items-center justify-between px-5 py-3 gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: '#6366f115', border: '1px solid #6366f130' }}
            >
              <Radio className="w-4 h-4 text-[#6366f1]" />
            </div>
            <div>
              <p className="text-sm font-bold text-[var(--text-1)]">Reviewer Workflow — Mission Control</p>
              <p className="text-[10px] text-[var(--text-4)]">PA Review Queue · Real-time assignment management</p>
            </div>
          </div>

          {/* Stats row */}
          <div className="flex items-center gap-2 shrink-0 flex-wrap">
            <MCStat icon={Activity}     label="Queue"       value={stats.total}           color="#6366f1" />
            <MCStat icon={AlertTriangle} label="Unassigned" value={stats.unassigned}      color="#f59e0b" pulse={stats.unassigned > 0} />
            <MCStat icon={AlertTriangle} label="SLA Risk"   value={stats.slaAtRisk}       color={stats.slaAtRisk > 0 ? '#f59e0b' : '#6b7280'} pulse={stats.slaAtRisk > 0} />
            <MCStat icon={AlertTriangle} label="Breached"   value={stats.slaBreached}     color={stats.slaBreached > 0 ? '#ef4444' : '#6b7280'} pulse={stats.slaBreached > 0} />
            <MCStat icon={CheckCircle2}  label="Done Today" value={stats.throughputToday} color="#10b981" />
            <MCStat icon={Users}         label="Escalated"  value={stats.openEscalations} color={stats.openEscalations > 0 ? '#ef4444' : '#6b7280'} />
            <MCStat icon={Zap}           label="AI Score"   value={stats.avgAIScore}      color="#8b5cf6" />
            <MCStat icon={Clock}         label="In Review"  value={stats.inReview}        color="#0ea5e9" />
          </div>
        </div>

        {/* Live ticker */}
        <div
          className="px-5 py-1.5 border-t border-[var(--border)] flex items-center gap-3"
          style={{ background: 'rgba(0,0,0,0.15)' }}
        >
          <LiveTicker stats={stats} />
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => setRosterOpen((v) => !v)}
              className="flex items-center gap-1 text-[9px] text-[var(--text-4)] hover:text-[var(--text-2)] transition-colors px-2 py-1 rounded-md hover:bg-[var(--surface)]"
            >
              <Users className="w-3 h-3" />
              {rosterOpen ? <ChevronLeft className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            </button>
          </div>
        </div>
      </div>

      {/* ── Body ────────────────────────────────────────────────────────────── */}
      <div
        ref={(el) => { containerRef.current = el }}
        className="flex-1 min-h-0 flex overflow-hidden"
      >
        {/* LEFT — Reviewer Roster */}
        <AnimatePresence initial={false}>
          {rosterOpen && (
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: `${leftDrag.width}%`, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="shrink-0 min-h-0 overflow-hidden"
              style={{ minWidth: 200, maxWidth: 320 }}
            >
              <ReviewerRoster
                reviewers={wf.reviewers}
                cases={wf.cases}
                selectedReviewer={selectedReviewer}
                onSelect={setSelectedReviewer}
                onQuickAssign={handleQuickAssign}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Drag divider */}
        {rosterOpen && (
          <div
            className="w-1.5 cursor-col-resize hover:bg-[var(--border)] transition-colors shrink-0 rounded-full my-2"
            onMouseDown={(e) => leftDrag.startDrag(e, containerRef)}
          />
        )}

        {/* CENTER — Case Queue */}
        <div className="flex-1 min-w-0 min-h-0 overflow-hidden flex flex-col">
          <CaseQueue
            cases={filteredCases}
            reviewers={wf.reviewers}
            selectedIds={wf.selectedIds}
            filters={wf.filters}
            sortField={wf.sortField}
            sortDir={wf.sortDir}
            search={wf.search}
            totalCount={wf.cases.length}
            onToggle={wf.toggleSelected}
            onClearSelected={wf.clearSelected}
            onAssign={wf.assignCase}
            onBatchAssign={wf.batchAssign}
            onEscalate={(id) => wf.escalateCase(id, 'Manually escalated by reviewer')}
            onFilter={wf.setFilters}
            onSort={wf.setSort}
            onSearch={wf.setSearch}
          />
        </div>

        {/* Drag divider */}
        <div
          className="w-1.5 cursor-col-resize hover:bg-[var(--border)] transition-colors shrink-0 rounded-full my-2"
          onMouseDown={(e) => rightDrag.startDrag(e, containerRef)}
        />

        {/* RIGHT — AI Copilot / Analytics */}
        <div
          className="shrink-0 min-h-0 flex flex-col"
          style={{ width: `${rightDrag.width}%`, minWidth: 260, maxWidth: 420, borderLeft: '1px solid var(--border)' }}
        >
          {/* Tab bar */}
          <div
            className="flex items-center gap-1 px-3 py-2 border-b border-[var(--border)] shrink-0"
            style={{ background: 'var(--elevated)' }}
          >
            {RIGHT_TABS.map((tab) => {
              const isActive = rightTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setRightTab(tab.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-semibold transition-all flex-1 justify-center"
                  style={{
                    background: isActive ? 'var(--surface)' : 'transparent',
                    color:      isActive ? 'var(--text-1)' : 'var(--text-4)',
                    border:     `1px solid ${isActive ? 'var(--border)' : 'transparent'}`,
                  }}
                >
                  <tab.icon className="w-3 h-3" />
                  {tab.label}
                </button>
              )
            })}
          </div>

          {/* Panel content */}
          <div className="flex-1 min-h-0 overflow-hidden">
            <AnimatePresence mode="wait">
              <motion.div
                key={rightTab}
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ duration: 0.15 }}
                className="h-full"
              >
                {rightTab === 'copilot' && (
                  <AIRoutingPanel
                    routingRules={wf.routingRules}
                    cases={wf.cases}
                    escalations={wf.escalations}
                    overrides={wf.overrides}
                    onToggleRule={wf.toggleRule}
                  />
                )}
                {rightTab === 'analytics' && (
                  <ReviewerAnalytics metrics={wf.metrics} />
                )}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  )
}
