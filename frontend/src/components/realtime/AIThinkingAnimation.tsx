import { motion, AnimatePresence } from 'framer-motion'
import { Brain, Sparkles, Zap, CheckCircle2 } from 'lucide-react'
import type { AIStreamState } from '@/store/realtimeStore'

// ─── Thinking dots ────────────────────────────────────────────────────────────

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1">
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-violet-400"
          animate={{ scale: [1, 1.5, 1], opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.2 }}
        />
      ))}
    </div>
  )
}

// ─── Stage icon ───────────────────────────────────────────────────────────────

const STAGE_CFG = {
  retrieval: { icon: Sparkles, color: '#0ea5e9', label: 'Retrieving' },
  reasoning: { icon: Brain,    color: '#8b5cf6', label: 'Reasoning'  },
  decision:  { icon: Zap,      color: '#f59e0b', label: 'Deciding'   },
  complete:  { icon: CheckCircle2, color: '#10b981', label: 'Complete' },
  idle:      { icon: Brain,    color: '#6b7280', label: 'Idle'       },
}

// ─── Step list ────────────────────────────────────────────────────────────────

function StepList({ steps, currentLabel }: { steps: AIStreamState['steps']; currentLabel: string }) {
  return (
    <div className="space-y-1 mt-2">
      <AnimatePresence>
        {steps.map((step, i) => (
          <motion.div
            key={step.label}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.04 }}
            className="flex items-center gap-2"
          >
            <CheckCircle2 className="w-3 h-3 text-emerald-400 flex-shrink-0" />
            <span className="text-[10px] text-[var(--text-3)]">{step.label}</span>
          </motion.div>
        ))}
      </AnimatePresence>
      {currentLabel && (
        <div className="flex items-center gap-2">
          <ThinkingDots />
          <span className="text-[10px] text-violet-400 font-medium">{currentLabel}</span>
        </div>
      )}
    </div>
  )
}

// ─── Streaming text ───────────────────────────────────────────────────────────

function StreamingText({ text }: { text: string }) {
  if (!text) return null
  return (
    <div className="mt-3 rounded-lg p-3 text-[11px] leading-relaxed text-[var(--text-2)] font-mono"
         style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
      {text}
      <motion.span
        className="inline-block w-0.5 h-3 ml-0.5 bg-violet-400 align-text-bottom"
        animate={{ opacity: [1, 0] }}
        transition={{ duration: 0.6, repeat: Infinity }}
      />
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface AIThinkingAnimationProps {
  stream:   AIStreamState
  compact?: boolean
}

export function AIThinkingAnimation({ stream, compact = false }: AIThinkingAnimationProps) {
  const stageCfg = STAGE_CFG[stream.stage]
  const StageIcon = stageCfg.icon
  const isActive = stream.stage !== 'idle' && stream.stage !== 'complete'

  if (compact) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg"
           style={{ background: `${stageCfg.color}10`, border: `1px solid ${stageCfg.color}30` }}>
        <motion.div
          animate={isActive ? { rotate: 360 } : {}}
          transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
        >
          <StageIcon className="w-3.5 h-3.5" style={{ color: stageCfg.color }} />
        </motion.div>
        <span className="text-[10px] font-medium" style={{ color: stageCfg.color }}>
          {stream.stepLabel || stageCfg.label}
        </span>
        {isActive && <ThinkingDots />}
      </div>
    )
  }

  return (
    <div className="rounded-xl p-4" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <motion.div
            className="w-7 h-7 rounded-full flex items-center justify-center"
            style={{ background: `${stageCfg.color}20` }}
            animate={isActive ? { scale: [1, 1.08, 1] } : {}}
            transition={{ duration: 1.5, repeat: Infinity }}
          >
            <motion.div
              animate={isActive ? { rotate: 360 } : {}}
              transition={{ duration: 2.5, repeat: Infinity, ease: 'linear' }}
            >
              <StageIcon className="w-3.5 h-3.5" style={{ color: stageCfg.color }} />
            </motion.div>
          </motion.div>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wide" style={{ color: stageCfg.color }}>
              AI {stageCfg.label}
            </p>
            <p className="text-[9px] text-[var(--text-4)]">Case {stream.caseId}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {stream.tokensUsed > 0 && (
            <span className="text-[8px] px-2 py-0.5 rounded-full font-mono"
                  style={{ background: '#8b5cf620', color: '#8b5cf6' }}>
              {stream.tokensUsed.toLocaleString()} tokens
            </span>
          )}
          {isActive && (
            <span className="text-[8px] px-2 py-0.5 rounded-full"
                  style={{ background: `${stageCfg.color}15`, color: stageCfg.color }}>
              LIVE
            </span>
          )}
        </div>
      </div>

      {/* Steps */}
      <StepList steps={stream.steps} currentLabel={isActive ? (stream.stepLabel ?? '') : ''} />

      {/* Streaming output */}
      {stream.tokens && <StreamingText text={stream.tokens} />}

      {/* Complete indicator */}
      {stream.stage === 'complete' && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-3 flex items-center gap-2 text-emerald-400"
        >
          <CheckCircle2 className="w-3.5 h-3.5" />
          <span className="text-[10px] font-semibold">Analysis complete</span>
          {stream.completedAt && (
            <span className="text-[9px] text-[var(--text-4)] ml-auto">
              {new Date(stream.completedAt).toLocaleTimeString()}
            </span>
          )}
        </motion.div>
      )}
    </div>
  )
}
