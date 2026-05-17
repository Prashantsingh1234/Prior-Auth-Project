import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, ShieldCheck, ScanLine, Tag, LayoutTemplate,
  Brain, Star, CheckCircle2, Loader2, Clock,
} from 'lucide-react'
import type { StageInfo, PipelineStage } from '../hooks/useDocumentIntelligence'

// ─── Icon map ─────────────────────────────────────────────────────────────────

const STAGE_ICONS: Record<PipelineStage | string, React.ElementType> = {
  upload:   Upload,
  validate: ShieldCheck,
  ocr:      ScanLine,
  classify: Tag,
  layout:   LayoutTemplate,
  extract:  Brain,
  quality:  Star,
  complete: CheckCircle2,
}

const STAGE_COLORS: Record<string, string> = {
  upload:   '#0ea5e9',
  validate: '#6366f1',
  ocr:      '#8b5cf6',
  classify: '#a855f7',
  layout:   '#06b6d4',
  extract:  '#8b5cf6',
  quality:  '#f59e0b',
  complete: '#10b981',
}

// ─── Spinner ──────────────────────────────────────────────────────────────────

function StageSpinner({ color }: { color: string }) {
  return (
    <motion.div
      animate={{ rotate: 360 }}
      transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
      style={{ color }}
    >
      <Loader2 className="w-4 h-4" />
    </motion.div>
  )
}

// ─── Single stage node ────────────────────────────────────────────────────────

function StageNode({ stage, isLast }: { stage: StageInfo; isLast: boolean }) {
  const Icon  = STAGE_ICONS[stage.id] ?? Clock
  const color = STAGE_COLORS[stage.id] ?? '#6b7280'
  const done  = stage.status === 'done'
  const running = stage.status === 'running'
  const waiting = stage.status === 'waiting'

  return (
    <div className="flex items-center gap-0">
      {/* Node */}
      <div className="flex flex-col items-center gap-1.5 relative">
        {/* Circle */}
        <motion.div
          animate={running ? {
            boxShadow: [`0 0 0 0 ${color}40`, `0 0 0 8px ${color}00`, `0 0 0 0 ${color}40`],
          } : {}}
          transition={{ duration: 1.5, repeat: Infinity }}
          className="w-10 h-10 rounded-xl flex items-center justify-center relative transition-all duration-300"
          style={{
            background: done ? `${color}20` : running ? `${color}15` : 'var(--elevated)',
            border:     `1.5px solid ${done ? color : running ? color : 'var(--border)'}`,
            opacity:    waiting ? 0.45 : 1,
          }}
        >
          {running ? (
            <StageSpinner color={color} />
          ) : done ? (
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 300, damping: 18 }}
            >
              <Icon style={{ color, width: 16, height: 16 }} />
            </motion.div>
          ) : (
            <Icon style={{ color: waiting ? '#6b7280' : color, width: 16, height: 16 }} />
          )}

          {/* Done checkmark overlay */}
          {done && (
            <motion.div
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full flex items-center justify-center"
              style={{ background: color }}
            >
              <CheckCircle2 className="w-2.5 h-2.5 text-white" />
            </motion.div>
          )}
        </motion.div>

        {/* Label */}
        <div className="text-center">
          <p
            className="text-[10px] font-semibold whitespace-nowrap"
            style={{ color: done ? color : running ? color : 'var(--text-4)' }}
          >
            {stage.label}
          </p>
          {running && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-[8px] text-[var(--text-4)] whitespace-nowrap mt-0.5"
            >
              {stage.sublabel}
            </motion.p>
          )}
          {done && stage.elapsedMs && (
            <p className="text-[8px] font-mono tabular-nums mt-0.5" style={{ color: `${color}80` }}>
              {(stage.elapsedMs / 1000).toFixed(1)}s
            </p>
          )}
        </div>
      </div>

      {/* Connector line */}
      {!isLast && (
        <div className="flex-1 h-px mx-1 relative overflow-hidden" style={{ minWidth: 16, maxWidth: 40 }}>
          <div className="absolute inset-0 bg-[var(--border)]" />
          {done && (
            <motion.div
              className="absolute inset-0"
              initial={{ scaleX: 0, originX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ duration: 0.4, ease: 'easeOut' }}
              style={{ background: color }}
            />
          )}
          {running && (
            <motion.div
              className="absolute inset-0 h-full"
              animate={{ x: ['-100%', '200%'] }}
              transition={{ duration: 1, repeat: Infinity, ease: 'easeInOut' }}
              style={{ background: `linear-gradient(90deg, transparent, ${color}, transparent)`, width: '50%' }}
            />
          )}
        </div>
      )}
    </div>
  )
}

// ─── Progress summary strip ───────────────────────────────────────────────────

function ProgressStrip({ stages, elapsedMs }: { stages: StageInfo[]; elapsedMs: number }) {
  const done  = stages.filter((s) => s.status === 'done').length
  const total = stages.length
  const pct   = Math.round((done / total) * 100)

  return (
    <div className="flex items-center gap-4 mt-4 pt-3 border-t border-[var(--border)]">
      <div className="flex-1">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[10px] text-[var(--text-4)]">{done}/{total} stages complete</span>
          <span className="text-[10px] font-mono text-[var(--text-3)] tabular-nums">
            {(elapsedMs / 1000).toFixed(1)}s elapsed
          </span>
        </div>
        <div className="h-1 rounded-full bg-[var(--border)] overflow-hidden">
          <motion.div
            className="h-full rounded-full"
            style={{ background: 'linear-gradient(90deg, #0ea5e9, #8b5cf6, #10b981)' }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 0.4, ease: 'easeOut' }}
          />
        </div>
      </div>
      <span className="text-sm font-bold tabular-nums text-[var(--text-1)]">{pct}%</span>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  stages:       StageInfo[]
  currentStage: PipelineStage
  isComplete:   boolean
  elapsedMs:    number
  fileName:     string
  fileSize:     string
}

export function PipelineProgress({ stages, currentStage, isComplete, elapsedMs, fileName, fileSize }: Props) {
  const visibleStages = stages.filter((s) => s.id !== 'idle')

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl overflow-hidden"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-3 border-b border-[var(--border)]"
        style={{ background: 'var(--elevated)' }}
      >
        <div className="flex items-center gap-2.5">
          <motion.div
            animate={!isComplete ? {
              boxShadow: ['0 0 0 0 rgba(139,92,246,0)', '0 0 8px 3px rgba(139,92,246,0.4)', '0 0 0 0 rgba(139,92,246,0)'],
            } : {}}
            transition={{ duration: 2, repeat: Infinity }}
            className="w-2 h-2 rounded-full"
            style={{ background: isComplete ? '#10b981' : '#8b5cf6' }}
          />
          <span className="text-sm font-semibold text-[var(--text-1)]">
            {isComplete ? 'Extraction Complete' : 'AI Ingestion Pipeline'}
          </span>
          {!isComplete && (
            <span className="text-[10px] text-[var(--text-4)]">Processing…</span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-[10px] text-[var(--text-4)] truncate max-w-32">{fileName}</p>
            <p className="text-[9px] font-mono text-[var(--text-4)]">{fileSize}</p>
          </div>
          {isComplete && (
            <motion.span
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 240, damping: 16 }}
              className="text-[10px] font-bold px-2 py-0.5 rounded-full"
              style={{ background: 'rgba(16,185,129,0.15)', color: '#10b981' }}
            >
              ✓ Done
            </motion.span>
          )}
        </div>
      </div>

      {/* Stage nodes */}
      <div className="px-5 pt-5 pb-4">
        <div className="flex items-start justify-between">
          {visibleStages.map((stage, i) => (
            <StageNode
              key={stage.id}
              stage={stage}
              isLast={i === visibleStages.length - 1}
            />
          ))}
        </div>

        {/* Progress strip */}
        <ProgressStrip stages={visibleStages} elapsedMs={elapsedMs} />
      </div>

      {/* Live detail ticker */}
      <AnimatePresence mode="wait">
        {currentStage !== 'idle' && currentStage !== 'complete' && (
          <motion.div
            key={currentStage}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="px-5 py-2 border-t border-[var(--border)] flex items-center gap-2"
            style={{ background: `${STAGE_COLORS[currentStage] ?? '#6b7280'}08` }}
          >
            <motion.div
              className="w-1.5 h-1.5 rounded-full"
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ duration: 0.8, repeat: Infinity }}
              style={{ background: STAGE_COLORS[currentStage] ?? '#6b7280' }}
            />
            <span className="text-[10px] font-mono text-[var(--text-3)]">
              {stages.find((s) => s.id === currentStage)?.sublabel ?? '…'}
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
