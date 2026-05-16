import { useEffect, useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft, Brain, CheckCircle2, XCircle, AlertTriangle,
  ArrowUpRight, Clock, Maximize2, User,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useUIStore } from '@/store/uiStore'
import { useCaseReviewData } from './hooks/useCaseReviewData'
import { DocumentPanel }      from './panels/DocumentPanel'
import { AIReasoningPanel }   from './panels/AIReasoningPanel'
import { ReviewerActionsPanel } from './panels/ReviewerActionsPanel'

// ─── Status config ────────────────────────────────────────────────────────────

const AI_REC_CFG = {
  APPROVE:      { color: '#10b981', bg: 'rgba(16,185,129,0.12)', label: 'Approve',      icon: CheckCircle2 },
  DENY:         { color: '#ef4444', bg: 'rgba(239,68,68,0.12)',  label: 'Deny',         icon: XCircle },
  REQUEST_INFO: { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)',label: 'Request Info', icon: AlertTriangle },
  ESCALATE:     { color: '#8b5cf6', bg: 'rgba(139,92,246,0.12)',label: 'Escalate',     icon: ArrowUpRight },
}

const PRIORITY_CFG = {
  ROUTINE:  { color: '#6b7280', label: 'Routine'  },
  URGENT:   { color: '#f59e0b', label: 'Urgent'   },
  EMERGENT: { color: '#ef4444', label: 'Emergent' },
}

// ─── Resizable divider ────────────────────────────────────────────────────────

function Divider({ onDrag, vertical = true }: {
  onDrag: (delta: number) => void; vertical?: boolean
}) {
  const dragging = useRef(false)
  const last     = useRef(0)

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    dragging.current = true
    last.current = vertical ? e.clientX : e.clientY
    e.preventDefault()

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return
      const curr = vertical ? ev.clientX : ev.clientY
      onDrag(curr - last.current)
      last.current = curr
    }
    const onUp = () => { dragging.current = false; document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp) }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }, [onDrag, vertical])

  return (
    <div
      onMouseDown={onMouseDown}
      className={cn(
        'flex-shrink-0 group transition-colors z-10',
        vertical ? 'w-1 cursor-col-resize hover:w-1' : 'h-1 cursor-row-resize',
      )}
      style={{ background: 'var(--border)' }}
    >
      <div
        className="opacity-0 group-hover:opacity-100 transition-opacity"
        style={{
          width:      vertical ? '100%' : '100%',
          height:     vertical ? '100%' : '100%',
          background: 'rgba(14,165,233,0.5)',
        }}
      />
    </div>
  )
}

// ─── Panel label ──────────────────────────────────────────────────────────────

function PanelLabel({ icon: Icon, label, color }: { icon: React.ElementType; label: string; color: string }) {
  return (
    <div
      className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider border-b border-[var(--border)]"
      style={{ background: 'var(--surface)', color }}
    >
      <Icon style={{ width: 12, height: 12 }} />
      {label}
    </div>
  )
}

// ─── Top bar ──────────────────────────────────────────────────────────────────

function TopBar({ state, onMaximize }: { state: ReturnType<typeof useCaseReviewData>; onMaximize: () => void }) {
  const navigate = useNavigate()
  const { caseData } = state
  const aiCfg  = AI_REC_CFG[caseData.ai.recommendation]
  const priCfg = PRIORITY_CFG[caseData.priority]

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center gap-3 px-5 py-3 border-b border-[var(--border)] flex-shrink-0"
      style={{ background: 'var(--surface)' }}
    >
      {/* Back */}
      <button
        onClick={() => navigate(-1)}
        className="p-1.5 rounded-lg text-[var(--text-4)] hover:bg-[var(--elevated)] hover:text-[var(--text-1)] transition-colors flex-shrink-0"
      >
        <ArrowLeft className="w-4 h-4" />
      </button>

      {/* Case ID + priority */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <span className="text-xs font-mono font-bold text-cyan-400">{caseData.caseNumber}</span>
        <span
          className="text-[9px] font-bold px-1.5 py-0.5 rounded-full uppercase tracking-wide"
          style={{ background: `${priCfg.color}15`, color: priCfg.color }}
        >
          {priCfg.label}
        </span>
        <span
          className="text-[9px] font-bold px-1.5 py-0.5 rounded-full uppercase tracking-wide"
          style={{ background: 'rgba(14,165,233,0.12)', color: '#38bdf8' }}
        >
          {caseData.status.replace('_', ' ')}
        </span>
      </div>

      <div className="w-px h-5 bg-[var(--border)] flex-shrink-0" />

      {/* Patient + procedure */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <User className="w-3.5 h-3.5 text-[var(--text-4)] flex-shrink-0" />
          <span className="text-sm font-semibold text-[var(--text-1)] truncate">{caseData.patient.name}</span>
          <span className="text-xs text-[var(--text-4)]">·</span>
          <span className="text-xs text-[var(--text-3)] truncate">{caseData.procedure.description}</span>
          <span className="text-[10px] font-mono text-[var(--text-4)]">({caseData.procedure.cptCode})</span>
        </div>
        <div className="flex items-center gap-3 mt-0.5">
          <span className="text-[10px] text-[var(--text-4)]">{caseData.provider.name}</span>
          <span className="text-[10px] text-[var(--text-4)]">· {caseData.patient.plan}</span>
        </div>
      </div>

      {/* AI decision summary */}
      <div
        className="flex items-center gap-3 px-3 py-2 rounded-xl flex-shrink-0"
        style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
      >
        <div
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg"
          style={{ background: aiCfg.bg }}
        >
          <aiCfg.icon style={{ color: aiCfg.color, width: 14, height: 14 }} />
          <span className="text-xs font-bold" style={{ color: aiCfg.color }}>{aiCfg.label}</span>
        </div>
        <div className="text-right">
          <p className="text-[9px] text-[var(--text-4)]">AI Score</p>
          <p className="text-sm font-bold tabular-nums text-violet-400">
            {Math.round(caseData.ai.confidence * 100)}%
          </p>
        </div>
        <div className="text-right">
          <p className="text-[9px] text-[var(--text-4)]">Criteria</p>
          <p className="text-sm font-bold tabular-nums text-emerald-400">
            {caseData.ai.metCriteria}/{caseData.ai.totalCriteria}
          </p>
        </div>
      </div>

      {/* Fullscreen toggle */}
      <button
        onClick={onMaximize}
        className="p-1.5 rounded-lg text-[var(--text-4)] hover:bg-[var(--elevated)] hover:text-[var(--text-2)] transition-colors flex-shrink-0"
        title="Maximize panel"
      >
        <Maximize2 className="w-3.5 h-3.5" />
      </button>
    </motion.div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

type MaximizedPanel = 'doc' | 'ai' | 'reviewer' | null

export function CaseReviewPage() {
  const state   = useCaseReviewData()
  const addTab  = useUIStore((s) => s.addTab)

  const [maximized,  setMaximized]  = useState<MaximizedPanel>(null)
  const [leftWidth,  setLeftWidth]  = useState(38)   // percent
  const [rightWidth, setRightWidth] = useState(26)   // percent
  // center = 100 - left - right

  // Register workspace tab
  useEffect(() => {
    addTab({
      title:     `${state.caseData.caseNumber}`,
      path:      `/review/${state.caseData.id}`,
      type:      'review',
      closeable: true,
      status:    'UNDER_REVIEW',
    })
  }, [addTab, state.caseData.caseNumber, state.caseData.id])

  const handleLeftDrag = useCallback((delta: number) => {
    setLeftWidth((prev) => Math.max(25, Math.min(50, prev + delta / window.innerWidth * 100)))
  }, [])

  const handleRightDrag = useCallback((delta: number) => {
    setRightWidth((prev) => Math.max(20, Math.min(40, prev - delta / window.innerWidth * 100)))
  }, [])

  const centerWidth = 100 - leftWidth - rightWidth

  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ background: 'var(--bg)' }}>

      {/* Top bar */}
      <TopBar state={state} onMaximize={() => setMaximized(null)} />

      {/* Three-panel layout */}
      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* ── LEFT: Document Viewer ──────────────────────────────────── */}
        <AnimatePresence>
          {maximized !== 'ai' && maximized !== 'reviewer' && (
            <motion.div
              key="doc-panel"
              initial={false}
              animate={{ width: maximized === 'doc' ? '100%' : `${leftWidth}%` }}
              transition={{ duration: 0.25, ease: 'easeInOut' }}
              className="flex flex-col min-w-0 overflow-hidden border-r border-[var(--border)]"
            >
              <PanelLabel icon={Brain} label="Document Viewer" color="#0ea5e9" />
              <div className="flex-1 min-h-0 overflow-hidden">
                <DocumentPanel state={state} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Drag handle left */}
        {!maximized && (
          <Divider onDrag={handleLeftDrag} />
        )}

        {/* ── CENTER: AI Reasoning ───────────────────────────────────── */}
        <AnimatePresence>
          {maximized !== 'doc' && maximized !== 'reviewer' && (
            <motion.div
              key="ai-panel"
              initial={false}
              animate={{ width: maximized === 'ai' ? '100%' : `${centerWidth}%` }}
              transition={{ duration: 0.25, ease: 'easeInOut' }}
              className="flex flex-col min-w-0 overflow-hidden border-r border-[var(--border)]"
            >
              <PanelLabel icon={Brain} label="AI Reasoning Engine" color="#8b5cf6" />
              <div className="flex-1 min-h-0 overflow-hidden">
                <AIReasoningPanel state={state} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Drag handle right */}
        {!maximized && (
          <Divider onDrag={handleRightDrag} />
        )}

        {/* ── RIGHT: Reviewer Actions ────────────────────────────────── */}
        <AnimatePresence>
          {maximized !== 'doc' && maximized !== 'ai' && (
            <motion.div
              key="reviewer-panel"
              initial={false}
              animate={{ width: maximized === 'reviewer' ? '100%' : `${rightWidth}%` }}
              transition={{ duration: 0.25, ease: 'easeInOut' }}
              className="flex flex-col min-w-0 overflow-hidden"
            >
              <PanelLabel icon={Clock} label="Reviewer Actions" color="#f59e0b" />
              <div className="flex-1 min-h-0 overflow-hidden">
                <ReviewerActionsPanel state={state} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
