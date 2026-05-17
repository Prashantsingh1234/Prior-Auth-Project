import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  CheckCircle2, Brain, LayoutGrid, GitBranch,
  BarChart3, ChevronLeft, ChevronRight,
} from 'lucide-react'
import { useReasoningData } from './hooks/useReasoningData'
import { ReasoningTimeline }  from './components/ReasoningTimeline'
import { EvidencePolicyMapper } from './components/EvidencePolicyMapper'
import { ConfidenceHeatmap }   from './components/ConfidenceHeatmap'
import { AIChainPanel }        from './components/AIChainPanel'
import { RationaleTree }       from './components/RationaleTree'
import { RAGChunksPanel }      from './components/RAGChunksPanel'

// ─── Tab config ───────────────────────────────────────────────────────────────

type ViewTab = 'timeline' | 'mapper' | 'heatmap' | 'chain' | 'tree'

interface TabCfg {
  id:    ViewTab
  label: string
  icon:  React.ElementType
  color: string
  description: string
}

const TABS: TabCfg[] = [
  { id: 'timeline', label: 'Reasoning Chain',   icon: GitBranch,   color: '#6366f1', description: 'Step-by-step AI reasoning timeline with latency and token usage' },
  { id: 'mapper',   label: 'Evidence Mapping',  icon: LayoutGrid,  color: '#0ea5e9', description: 'Bezier curve visualization linking patient evidence to policy criteria' },
  { id: 'heatmap',  label: 'Confidence Matrix', icon: BarChart3,   color: '#8b5cf6', description: 'Heatmap of AI confidence by evidence type × policy criterion' },
  { id: 'chain',    label: 'AI Execution',      icon: Brain,       color: '#a855f7', description: 'Model chain, RAG pipeline, token costs, and latency breakdown' },
  { id: 'tree',     label: 'Rationale Tree',    icon: CheckCircle2,color: '#10b981', description: 'Expandable decision tree from final outcome to evidence leaves' },
]

// ─── Decision badge ───────────────────────────────────────────────────────────

function DecisionBadge({ decision, confidence }: { decision: string; confidence: number }) {
  const color = decision === 'APPROVED' ? '#10b981' : decision === 'DENIED' ? '#ef4444' : '#f59e0b'
  return (
    <motion.div
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 260, damping: 18 }}
      className="flex items-center gap-2 px-3 py-1.5 rounded-xl"
      style={{ background: `${color}15`, border: `1px solid ${color}40` }}
    >
      <motion.div
        className="w-2 h-2 rounded-full"
        animate={{ boxShadow: [`0 0 0 0 ${color}60`, `0 0 6px 3px ${color}30`, `0 0 0 0 ${color}60`] }}
        transition={{ duration: 2, repeat: Infinity }}
        style={{ background: color }}
      />
      <span className="text-xs font-bold" style={{ color }}>{decision}</span>
      <span className="text-xs font-mono text-[var(--text-3)]">{(confidence * 100).toFixed(1)}%</span>
    </motion.div>
  )
}

// ─── Tab button ───────────────────────────────────────────────────────────────

function TabBtn({ tab, isActive, onClick }: { tab: TabCfg; isActive: boolean; onClick: () => void }) {
  const { Icon, color, label } = { Icon: tab.icon, ...tab }
  return (
    <motion.button
      whileHover={{ y: -1 }}
      whileTap={{ scale: 0.97 }}
      onClick={onClick}
      className="flex items-center gap-1.5 px-3 py-2 rounded-xl transition-all text-xs font-semibold relative whitespace-nowrap"
      style={{
        background: isActive ? `${color}15` : 'transparent',
        color:      isActive ? color : 'var(--text-4)',
        border:     `1px solid ${isActive ? `${color}40` : 'transparent'}`,
      }}
    >
      <Icon style={{ width: 13, height: 13 }} />
      {label}
      {isActive && (
        <motion.div
          layoutId="tab-indicator"
          className="absolute inset-0 rounded-xl"
          style={{ border: `1px solid ${color}50` }}
          transition={{ type: 'spring', stiffness: 300, damping: 28 }}
        />
      )}
    </motion.button>
  )
}

// ─── Stat chip ────────────────────────────────────────────────────────────────

function StatChip({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div
      className="flex flex-col px-3 py-1.5 rounded-lg"
      style={{ background: `${color}10`, border: `1px solid ${color}25` }}
    >
      <span className="text-[8px] uppercase tracking-widest font-bold text-[var(--text-4)]">{label}</span>
      <span className="text-sm font-bold font-mono tabular-nums mt-0.5" style={{ color }}>{value}</span>
    </div>
  )
}

// ─── Side column layout with RAG chunks ──────────────────────────────────────

function TwoColumnLayout({ left, right }: { left: React.ReactNode; right: React.ReactNode }) {
  const [leftWidth, setLeftWidth] = useState(65)
  let dragging = false

  function startDrag(e: React.MouseEvent) {
    e.preventDefault()
    dragging = true
    const startX     = e.clientX
    const startWidth = leftWidth

    function onMove(ev: MouseEvent) {
      if (!dragging) return
      const container = (e.target as HTMLElement).closest('[data-resizable]') as HTMLElement
      if (!container) return
      const totalW = container.offsetWidth
      const delta  = ((ev.clientX - startX) / totalW) * 100
      setLeftWidth(Math.min(75, Math.max(35, startWidth + delta)))
    }
    function onUp() {
      dragging = false
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }

  return (
    <div className="flex gap-0 h-full min-h-0" data-resizable="true">
      <div style={{ width: `${leftWidth}%` }} className="min-h-0 overflow-hidden">
        {left}
      </div>
      <div
        className="w-1.5 cursor-col-resize hover:bg-[var(--border)] transition-colors mx-0.5 rounded-full shrink-0"
        onMouseDown={startDrag}
      />
      <div className="flex-1 min-h-0 overflow-hidden">
        {right}
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function ReasoningPage() {
  const state   = useReasoningData()
  const [activeTab, setActiveTab] = useState<ViewTab>('timeline')
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const { data } = state
  const activeTabCfg = TABS.find((t) => t.id === activeTab)!

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden">
      {/* ── Top bar ───────────────────────────────────────────────────────── */}
      <div
        className="flex items-center justify-between px-5 py-3 border-b border-[var(--border)] shrink-0"
        style={{ background: 'var(--elevated)' }}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center" style={{ background: '#6366f115', border: '1px solid #6366f130' }}>
              <Brain className="w-4 h-4 text-[#6366f1]" />
            </div>
            <div>
              <p className="text-sm font-bold text-[var(--text-1)]">AI Reasoning Visualization</p>
              <p className="text-[10px] text-[var(--text-4)] font-mono">{data.caseId}</p>
            </div>
          </div>
          <div className="h-5 w-px bg-[var(--border)]" />
          <div className="min-w-0">
            <p className="text-xs font-semibold text-[var(--text-2)] truncate">{data.patientName}</p>
            <p className="text-[10px] text-[var(--text-4)] truncate">{data.procedure}</p>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <div className="flex items-center gap-2">
            <StatChip label="Latency"  value={`${data.totalLatencyMs}ms`}    color="#f59e0b" />
            <StatChip label="Tokens"   value={data.totalTokens.toLocaleString()} color="#8b5cf6" />
            <StatChip label="Steps"    value={String(data.steps.length)}     color="#0ea5e9" />
          </div>
          <DecisionBadge decision={data.decision} confidence={data.overallConfidence} />
        </div>
      </div>

      {/* ── Tab bar ───────────────────────────────────────────────────────── */}
      <div
        className="flex items-center gap-1 px-4 py-2 border-b border-[var(--border)] shrink-0 overflow-x-auto"
        style={{ background: 'var(--surface)' }}
      >
        {TABS.map((tab) => (
          <TabBtn key={tab.id} tab={tab} isActive={activeTab === tab.id} onClick={() => setActiveTab(tab.id)} />
        ))}
        <div className="flex-1" />
        <span className="text-[10px] text-[var(--text-4)] hidden sm:block shrink-0 truncate max-w-xs">
          {activeTabCfg.description}
        </span>
        <button
          onClick={() => setSidebarOpen((v) => !v)}
          className="ml-2 p-1.5 rounded-lg text-[var(--text-4)] hover:text-[var(--text-1)] hover:bg-[var(--elevated)] transition-all shrink-0"
          title={sidebarOpen ? 'Hide chunks' : 'Show chunks'}
        >
          {sidebarOpen ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* ── Body ──────────────────────────────────────────────────────────── */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <AnimatePresence mode="wait">
          {sidebarOpen ? (
            <motion.div
              key="with-sidebar"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="h-full"
            >
              <TwoColumnLayout
                left={<MainView tab={activeTab} state={state} />}
                right={<div className="h-full p-2"><RAGChunksPanel chunks={data.chunks} /></div>}
              />
            </motion.div>
          ) : (
            <motion.div
              key="no-sidebar"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="h-full p-3"
            >
              <MainView tab={activeTab} state={state} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

// ─── Main view switcher ───────────────────────────────────────────────────────

function MainView({ tab, state }: { tab: ViewTab; state: ReturnType<typeof useReasoningData> }) {
  const { data } = state

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={tab}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={{ duration: 0.2 }}
        className="h-full p-3"
      >
        {tab === 'timeline' && (
          <ReasoningTimeline
            steps={data.steps}
            activeStepId={state.activeStepId}
            expandedStepIds={state.expandedStepIds}
            onActivate={state.setActiveStep}
            onToggle={state.toggleStep}
            totalLatencyMs={data.totalLatencyMs}
            totalTokens={data.totalTokens}
          />
        )}

        {tab === 'mapper' && (
          <EvidencePolicyMapper
            evidenceNodes={data.evidenceNodes}
            policyNodes={data.policyNodes}
            mappings={data.mappings}
            activeEvidenceId={state.activeEvidenceId}
            activePolicyId={state.activePolicyId}
            onEvidenceClick={state.setActiveEvidence}
            onPolicyClick={state.setActivePolicy}
          />
        )}

        {tab === 'heatmap' && (
          <ConfidenceHeatmap
            heatmap={data.heatmap}
            policyNodes={data.policyNodes}
          />
        )}

        {tab === 'chain' && (
          <AIChainPanel
            modelChain={data.modelChain}
            ragChain={data.ragChain}
            totalLatencyMs={data.totalLatencyMs}
            totalTokens={data.totalTokens}
          />
        )}

        {tab === 'tree' && (
          <RationaleTree
            policyNodes={data.policyNodes}
            evidenceNodes={data.evidenceNodes}
            mappings={data.mappings}
          />
        )}
      </motion.div>
    </AnimatePresence>
  )
}
