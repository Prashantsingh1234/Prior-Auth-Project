import { useEffect, useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft, Brain, CheckCircle2, XCircle, AlertTriangle,
  ArrowUpRight, Clock, FileText, User,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useUIStore } from '@/store/uiStore'
import { useBreakpoint } from '@/hooks/useBreakpoint'
import { useCaseReviewData } from './hooks/useCaseReviewData'
import { DocumentPanel }      from './panels/DocumentPanel'
import { AIReasoningPanel }   from './panels/AIReasoningPanel'
import { ReviewerActionsPanel } from './panels/ReviewerActionsPanel'

// ─── Status config ────────────────────────────────────────────────────────────

const AI_REC_CFG = {
  APPROVE:      { color: '#10b981', bg: 'rgba(16,185,129,0.12)', label: 'Approve',      icon: CheckCircle2 },
  DENY:         { color: '#ef4444', bg: 'rgba(239,68,68,0.12)',  label: 'Deny',         icon: XCircle },
  REQUEST_INFO: { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', label: 'Request Info', icon: AlertTriangle },
  ESCALATE:     { color: '#8b5cf6', bg: 'rgba(139,92,246,0.12)', label: 'Escalate',     icon: ArrowUpRight },
}

const PRIORITY_CFG = {
  ROUTINE:  { color: '#6b7280', label: 'Routine'  },
  URGENT:   { color: '#f59e0b', label: 'Urgent'   },
  EMERGENT: { color: '#ef4444', label: 'Emergent' },
}

// ─── Resizable divider (desktop only) ────────────────────────────────────────

function Divider({ onDrag }: { onDrag: (delta: number) => void }) {
  const dragging = useRef(false)
  const last     = useRef(0)

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    dragging.current = true
    last.current = e.clientX
    e.preventDefault()
    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return
      onDrag(ev.clientX - last.current)
      last.current = ev.clientX
    }
    const onUp = () => {
      dragging.current = false
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }, [onDrag])

  return (
    <div
      onMouseDown={onMouseDown}
      className="w-1 flex-shrink-0 cursor-col-resize group z-10 transition-colors"
      style={{ background: 'var(--border)' }}
    >
      <div className="w-full h-full opacity-0 group-hover:opacity-100 transition-opacity"
           style={{ background: 'rgba(14,165,233,0.5)' }} />
    </div>
  )
}

// ─── Panel label ──────────────────────────────────────────────────────────────

function PanelLabel({ icon: Icon, label, color }: { icon: React.ElementType; label: string; color: string }) {
  return (
    <div
      className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider border-b border-[var(--border)] flex-shrink-0"
      style={{ background: 'var(--surface)', color }}
    >
      <Icon style={{ width: 12, height: 12 }} />
      {label}
    </div>
  )
}

// ─── Mobile tab bar ───────────────────────────────────────────────────────────

type PanelId = 'doc' | 'ai' | 'reviewer'

const PANEL_TABS: { id: PanelId; label: string; shortLabel: string; icon: React.ElementType; color: string }[] = [
  { id: 'doc',      label: 'Document',   shortLabel: 'Doc',     icon: FileText,  color: '#0ea5e9' },
  { id: 'ai',       label: 'AI Reasoning', shortLabel: 'AI',    icon: Brain,     color: '#8b5cf6' },
  { id: 'reviewer', label: 'Actions',    shortLabel: 'Actions', icon: Clock,     color: '#f59e0b' },
]

function MobilePanelTabs({ active, onChange }: { active: PanelId; onChange: (p: PanelId) => void }) {
  return (
    <div
      className="flex flex-shrink-0 border-b border-[var(--border)]"
      style={{ background: 'var(--surface)' }}
    >
      {PANEL_TABS.map((tab) => {
        const Icon    = tab.icon
        const isActive = active === tab.id
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={cn(
              'flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors relative',
              isActive ? 'text-[var(--text-1)]' : 'text-[var(--text-4)]',
            )}
          >
            {isActive && (
              <motion.div
                layoutId="panel-tab-indicator"
                className="absolute bottom-0 left-0 right-0 h-0.5 rounded-t-full"
                style={{ background: tab.color }}
              />
            )}
            <Icon style={{ width: 13, height: 13, color: isActive ? tab.color : undefined }} />
            <span className="hidden xs:inline sm:hidden md:inline">{tab.label}</span>
            <span className="xs:hidden sm:inline md:hidden">{tab.shortLabel}</span>
          </button>
        )
      })}
    </div>
  )
}

// ─── Case info bar (compact for mobile) ──────────────────────────────────────

function CaseInfoBar({ state }: { state: ReturnType<typeof useCaseReviewData> }) {
  const navigate = useNavigate()
  const { caseData } = state
  const aiCfg  = AI_REC_CFG[caseData.ai.recommendation]
  const priCfg = PRIORITY_CFG[caseData.priority]

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center gap-2 sm:gap-3 px-3 sm:px-5 py-2.5 sm:py-3 border-b border-[var(--border)] flex-shrink-0 min-w-0"
      style={{ background: 'var(--surface)' }}
    >
      {/* Back */}
      <button
        onClick={() => navigate(-1)}
        className="p-1.5 rounded-lg text-[var(--text-4)] hover:bg-[var(--elevated)] hover:text-[var(--text-1)] transition-colors flex-shrink-0"
      >
        <ArrowLeft className="w-4 h-4" />
      </button>

      {/* Case ID + badges */}
      <div className="flex items-center gap-1.5 flex-shrink-0">
        <span className="text-xs font-mono font-bold text-cyan-400">{caseData.caseNumber}</span>
        <span
          className="text-[9px] font-bold px-1.5 py-0.5 rounded-full uppercase tracking-wide hidden sm:inline"
          style={{ background: `${priCfg.color}15`, color: priCfg.color }}
        >
          {priCfg.label}
        </span>
      </div>

      <div className="hidden sm:block w-px h-5 bg-[var(--border)] flex-shrink-0" />

      {/* Patient info — truncated on mobile */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <User className="w-3.5 h-3.5 text-[var(--text-4)] flex-shrink-0 hidden sm:block" />
          <span className="text-sm font-semibold text-[var(--text-1)] truncate">{caseData.patient.name}</span>
          <span className="text-xs text-[var(--text-3)] truncate hidden md:inline">· {caseData.procedure.description}</span>
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-[10px] text-[var(--text-4)] truncate hidden sm:inline">{caseData.provider.name}</span>
        </div>
      </div>

      {/* AI decision summary — compact on mobile */}
      <div
        className="flex items-center gap-1.5 sm:gap-3 px-2 sm:px-3 py-1.5 sm:py-2 rounded-xl flex-shrink-0"
        style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
      >
        <div
          className="flex items-center gap-1 sm:gap-1.5 px-1.5 sm:px-2.5 py-1 rounded-lg"
          style={{ background: aiCfg.bg }}
        >
          <aiCfg.icon style={{ color: aiCfg.color, width: 12, height: 12 }} />
          <span className="text-[10px] sm:text-xs font-bold" style={{ color: aiCfg.color }}>{aiCfg.label}</span>
        </div>
        <div className="text-right hidden sm:block">
          <p className="text-[9px] text-[var(--text-4)]">AI Score</p>
          <p className="text-sm font-bold tabular-nums text-violet-400">
            {Math.round(caseData.ai.confidence * 100)}%
          </p>
        </div>
        <div className="text-right hidden md:block">
          <p className="text-[9px] text-[var(--text-4)]">Criteria</p>
          <p className="text-sm font-bold tabular-nums text-emerald-400">
            {caseData.ai.metCriteria}/{caseData.ai.totalCriteria}
          </p>
        </div>
      </div>
    </motion.div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function CaseReviewPage() {
  const state   = useCaseReviewData()
  const addTab  = useUIStore((s) => s.addTab)
  const isLg    = useBreakpoint('lg')

  // Desktop-only resize state
  const [leftWidth,  setLeftWidth]  = useState(38)
  const [rightWidth, setRightWidth] = useState(26)

  // Mobile/tablet tab state
  const [activePanel, setActivePanel] = useState<PanelId>('doc')

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

      {/* Top case info bar */}
      <CaseInfoBar state={state} />

      {/* ── MOBILE / TABLET: Tab-based single panel ─────────────────────── */}
      {!isLg && (
        <>
          <MobilePanelTabs active={activePanel} onChange={setActivePanel} />
          <div className="flex-1 min-h-0 overflow-hidden">
            <AnimatePresence mode="wait" initial={false}>
              {activePanel === 'doc' && (
                <motion.div
                  key="doc"
                  initial={{ opacity: 0, x: -16 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 16 }}
                  transition={{ duration: 0.18 }}
                  className="h-full"
                >
                  <DocumentPanel state={state} />
                </motion.div>
              )}
              {activePanel === 'ai' && (
                <motion.div
                  key="ai"
                  initial={{ opacity: 0, x: -16 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 16 }}
                  transition={{ duration: 0.18 }}
                  className="h-full overflow-y-auto"
                >
                  <AIReasoningPanel state={state} />
                </motion.div>
              )}
              {activePanel === 'reviewer' && (
                <motion.div
                  key="reviewer"
                  initial={{ opacity: 0, x: -16 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 16 }}
                  transition={{ duration: 0.18 }}
                  className="h-full overflow-y-auto"
                >
                  <ReviewerActionsPanel state={state} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </>
      )}

      {/* ── DESKTOP: Three-panel layout with drag handles ───────────────── */}
      {isLg && (
        <div className="flex flex-1 min-h-0 overflow-hidden">

          {/* LEFT: Document Viewer */}
          <motion.div
            animate={{ width: `${leftWidth}%` }}
            transition={{ duration: 0 }}
            className="flex flex-col min-w-0 overflow-hidden border-r border-[var(--border)]"
          >
            <PanelLabel icon={Brain} label="Document Viewer" color="#0ea5e9" />
            <div className="flex-1 min-h-0 overflow-hidden">
              <DocumentPanel state={state} />
            </div>
          </motion.div>

          <Divider onDrag={handleLeftDrag} />

          {/* CENTER: AI Reasoning */}
          <motion.div
            animate={{ width: `${centerWidth}%` }}
            transition={{ duration: 0 }}
            className="flex flex-col min-w-0 overflow-hidden border-r border-[var(--border)]"
          >
            <PanelLabel icon={Brain} label="AI Reasoning Engine" color="#8b5cf6" />
            <div className="flex-1 min-h-0 overflow-hidden">
              <AIReasoningPanel state={state} />
            </div>
          </motion.div>

          <Divider onDrag={handleRightDrag} />

          {/* RIGHT: Reviewer Actions */}
          <motion.div
            animate={{ width: `${rightWidth}%` }}
            transition={{ duration: 0 }}
            className="flex flex-col min-w-0 overflow-hidden"
          >
            <PanelLabel icon={Clock} label="Reviewer Actions" color="#f59e0b" />
            <div className="flex-1 min-h-0 overflow-hidden">
              <ReviewerActionsPanel state={state} />
            </div>
          </motion.div>
        </div>
      )}
    </div>
  )
}
