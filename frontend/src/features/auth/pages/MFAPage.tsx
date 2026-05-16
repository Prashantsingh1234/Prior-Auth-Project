import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck, Smartphone, MessageSquare, Key, AlertCircle, RefreshCw, ChevronDown } from 'lucide-react'
import { AuthLayout } from '../components/AuthLayout'
import { OTPInput } from '../components/OTPInput'
import { useMFA } from '../hooks/useMFA'
import { useAuthStore } from '@/store'
import { cn } from '@/lib/utils'
import type { MFAMethod } from '@/types'

const METHOD_CONFIG: Record<MFAMethod, { label: string; description: string; icon: React.ElementType }> = {
  totp:        { label: 'Authenticator App', description: 'Open your authenticator app',         icon: Smartphone    },
  sms:         { label: 'SMS Code',          description: 'Sent to your registered phone',        icon: MessageSquare },
  email:       { label: 'Email Code',        description: 'Sent to your registered email',        icon: ShieldCheck   },
  backup_code: { label: 'Backup Code',       description: 'Use a one-time backup recovery code',  icon: Key           },
}

export function MFAPage() {
  const navigate    = useNavigate()
  const challenge   = useAuthStore((s) => s.mfaChallenge)
  const [code, setCode]         = useState('')
  const [apiError, setApiError] = useState<string | null>(null)
  const [method, setMethod]     = useState<MFAMethod>(challenge?.method ?? 'totp')
  const [showMethods, setShowMethods] = useState(false)
  const { mutate: verifyMFA, isPending, mutate: resendMFA } = useMFA()

  if (!challenge) {
    navigate('/', { replace: true })
    return null
  }

  const cfg = METHOD_CONFIG[method]
  const isBackup = method === 'backup_code'

  function handleComplete(value: string) {
    if (!challenge) return
    setApiError(null)
    verifyMFA(
      { challengeId: challenge.challengeId, code: value, method },
      { onError: (e: any) => setApiError(e?.message ?? 'Invalid code. Please try again.') }
    )
  }

  function handleResend() {
    if (!challenge) return
    setCode('')
    setApiError(null)
    resendMFA(
      { challengeId: challenge.challengeId, code: '', method },
      { onError: (e: any) => setApiError(e?.message ?? 'Failed to resend code') }
    )
  }

  const altMethods: MFAMethod[] = (['totp', 'sms', 'email', 'backup_code'] as MFAMethod[]).filter((m) => m !== method)

  return (
    <AuthLayout>
      {/* Header */}
      <div className="mb-6">
        <motion.div
          initial={{ scale: 0.85, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 280, damping: 22 }}
          className="w-12 h-12 rounded-xl flex items-center justify-center mb-4"
          style={{
            background: 'rgba(139,92,246,0.15)',
            border: '1px solid rgba(139,92,246,0.25)',
          }}
        >
          <ShieldCheck className="w-6 h-6 text-violet-400" />
        </motion.div>
        <h1 className="text-2xl font-bold text-[var(--text-1)]">Two-factor verification</h1>
        <p className="text-sm text-[var(--text-3)] mt-1">
          Your organization requires an additional verification step.
        </p>
      </div>

      {/* Current method badge */}
      <div
        className="flex items-center justify-between px-3 py-2.5 rounded-xl mb-4 cursor-pointer"
        style={{ background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.2)' }}
        onClick={() => setShowMethods((v) => !v)}
      >
        <div className="flex items-center gap-2.5">
          <cfg.icon className="w-4 h-4 text-violet-400" />
          <div>
            <p className="text-sm font-medium text-[var(--text-1)]">{cfg.label}</p>
            <p className="text-xs text-[var(--text-3)]">{cfg.description}</p>
          </div>
        </div>
        <ChevronDown className={cn('w-4 h-4 text-[var(--text-3)] transition-transform', showMethods && 'rotate-180')} />
      </div>

      {/* Alt method picker */}
      <AnimatePresence>
        {showMethods && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-4 overflow-hidden rounded-xl border border-[var(--border)]"
          >
            {altMethods.map((m) => {
              const c = METHOD_CONFIG[m]
              return (
                <button
                  key={m}
                  onClick={() => { setMethod(m); setShowMethods(false); setCode(''); setApiError(null) }}
                  className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-[var(--elevated)] transition-colors text-left border-b border-[var(--border)] last:border-0"
                >
                  <c.icon className="w-4 h-4 text-[var(--text-3)] flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-[var(--text-2)]">{c.label}</p>
                    <p className="text-xs text-[var(--text-4)]">{c.description}</p>
                  </div>
                </button>
              )
            })}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error */}
      <AnimatePresence>
        {apiError && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm mb-4 overflow-hidden"
          >
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {apiError}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Code input */}
      {isBackup ? (
        <div className="mb-5">
          <label className="section-label mb-1 block">Backup recovery code</label>
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="XXXX-XXXX-XXXX"
            className="input w-full font-mono tracking-widest text-center text-lg"
            autoFocus
          />
          <p className="text-xs text-[var(--text-4)] mt-1.5">
            Each backup code can only be used once.
          </p>
        </div>
      ) : (
        <OTPInput
          value={code}
          onChange={setCode}
          onComplete={handleComplete}
          disabled={isPending}
          error={!!apiError}
          className="mb-5"
        />
      )}

      {/* Verify */}
      <motion.button
        onClick={() => (isBackup ? handleComplete(code) : code.length === 6 && handleComplete(code))}
        disabled={(!isBackup && code.length < 6) || (isBackup && code.length < 8) || isPending}
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.98 }}
        className={cn(
          'w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-bold text-white',
          'bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500',
          'shadow-[0_0_20px_rgba(139,92,246,0.25)] transition-all',
          'disabled:opacity-40 disabled:cursor-not-allowed',
        )}
      >
        {isPending ? (
          <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
        ) : (
          <ShieldCheck className="w-4 h-4" />
        )}
        {isPending ? 'Verifying…' : 'Verify & Sign In'}
      </motion.button>

      {/* Resend / help */}
      {method !== 'totp' && method !== 'backup_code' && (
        <div className="mt-4 text-center">
          <button
            onClick={handleResend}
            className="inline-flex items-center gap-1.5 text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Resend code
          </button>
        </div>
      )}

      {/* Expiry notice */}
      {challenge.expiresAt && (
        <p className="text-center text-xs text-[var(--text-4)] mt-4">
          Code expires at {new Date(challenge.expiresAt).toLocaleTimeString()}
        </p>
      )}

      <p className="text-center text-xs text-[var(--text-4)] mt-3">
        This step protects access to Protected Health Information. Contact IT support if you need assistance.
      </p>
    </AuthLayout>
  )
}
