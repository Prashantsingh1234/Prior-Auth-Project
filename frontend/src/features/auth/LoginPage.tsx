import { useState } from 'react'
import { motion } from 'framer-motion'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Stethoscope, Eye, EyeOff, Shield, Lock, AlertCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { cn } from '@/lib/utils'

const schema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(1, 'Password is required'),
})
type FormData = z.infer<typeof schema>

const DEMO_ACCOUNTS = [
  { label: 'Reviewer', email: 'reviewer@healthcare.internal', role: 'reviewer' as const },
  { label: 'Admin',    email: 'admin@healthcare.internal',    role: 'admin' as const },
]

export function LoginPage() {
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const setAuth = useAuthStore((s) => s.setAuth)
  const navigate = useNavigate()

  const { register, handleSubmit, setValue, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (data: FormData) => {
    setLoading(true)
    setError(null)
    try {
      await new Promise((r) => setTimeout(r, 800))
      const account = DEMO_ACCOUNTS.find((a) => a.email === data.email)
      if (!account && data.email !== 'provider@healthcare.internal') {
        throw new Error('Invalid credentials')
      }
      const role = account?.role ?? 'provider'
      setAuth('demo-token-' + role, {
        id: 'user-1',
        name: role === 'admin' ? 'Admin User' : role === 'reviewer' ? 'Dr. Sarah Chen' : 'Dr. James Miller',
        email: data.email,
        role,
      })
      navigate('/dashboard')
    } catch (e: any) {
      setError(e.message ?? 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] flex">
      {/* Left panel — branding */}
      <motion.div
        initial={{ opacity: 0, x: -40 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5 }}
        className="hidden lg:flex flex-col w-1/2 bg-gradient-to-br from-brand-900 via-brand-800 to-violet-900 p-12 relative overflow-hidden"
      >
        <div className="absolute inset-0 bg-grid-pattern opacity-5" />
        <div className="relative z-10 flex-1 flex flex-col">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/15 border border-white/20 flex items-center justify-center backdrop-blur-sm">
              <Stethoscope className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-white font-semibold text-lg leading-none">PA Review Platform</p>
              <p className="text-white/60 text-xs mt-0.5">AI-Assisted Prior Authorization</p>
            </div>
          </div>

          {/* Hero */}
          <div className="flex-1 flex flex-col justify-center">
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 0.5 }}
              className="text-4xl font-bold text-white leading-tight"
            >
              AI-Powered<br />Prior Authorization<br />Review
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.5 }}
              className="text-white/60 mt-4 text-lg leading-relaxed"
            >
              Reduce review time by 73%. Increase decision accuracy with
              evidence-based AI recommendations grounded in your payer policies.
            </motion.p>

            {/* Stats */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4, duration: 0.5 }}
              className="grid grid-cols-3 gap-4 mt-10"
            >
              {[
                { value: '94.2%', label: 'AI Accuracy' },
                { value: '3.5s',  label: 'Avg. Review Time' },
                { value: '73%',   label: 'Time Saved' },
              ].map(({ value, label }) => (
                <div key={label} className="bg-white/10 backdrop-blur-sm border border-white/10 rounded-xl p-4">
                  <p className="text-2xl font-bold text-white">{value}</p>
                  <p className="text-white/60 text-xs mt-1">{label}</p>
                </div>
              ))}
            </motion.div>
          </div>

          {/* HIPAA notice */}
          <div className="flex items-start gap-3 bg-white/5 border border-white/10 rounded-xl p-4">
            <Shield className="w-5 h-5 text-white/60 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-white/80 text-sm font-medium">HIPAA Compliant Platform</p>
              <p className="text-white/50 text-xs mt-0.5">
                All PHI is encrypted at rest and in transit. Access is logged and audited.
                This system processes Protected Health Information.
              </p>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Right panel — form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-sm"
        >
          {/* Mobile logo */}
          <div className="flex items-center gap-3 mb-8 lg:hidden">
            <div className="w-9 h-9 rounded-xl bg-brand-500/20 flex items-center justify-center">
              <Stethoscope className="w-4.5 h-4.5 text-brand-400" />
            </div>
            <p className="text-[var(--text-1)] font-semibold">PA Review Platform</p>
          </div>

          <h2 className="text-2xl font-bold text-[var(--text-1)]">Welcome back</h2>
          <p className="text-[var(--text-3)] mt-1 text-sm">Sign in to your clinical account</p>

          {/* Demo accounts */}
          <div className="mt-6 grid grid-cols-2 gap-2">
            {DEMO_ACCOUNTS.map((a) => (
              <button
                key={a.role}
                type="button"
                onClick={() => { setValue('email', a.email); setValue('password', 'demo') }}
                className="px-3 py-2 rounded-lg border border-[var(--border)] text-xs text-[var(--text-2)] hover:bg-[var(--elevated)] hover:text-[var(--text-1)] transition-colors text-left"
              >
                <p className="font-medium">{a.label} Demo</p>
                <p className="text-[var(--text-3)] truncate">{a.email}</p>
              </button>
            ))}
          </div>

          <div className="relative my-5">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-[var(--border)]" />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="px-2 bg-[var(--bg)] text-[var(--text-3)]">or sign in manually</span>
            </div>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm"
              >
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                {error}
              </motion.div>
            )}

            <div>
              <label className="section-label">Email address</label>
              <input
                {...register('email')}
                type="email"
                className={cn('input mt-1 w-full', errors.email && 'border-red-500/50')}
                placeholder="you@healthcare.org"
                autoComplete="email"
              />
              {errors.email && (
                <p className="text-xs text-red-400 mt-1">{errors.email.message}</p>
              )}
            </div>

            <div>
              <div className="flex items-center justify-between">
                <label className="section-label">Password</label>
                <button type="button" className="text-xs text-brand-400 hover:text-brand-300">
                  Forgot password?
                </button>
              </div>
              <div className="relative mt-1">
                <input
                  {...register('password')}
                  type={showPassword ? 'text' : 'password'}
                  className={cn('input w-full pr-10', errors.password && 'border-red-500/50')}
                  placeholder="••••••••"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-3)] hover:text-[var(--text-2)]"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {errors.password && (
                <p className="text-xs text-red-400 mt-1">{errors.password.message}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-60"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Authenticating…
                </>
              ) : (
                <>
                  <Lock className="w-4 h-4" />
                  Sign in securely
                </>
              )}
            </button>
          </form>

          <p className="text-center text-xs text-[var(--text-3)] mt-6">
            By signing in, you agree to our{' '}
            <span className="text-brand-400 cursor-pointer">Terms of Service</span> and
            acknowledge that this system contains Protected Health Information (PHI).
          </p>
        </motion.div>
      </div>
    </div>
  )
}