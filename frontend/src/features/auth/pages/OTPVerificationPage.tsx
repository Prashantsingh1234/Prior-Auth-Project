import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useSearchParams, Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Mail, RefreshCw, AlertCircle, ShieldCheck } from 'lucide-react'
import { AuthLayout } from '../components/AuthLayout'
import { OTPInput } from '../components/OTPInput'
import { useVerifyOTP } from '../hooks/useVerifyOTP'
import { useAuthStore } from '@/store'
import { ROUTES } from '@/config/routes.config'
import { cn } from '@/lib/utils'

const RESEND_COOLDOWN = 60

export function OTPVerificationPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const purpose = (params.get('purpose') as 'password_reset' | 'mfa' | 'email_verification') ?? 'password_reset'
  const email = useAuthStore((s) => s.pendingEmail) ?? params.get('email') ?? ''

  const [code, setCode] = useState('')
  const [apiError, setApiError] = useState<string | null>(null)
  const [resendCooldown, setResendCooldown] = useState(0)
  const [resent, setResent] = useState(false)

  const { mutate: verifyOTP, isPending } = useVerifyOTP()

  // Cooldown countdown
  useEffect(() => {
    if (resendCooldown <= 0) return
    const t = setInterval(() => setResendCooldown((c) => c - 1), 1000)
    return () => clearInterval(t)
  }, [resendCooldown])

  function handleComplete(value: string) {
    setApiError(null)
    verifyOTP(
      { email, code: value, purpose },
      {
        onSuccess: (res) => {
          if (purpose === 'password_reset' && res.resetToken) {
            navigate(`${ROUTES.RESET_PASSWORD}?token=${res.resetToken}`)
          } else {
            navigate(ROUTES.LOGIN)
          }
        },
        onError: (e: any) => setApiError(e?.message ?? 'Invalid or expired code. Please try again.'),
      }
    )
  }

  function handleResend() {
    setResent(true)
    setResendCooldown(RESEND_COOLDOWN)
    setCode('')
    setApiError(null)
    setTimeout(() => setResent(false), 3000)
  }

  const maskedEmail = email
    ? email.replace(/^(.)(.*)(@.*)$/, (_, a, b, c) => a + '*'.repeat(b.length) + c)
    : '••••@••••'

  return (
    <AuthLayout>
      <Link
        to={purpose === 'password_reset' ? ROUTES.FORGOT_PASSWORD : ROUTES.LOGIN}
        className="inline-flex items-center gap-1.5 text-sm text-[var(--text-3)] hover:text-[var(--text-1)] transition-colors mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        Back
      </Link>

      {/* Header */}
      <div className="mb-6">
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 300, damping: 20 }}
          className="w-12 h-12 rounded-xl flex items-center justify-center mb-4"
          style={{ background: 'rgba(14,165,233,0.15)', border: '1px solid rgba(14,165,233,0.25)' }}
        >
          <Mail className="w-6 h-6 text-cyan-400" />
        </motion.div>
        <h1 className="text-2xl font-bold text-[var(--text-1)]">Enter verification code</h1>
        <p className="text-sm text-[var(--text-3)] mt-1">
          We sent a 6-digit code to{' '}
          <span className="text-[var(--text-2)] font-medium">{maskedEmail}</span>
        </p>
      </div>

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

      {/* Resent confirmation */}
      <AnimatePresence>
        {resent && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm mb-4 overflow-hidden"
          >
            <ShieldCheck className="w-4 h-4 flex-shrink-0" />
            New code sent to your email
          </motion.div>
        )}
      </AnimatePresence>

      {/* OTP input */}
      <OTPInput
        value={code}
        onChange={setCode}
        onComplete={handleComplete}
        disabled={isPending}
        error={!!apiError}
        className="mb-5"
      />

      {/* Loading state */}
      <AnimatePresence>
        {isPending && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex items-center justify-center gap-2 text-sm text-cyan-400 mb-4"
          >
            <div className="w-4 h-4 border-2 border-cyan-400/30 border-t-cyan-400 rounded-full animate-spin" />
            Verifying code…
          </motion.div>
        )}
      </AnimatePresence>

      {/* Verify button */}
      <motion.button
        onClick={() => code.length === 6 && handleComplete(code)}
        disabled={code.length < 6 || isPending}
        whileHover={code.length === 6 ? { scale: 1.01 } : {}}
        whileTap={code.length === 6 ? { scale: 0.98 } : {}}
        className={cn(
          'w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-bold text-white',
          'bg-gradient-to-r from-cyan-600 to-blue-600',
          'shadow-[0_0_20px_rgba(14,165,233,0.2)] transition-all',
          'disabled:opacity-40 disabled:cursor-not-allowed',
        )}
      >
        <ShieldCheck className="w-4 h-4" />
        Verify code
      </motion.button>

      {/* Resend */}
      <div className="mt-5 text-center">
        <p className="text-sm text-[var(--text-3)]">
          Didn't receive it?{' '}
          {resendCooldown > 0 ? (
            <span className="text-[var(--text-4)]">Resend in {resendCooldown}s</span>
          ) : (
            <button
              onClick={handleResend}
              className="inline-flex items-center gap-1 text-cyan-400 hover:text-cyan-300 transition-colors font-medium"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Resend code
            </button>
          )}
        </p>
      </div>

      <p className="text-center text-xs text-[var(--text-4)] mt-5">
        Code expires in 15 minutes. This is part of your organization's multi-factor authentication policy.
      </p>
    </AuthLayout>
  )
}
