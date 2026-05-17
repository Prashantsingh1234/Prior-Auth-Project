import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, Info, Zap, X, ShieldAlert } from 'lucide-react'
import { useRealtimeStore } from '@/store/realtimeStore'
import type { SystemAlert } from '@/store/realtimeStore'

// ─── Level config ─────────────────────────────────────────────────────────────

const LEVEL_CFG = {
  info:     { icon: Info,         color: '#0ea5e9', bg: '#0ea5e915', border: '#0ea5e930' },
  warning:  { icon: AlertTriangle, color: '#f59e0b', bg: '#f59e0b15', border: '#f59e0b30' },
  critical: { icon: ShieldAlert,  color: '#ef4444', bg: '#ef444415', border: '#ef444430' },
}

// ─── Single alert ─────────────────────────────────────────────────────────────

function AlertItem({ alert }: { alert: SystemAlert }) {
  const { dismissAlert } = useRealtimeStore()
  const cfg  = LEVEL_CFG[alert.level]
  const Icon = cfg.icon

  return (
    <motion.div
      layout
      initial={{ y: -20, opacity: 0, scale: 0.97 }}
      animate={{ y: 0,   opacity: 1, scale: 1 }}
      exit={{ y: -20, opacity: 0, scale: 0.97 }}
      transition={{ type: 'spring', stiffness: 400, damping: 35 }}
      className="flex items-start gap-3 px-4 py-3 rounded-xl"
      style={{ background: cfg.bg, border: `1px solid ${cfg.border}` }}
    >
      <motion.div
        animate={alert.level === 'critical' ? { scale: [1, 1.2, 1] } : {}}
        transition={{ duration: 1, repeat: Infinity }}
        className="flex-shrink-0 mt-0.5"
      >
        <Icon className="w-4 h-4" style={{ color: cfg.color }} />
      </motion.div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-[10px] font-bold uppercase tracking-wide" style={{ color: cfg.color }}>
            {alert.level}
          </span>
          <span className="text-[10px] text-[var(--text-3)] font-medium">{alert.service}</span>
          {alert.code && (
            <span className="text-[8px] px-1.5 py-0.5 rounded font-mono"
                  style={{ background: `${cfg.color}20`, color: cfg.color }}>{alert.code}</span>
          )}
        </div>
        <p className="text-[11px] text-[var(--text-2)]">{alert.message}</p>
        <p className="text-[8px] text-[var(--text-4)] mt-0.5">
          {new Date(alert.timestamp).toLocaleTimeString()}
        </p>
      </div>

      <button
        onClick={() => dismissAlert(alert.id)}
        className="flex-shrink-0 p-1 rounded-lg text-[var(--text-4)] hover:text-[var(--text-2)] hover:bg-white/10 transition-colors"
      >
        <X className="w-3 h-3" />
      </button>
    </motion.div>
  )
}

// ─── Alert stack ──────────────────────────────────────────────────────────────

export function SystemAlertBanner() {
  const alerts = useRealtimeStore((s) => s.systemAlerts.filter((a) => !a.dismissed))

  if (alerts.length === 0) return null

  return (
    <div className="fixed top-16 right-4 z-50 w-80 space-y-2 pointer-events-none">
      <AnimatePresence>
        {alerts.slice(0, 4).map((alert) => (
          <div key={alert.id} className="pointer-events-auto">
            <AlertItem alert={alert} />
          </div>
        ))}
      </AnimatePresence>
    </div>
  )
}

// ─── Inline alert strip ───────────────────────────────────────────────────────

interface AlertStripProps {
  level:   SystemAlert['level']
  message: string
  service?: string
}

export function AlertStrip({ level, message, service }: AlertStripProps) {
  const cfg = LEVEL_CFG[level]

  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg text-[11px]"
         style={{ background: cfg.bg, border: `1px solid ${cfg.border}`, color: cfg.color }}>
      <Zap className="w-3.5 h-3.5 flex-shrink-0" />
      {service && <span className="font-semibold">{service}:</span>}
      <span>{message}</span>
    </div>
  )
}
