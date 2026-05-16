import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link } from 'react-router-dom'
import { Mail, ArrowLeft, CheckCircle, AlertCircle, Send } from 'lucide-react'
import { AuthLayout } from '../components/AuthLayout'
import { useForgotPassword } from '../hooks/useForgotPassword'
import { cn } from '@/lib/utils'
import { ROUTES } from '@/config/routes.config'

const schema = z.object({
  email: z.string().email('Enter a valid email address'),
})
type FormData = z.infer<typeof schema>

export function ForgotPasswordPage() {
  const [sent, setSent] = useState(false)
  const [maskedEmail, setMaskedEmail] = useState('')
  const { mutate: forgotPassword, isPending, error } = useForgotPassword()

  const { register, handleSubmit, watch, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  })
  const email = watch('email')

  const onSubmit = (data: FormData) => {
    forgotPassword(data, {
      onSuccess: (res) => {
        setMaskedEmail(res.maskedEmail)
        setSent(true)
      },
    })
  }

  return (
    <AuthLayout>
      <AnimatePresence mode="wait">
        {sent ? (
          /* ── Success state ─────────────────────────────────────────────── */
          <motion.div
            key="success"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex flex-col items-center text-center"
          >
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 300, damping: 20, delay: 0.1 }}
              className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5"
              style={{ background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.25)' }}
            >
              <CheckCircle className="w-8 h-8 text-emerald-400" />
            </motion.div>

            <h2 className="text-xl font-bold text-[var(--text-1)]">Check your email</h2>
            <p className="text-sm text-[var(--text-3)] mt-2 leading-relaxed">
              We've sent a password reset link to{' '}
              <span className="text-[var(--text-1)] font-medium">{maskedEmail}</span>
            </p>

            <div
              className="mt-6 w-full px-4 py-3 rounded-xl text-sm text-[var(--text-2)] text-left"
              style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
            >
              <p className="font-medium text-[var(--text-1)] mb-1">Next steps</p>
              <ul className="space-y-1 text-[var(--text-3)]">
                <li className="flex items-center gap-2">
                  <span className="w-4 h-4 rounded-full bg-cyan-500/20 text-cyan-400 text-[10px] flex items-center justify-center font-bold flex-shrink-0">1</span>
                  Open the email from PA Review Platform
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-4 h-4 rounded-full bg-cyan-500/20 text-cyan-400 text-[10px] flex items-center justify-center font-bold flex-shrink-0">2</span>
                  Click the secure reset link (expires in 15 min)
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-4 h-4 rounded-full bg-cyan-500/20 text-cyan-400 text-[10px] flex items-center justify-center font-bold flex-shrink-0">3</span>
                  Set a new strong password
                </li>
              </ul>
            </div>

            <p className="text-xs text-[var(--text-4)] mt-4">
              Didn't receive it?{' '}
              <button
                onClick={() => setSent(false)}
                className="text-cyan-400 hover:text-cyan-300 transition-colors"
              >
                Try again
              </button>
            </p>

            <Link
              to={ROUTES.LOGIN}
              className="mt-6 flex items-center gap-2 text-sm text-[var(--text-3)] hover:text-[var(--text-1)] transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to sign in
            </Link>
          </motion.div>
        ) : (
          /* ── Form state ────────────────────────────────────────────────── */
          <motion.div key="form" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
            <Link
              to={ROUTES.LOGIN}
              className="inline-flex items-center gap-1.5 text-sm text-[var(--text-3)] hover:text-[var(--text-1)] transition-colors mb-6"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to sign in
            </Link>

            <div className="mb-6">
              <div
                className="w-12 h-12 rounded-xl flex items-center justify-center mb-4"
                style={{ background: 'rgba(14,165,233,0.15)', border: '1px solid rgba(14,165,233,0.25)' }}
              >
                <Mail className="w-6 h-6 text-cyan-400" />
              </div>
              <h1 className="text-2xl font-bold text-[var(--text-1)]">Reset your password</h1>
              <p className="text-sm text-[var(--text-3)] mt-1">
                Enter your registered email and we'll send a secure reset link.
              </p>
            </div>

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm overflow-hidden"
                  >
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    {(error as any)?.message ?? 'Something went wrong. Please try again.'}
                  </motion.div>
                )}
              </AnimatePresence>

              <div>
                <label className="section-label mb-1 block">Email address</label>
                <input
                  {...register('email')}
                  type="email"
                  autoComplete="email"
                  autoFocus
                  placeholder="clinician@hospital.org"
                  className={cn('input w-full', errors.email && 'border-red-500/50')}
                />
                {errors.email && (
                  <p className="text-xs text-red-400 mt-1">{errors.email.message}</p>
                )}
              </div>

              <motion.button
                type="submit"
                disabled={isPending || !email}
                whileHover={!isPending ? { scale: 1.01 } : {}}
                whileTap={{ scale: 0.98 }}
                className={cn(
                  'w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-bold text-white',
                  'bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500',
                  'shadow-[0_0_20px_rgba(14,165,233,0.2)] transition-all',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                )}
              >
                {isPending ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
                {isPending ? 'Sending…' : 'Send reset link'}
              </motion.button>
            </form>

            <p className="text-center text-xs text-[var(--text-4)] mt-6">
              Contact{' '}
              <span className="text-cyan-400">it-support@healthcare.internal</span>{' '}
              if you no longer have access to your registered email.
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </AuthLayout>
  )
}
