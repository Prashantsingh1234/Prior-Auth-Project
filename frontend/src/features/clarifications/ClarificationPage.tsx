import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  MessageSquare, AlertTriangle, CheckCircle2, Clock,
  LayoutPanelLeft, History, SlidersHorizontal,
} from 'lucide-react'
import { useClarificationManager } from './hooks/useClarificationManager'
import { ThreadList }           from './components/ThreadList'
import { ConversationThread }   from './components/ConversationThread'
import { MissingEvidenceTracker } from './components/MissingEvidenceTracker'
import { EscalationPanel }      from './components/EscalationPanel'
import { ClarificationTimeline } from './components/ClarificationTimeline'

// ─── Metric chip ──────────────────────────────────────────────────────────────

function MetricChip({
  icon: Icon, label, value, color,
}: { icon: React.ElementType; label: string; value: string | number; color: string }) {
  return (
    <div
      className="flex items-center gap-2 px-3 py-2 rounded-xl"
      style={{ background: `${color}10`, border: `1px solid ${color}25` }}
    >
      <Icon style={{ color, width: 13, height: 13 }} />
      <div>
        <p className="text-[8px] uppercase tracking-widest font-bold text-[var(--text-4)]">{label}</p>
        <p className="text-xs font-bold tabular-nums leading-tight" style={{ color }}>{value}</p>
      </div>
    </div>
  )
}

// ─── Right panel tab ─────────────────────────────────────────────────────────

type RightTab = 'evidence' | 'escalation' | 'timeline'

const RIGHT_TABS: Array<{ id: RightTab; label: string; icon: React.ElementType }> = [
  { id: 'evidence',   label: 'Evidence',   icon: CheckCircle2 },
  { id: 'escalation', label: 'Escalation', icon: AlertTriangle },
  { id: 'timeline',   label: 'History',    icon: History },
]

// ─── Panel resizer ────────────────────────────────────────────────────────────

function useDragWidth(initial: number, min: number, max: number) {
  const [width, setWidth] = useState(initial)

  function startDrag(e: React.MouseEvent, containerRef: React.RefObject<HTMLDivElement>) {
    e.preventDefault()
    const startX     = e.clientX
    const startWidth = width

    function onMove(ev: MouseEvent) {
      if (!containerRef.current) return
      const totalW = containerRef.current.offsetWidth
      const delta  = ((ev.clientX - startX) / totalW) * 100
      setWidth(Math.min(max, Math.max(min, startWidth + delta)))
    }
    function onUp() {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }

  return { width, startDrag }
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function ClarificationPage() {
  const mgr = useClarificationManager()
  const { caseData, activeThreadId } = mgr

  const [rightTab,   setRightTab]   = useState<RightTab>('evidence')
  const [listOpen,   setListOpen]   = useState(true)

  const containerRef = { current: null as HTMLDivElement | null }
  const leftDrag  = useDragWidth(22, 16, 32)
  const rightDrag = useDragWidth(28, 20, 38)

  const activeThread = caseData.threads.find((t) => t.id === activeThreadId) ?? caseData.threads[0]

  // Summary stats
  const openCount     = caseData.threads.filter((t) => t.status === 'pending' || t.status === 'overdue').length
  const resolvedCount = caseData.threads.filter((t) => t.status === 'resolved').length
  const overdueCount  = caseData.threads.filter((t) => t.status === 'overdue').length
  const evidencePct   = Math.round(
    (caseData.evidence.filter((e) => e.status === 'received' || e.status === 'waived').length /
      caseData.evidence.filter((e) => e.required).length) * 100
  )

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div
        className="px-5 py-3 border-b border-[var(--border)] shrink-0"
        style={{ background: 'var(--elevated)' }}
      >
        <div className="flex items-center justify-between flex-wrap gap-3">
          {/* Case info */}
          <div className="flex items-center gap-3 min-w-0">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: '#6366f115', border: '1px solid #6366f130' }}
            >
              <MessageSquare className="w-4 h-4 text-[#6366f1]" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-bold text-[var(--text-1)]">Clarification Management</p>
              <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                <span className="text-[10px] font-mono text-[var(--text-4)]">{caseData.caseId}</span>
                <span className="text-[var(--text-4)]">·</span>
                <span className="text-[10px] text-[var(--text-3)] truncate">{caseData.patientName}</span>
                <span className="text-[var(--text-4)]">·</span>
                <span className="text-[10px] text-[var(--text-4)] truncate">{caseData.procedure}</span>
              </div>
            </div>
          </div>

          {/* Metrics */}
          <div className="flex items-center gap-2 flex-wrap shrink-0">
            <MetricChip icon={MessageSquare} label="Open"     value={openCount}     color="#f59e0b" />
            <MetricChip icon={CheckCircle2}  label="Resolved" value={resolvedCount} color="#10b981" />
            <MetricChip icon={AlertTriangle} label="Overdue"  value={overdueCount}  color="#ef4444" />
            <MetricChip icon={Clock}         label="Evidence" value={`${evidencePct}%`} color="#0ea5e9" />

            {/* Escalation pulse */}
            {caseData.escalation.level === 'warning' && (
              <motion.div
                animate={{ boxShadow: ['0 0 0 0 rgba(245,158,11,0)', '0 0 8px 3px rgba(245,158,11,0.3)', '0 0 0 0 rgba(245,158,11,0)'] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl"
                style={{ background: '#f59e0b15', border: '1px solid #f59e0b40' }}
              >
                <AlertTriangle className="w-3 h-3 text-[#f59e0b]" />
                <span className="text-[10px] font-bold text-[#f59e0b]">Escalation Warning</span>
              </motion.div>
            )}
          </div>
        </div>

        {/* Provider / Reviewer info strip */}
        <div className="flex items-center gap-4 mt-2 pt-2 border-t border-[var(--border)]">
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] text-[var(--text-4)]">Provider:</span>
            <span className="text-[10px] font-semibold text-[var(--text-2)]">{caseData.providerName}</span>
            <span className="text-[9px] text-[var(--text-4)]">· {caseData.providerOrg}</span>
          </div>
          <div className="h-3 w-px bg-[var(--border)]" />
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] text-[var(--text-4)]">Reviewer:</span>
            <span className="text-[10px] font-semibold text-[var(--text-2)]">{caseData.reviewerName}</span>
          </div>
          <div className="h-3 w-px bg-[var(--border)]" />
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] text-[var(--text-4)]">Payer:</span>
            <span className="text-[10px] font-semibold text-[var(--text-2)]">{caseData.payer}</span>
          </div>
          <div className="flex-1" />
          {/* Layout toggle */}
          <button
            onClick={() => setListOpen((v) => !v)}
            className="flex items-center gap-1 text-[9px] text-[var(--text-4)] hover:text-[var(--text-2)] transition-colors"
          >
            <LayoutPanelLeft className="w-3 h-3" />
            {listOpen ? 'Hide' : 'Show'} thread list
          </button>
        </div>
      </div>

      {/* ── Body ────────────────────────────────────────────────────────────── */}
      <div
        ref={(el) => { containerRef.current = el }}
        className="flex-1 min-h-0 flex overflow-hidden"
      >
        {/* Thread list panel */}
        <AnimatePresence initial={false}>
          {listOpen && (
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: `${leftDrag.width}%`, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="shrink-0 overflow-hidden min-h-0"
              style={{ minWidth: 180, maxWidth: 320 }}
            >
              <ThreadList
                threads={caseData.threads}
                activeThreadId={activeThreadId}
                onSelectThread={mgr.setActiveThread}
                onAddThread={mgr.addThread}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Divider */}
        {listOpen && (
          <div
            className="w-1.5 cursor-col-resize hover:bg-[var(--border)] transition-colors shrink-0 rounded-full my-2"
            onMouseDown={(e) => leftDrag.startDrag(e, containerRef as React.RefObject<HTMLDivElement>)}
          />
        )}

        {/* Conversation panel */}
        <div className="flex-1 min-w-0 min-h-0 overflow-hidden">
          <AnimatePresence mode="wait">
            {activeThread ? (
              <motion.div
                key={activeThread.id}
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ duration: 0.2 }}
                className="h-full"
              >
                <ConversationThread
                  thread={activeThread}
                  composerText={mgr.composerText}
                  isProviderTyping={mgr.isProviderTyping}
                  isSending={mgr.isSending}
                  onSend={mgr.sendMessage}
                  onComposerChange={mgr.setComposerText}
                  onResolve={mgr.resolveThread}
                  onApplyChip={mgr.applyChip}
                />
              </motion.div>
            ) : (
              <div className="h-full flex items-center justify-center">
                <div className="text-center">
                  <MessageSquare className="w-8 h-8 text-[var(--text-4)] mx-auto mb-2" />
                  <p className="text-sm text-[var(--text-4)]">Select a thread to view</p>
                </div>
              </div>
            )}
          </AnimatePresence>
        </div>

        {/* Divider */}
        <div
          className="w-1.5 cursor-col-resize hover:bg-[var(--border)] transition-colors shrink-0 rounded-full my-2"
          onMouseDown={(e) => rightDrag.startDrag(e, containerRef as React.RefObject<HTMLDivElement>)}
        />

        {/* Right panel */}
        <div
          className="shrink-0 min-h-0 overflow-hidden flex flex-col"
          style={{ width: `${rightDrag.width}%`, minWidth: 240, maxWidth: 420, borderLeft: '1px solid var(--border)' }}
        >
          {/* Tab bar */}
          <div
            className="flex items-center gap-1 px-3 py-2 border-b border-[var(--border)] shrink-0"
            style={{ background: 'var(--elevated)' }}
          >
            {RIGHT_TABS.map((tab) => {
              const isActive = rightTab === tab.id
              const badge = tab.id === 'escalation' && caseData.escalation.level !== 'normal'
              return (
                <button
                  key={tab.id}
                  onClick={() => setRightTab(tab.id)}
                  className="relative flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] font-semibold transition-all flex-1 justify-center"
                  style={{
                    background: isActive ? 'var(--surface)' : 'transparent',
                    color:      isActive ? 'var(--text-1)' : 'var(--text-4)',
                    border:     `1px solid ${isActive ? 'var(--border)' : 'transparent'}`,
                  }}
                >
                  <tab.icon className="w-3 h-3" />
                  <span className="hidden sm:block">{tab.label}</span>
                  {badge && (
                    <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-[#f59e0b]" />
                  )}
                </button>
              )
            })}
            <button
              className="w-7 h-7 flex items-center justify-center rounded-lg text-[var(--text-4)] hover:text-[var(--text-1)] hover:bg-[var(--surface)] transition-all ml-1"
            >
              <SlidersHorizontal className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto p-3">
            <AnimatePresence mode="wait">
              <motion.div
                key={rightTab}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.15 }}
                className="space-y-3"
              >
                {rightTab === 'evidence' && (
                  <MissingEvidenceTracker
                    evidence={caseData.evidence}
                    onMark={mgr.markEvidenceReceived}
                  />
                )}
                {rightTab === 'escalation' && (
                  <EscalationPanel escalation={caseData.escalation} />
                )}
                {rightTab === 'timeline' && (
                  <ClarificationTimeline events={caseData.timeline} />
                )}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  )
}
