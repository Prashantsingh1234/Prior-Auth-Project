import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Lock, LogOut, RefreshCw, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SessionTimeoutModalProps {
  open: boolean
  millisRemaining: number
  onContinue: () => void
  onSignOut: () => void
  isContinuing?: boolean
}

function formatCountdown(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export function SessionTimeoutModal({
  open,
  millisRemaining,
  onContinue,
  onSignOut,
  isContinuing = false,
}: SessionTimeoutModalProps) {
  const WARNING_MS = 5 * 60 * 1000 // 5 minutes
  const fraction = Math.max(0, Math.min(1, millisRemaining / WARNING_MS))
  const isUrgent = millisRemaining < 60_000

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-[90] bg-black/60 backdrop-blur-sm"
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.92, y: 10 }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            className="fixed inset-0 z-[91] flex items-center justify-center p-4 pointer-events-none"
          >
            <div
              className="pointer-events-auto w-full max-w-sm rounded-2xl p-6 shadow-card-xl"
              style={{
                background: 'var(--surface)',
                border: '1px solid var(--border)',
              }}
            >
              {/* Icon */}
              <div className="flex justify-center mb-4">
                <motion.div
                  className={cn(
                    'w-14 h-14 rounded-2xl flex items-center justify-center',
                    isUrgent
                      ? 'bg-red-500/15 border border-red-500/25'
                      : 'bg-amber-500/15 border border-amber-500/25'
                  )}
                  animate={isUrgent ? {
                    boxShadow: [
                      '0 0 0 0 rgba(239,68,68,0)',
                      '0 0 0 8px rgba(239,68,68,0.15)',
                      '0 0 0 0 rgba(239,68,68,0)',
                    ],
                  } : {}}
                  transition={{ duration: 1.2, repeat: Infinity }}
                >
                  <Lock className={cn('w-7 h-7', isUrgent ? 'text-red-400' : 'text-amber-400')} />
                </motion.div>
              </div>

              {/* Heading */}
              <h2 className="text-center text-lg font-bold text-[var(--text-1)]">
                Session Expiring Soon
              </h2>
              <p className="text-center text-sm text-[var(--text-3)] mt-1">
                Your session will expire due to inactivity
              </p>

              {/* Countdown */}
              <div className="mt-5 flex flex-col items-center gap-2">
                <div className="flex items-center gap-2">
                  <Clock className={cn('w-4 h-4', isUrgent ? 'text-red-400' : 'text-amber-400')} />
                  <motion.span
                    key={Math.floor(millisRemaining / 1000)}
                    initial={{ scale: 1.1 }}
                    animate={{ scale: 1 }}
                    className={cn(
                      'text-3xl font-bold tabular-nums tracking-tight',
                      isUrgent ? 'text-red-400' : 'text-[var(--text-1)]'
                    )}
                  >
                    {formatCountdown(millisRemaining)}
                  </motion.span>
                </div>
                <span className="text-xs text-[var(--text-4)]">remaining</span>

                {/* Progress bar */}
                <div className="w-full h-1.5 rounded-full bg-[var(--elevated)] mt-1 overflow-hidden">
                  <motion.div
                    className={cn(
                      'h-full rounded-full transition-colors',
                      isUrgent ? 'bg-red-500' : fraction < 0.3 ? 'bg-amber-500' : 'bg-cyan-500'
                    )}
                    animate={{ width: `${fraction * 100}%` }}
                    transition={{ duration: 0.5 }}
                  />
                </div>
              </div>

              {/* Actions */}
              <div className="mt-6 flex gap-3">
                <button
                  onClick={onSignOut}
                  disabled={isContinuing}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium border border-[var(--border)] text-[var(--text-2)] hover:bg-[var(--elevated)] hover:text-[var(--text-1)] transition-colors disabled:opacity-50"
                >
                  <LogOut className="w-4 h-4" />
                  Sign Out
                </button>
                <button
                  onClick={onContinue}
                  disabled={isContinuing}
                  className={cn(
                    'flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold text-white transition-all',
                    isUrgent
                      ? 'bg-red-500 hover:bg-red-600 shadow-[0_0_16px_rgba(239,68,68,0.4)]'
                      : 'bg-cyan-600 hover:bg-cyan-500 shadow-[0_0_16px_rgba(14,165,233,0.3)]',
                    isContinuing && 'opacity-70'
                  )}
                >
                  {isContinuing ? (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <RefreshCw className="w-4 h-4" />
                  )}
                  {isContinuing ? 'Refreshing…' : 'Continue Session'}
                </button>
              </div>

              <p className="text-center text-xs text-[var(--text-4)] mt-4">
                Activity on this system is monitored and logged per HIPAA requirements.
              </p>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
