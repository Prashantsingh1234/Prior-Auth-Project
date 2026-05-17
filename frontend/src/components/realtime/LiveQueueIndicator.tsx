import { motion, AnimatePresence } from 'framer-motion'
import { Inbox, Clock, CheckCircle2, Cpu, AlertTriangle } from 'lucide-react'
import { useRealtimeStore } from '@/store/realtimeStore'

// ─── Queue stat chip ──────────────────────────────────────────────────────────

interface StatChipProps {
  icon:   React.ElementType
  value:  number
  label:  string
  color:  string
  pulse?: boolean
}

function StatChip({ icon: Icon, value, label, color, pulse }: StatChipProps) {
  return (
    <div className="flex flex-col items-center gap-0.5 px-3 py-2 rounded-lg"
         style={{ background: `${color}10`, border: `1px solid ${color}25` }}>
      <div className="flex items-center gap-1">
        {pulse && (
          <motion.div className="w-1.5 h-1.5 rounded-full" style={{ background: color }}
                      animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 1.2, repeat: Infinity }} />
        )}
        <Icon className="w-3 h-3" style={{ color }} />
        <AnimatePresence mode="wait">
          <motion.span
            key={value}
            initial={{ y: -8, opacity: 0 }}
            animate={{ y: 0,  opacity: 1 }}
            exit={{ y: 8,   opacity: 0 }}
            className="text-sm font-bold tabular-nums"
            style={{ color }}
          >
            {value}
          </motion.span>
        </AnimatePresence>
      </div>
      <span className="text-[8px] text-[var(--text-4)] uppercase tracking-wide">{label}</span>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface LiveQueueIndicatorProps {
  compact?: boolean
}

export function LiveQueueIndicator({ compact = false }: LiveQueueIndicatorProps) {
  const queue = useRealtimeStore((s) => s.queueSnapshot)

  // Mock fallback when no WS data yet
  const q = queue ?? { pending: 14, processing: 3, completed: 87, avgWaitMin: 4.2, slaAtRisk: 2 }

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1 px-2 py-1 rounded-lg"
             style={{ background: '#0ea5e915', border: '1px solid #0ea5e930' }}>
          <Inbox className="w-3 h-3 text-sky-400" />
          <AnimatePresence mode="wait">
            <motion.span key={q.pending} initial={{ y: -6, opacity: 0 }} animate={{ y: 0, opacity: 1 }}
                         exit={{ y: 6, opacity: 0 }} className="text-xs font-bold text-sky-400 tabular-nums">
              {q.pending}
            </motion.span>
          </AnimatePresence>
          <span className="text-[9px] text-[var(--text-4)]">pending</span>
        </div>
        {q.slaAtRisk > 0 && (
          <div className="flex items-center gap-1 px-2 py-1 rounded-lg"
               style={{ background: '#ef444415', border: '1px solid #ef444430' }}>
            <motion.div animate={{ scale: [1, 1.15, 1] }} transition={{ duration: 1, repeat: Infinity }}>
              <AlertTriangle className="w-3 h-3 text-red-400" />
            </motion.div>
            <span className="text-xs font-bold text-red-400">{q.slaAtRisk}</span>
            <span className="text-[9px] text-[var(--text-4)]">at risk</span>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="rounded-xl p-4" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Inbox className="w-4 h-4 text-[var(--text-3)]" />
          <span className="text-xs font-semibold text-[var(--text-2)]">Live Queue</span>
        </div>
        <div className="flex items-center gap-1.5">
          <motion.div className="w-1.5 h-1.5 rounded-full bg-emerald-400"
                      animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 1.5, repeat: Infinity }} />
          <span className="text-[9px] text-emerald-400 font-semibold">LIVE</span>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-2">
        <StatChip icon={Inbox}        value={q.pending}    label="Pending"    color="#0ea5e9" pulse />
        <StatChip icon={Cpu}          value={q.processing} label="Processing" color="#8b5cf6" pulse />
        <StatChip icon={CheckCircle2} value={q.completed}  label="Completed"  color="#10b981" />
        <StatChip icon={AlertTriangle} value={q.slaAtRisk} label="SLA Risk"   color="#ef4444" pulse={q.slaAtRisk > 0} />
      </div>

      <div className="mt-3 flex items-center gap-1.5 text-[9px] text-[var(--text-4)]">
        <Clock className="w-3 h-3" />
        <span>Avg wait:</span>
        <span className="font-mono text-[var(--text-3)]">{q.avgWaitMin.toFixed(1)} min</span>
      </div>
    </div>
  )
}
