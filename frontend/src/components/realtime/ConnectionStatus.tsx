import { motion, AnimatePresence } from 'framer-motion'
import { Wifi, WifiOff, RefreshCw, AlertTriangle } from 'lucide-react'
import { useRealtimeStore } from '@/store/realtimeStore'
import type { WSConnectionState } from '@/services/realtime.service'

// ─── Status config ────────────────────────────────────────────────────────────

const STATE_CFG: Record<WSConnectionState, {
  icon:   React.ElementType
  color:  string
  label:  string
  pulse?: boolean
  spin?:  boolean
}> = {
  idle:         { icon: WifiOff,      color: '#6b7280', label: 'Not connected'  },
  connecting:   { icon: RefreshCw,    color: '#f59e0b', label: 'Connecting…',   spin: true },
  connected:    { icon: Wifi,         color: '#10b981', label: 'Live',          pulse: true },
  reconnecting: { icon: RefreshCw,    color: '#f97316', label: 'Reconnecting…', spin: true },
  closed:       { icon: WifiOff,      color: '#6b7280', label: 'Disconnected'  },
  error:        { icon: AlertTriangle, color: '#ef4444', label: 'Connection error' },
}

// ─── Compact chip ─────────────────────────────────────────────────────────────

export function ConnectionStatusChip() {
  const state = useRealtimeStore((s) => s.connectionState)
  const cfg   = STATE_CFG[state]
  const Icon  = cfg.icon

  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-full"
         style={{ background: `${cfg.color}15`, border: `1px solid ${cfg.color}30` }}>
      {cfg.pulse && (
        <motion.div
          className="w-1.5 h-1.5 rounded-full"
          style={{ background: cfg.color }}
          animate={{ opacity: [1, 0.3, 1], scale: [1, 0.8, 1] }}
          transition={{ duration: 1.5, repeat: Infinity }}
        />
      )}
      <motion.div
        animate={cfg.spin ? { rotate: 360 } : {}}
        transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
      >
        <Icon className="w-3 h-3" style={{ color: cfg.color }} />
      </motion.div>
      <span className="text-[9px] font-semibold uppercase tracking-wide" style={{ color: cfg.color }}>
        {cfg.label}
      </span>
    </div>
  )
}

// ─── Toast-style reconnect banner ────────────────────────────────────────────

export function ReconnectBanner() {
  const state = useRealtimeStore((s) => s.connectionState)
  const show  = state === 'reconnecting' || state === 'error' || state === 'closed'

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ y: -40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -40, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 400, damping: 35 }}
          className="fixed top-14 left-1/2 z-50 -translate-x-1/2 flex items-center gap-2 px-4 py-2 rounded-xl shadow-lg"
          style={{
            background: state === 'error' ? '#ef444420' : '#f9731620',
            border:     `1px solid ${state === 'error' ? '#ef4444' : '#f97316'}40`,
          }}
        >
          <motion.div animate={{ rotate: state === 'reconnecting' ? 360 : 0 }}
                      transition={{ duration: 1, repeat: state === 'reconnecting' ? Infinity : 0, ease: 'linear' }}>
            <RefreshCw className="w-3.5 h-3.5" style={{ color: state === 'error' ? '#ef4444' : '#f97316' }} />
          </motion.div>
          <span className="text-xs font-medium" style={{ color: state === 'error' ? '#ef4444' : '#f97316' }}>
            {state === 'reconnecting' ? 'Reconnecting to live updates…' : 'Live updates disconnected'}
          </span>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
