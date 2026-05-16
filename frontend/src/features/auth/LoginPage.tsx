import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link } from 'react-router-dom'
import { Eye, EyeOff, Lock, AlertCircle, ChevronRight, Stethoscope } from 'lucide-react'
import { AuthLayout } from './components/AuthLayout'
import { useLogin } from './hooks/useLogin'
import { cn } from '@/lib/utils'
import { ROUTES } from '@/config/routes.config'

const schema = z.object({
  email:      z.string().email('Enter a valid email address'),
  password:   z.string().min(1, 'Password is required'),
  rememberMe: z.boolean().optional(),
})
type FormData = z.infer<typeof schema>

const DEMO_ACCOUNTS = [
  {
    role:     'Admin',
    email:    'admin@healthcare.internal',
    name:     'Alex Carter',
    color:    'from-purple-500/20 to-violet-500/20',
    border:   'border-purple-500/20',
    textColor:'text-purple-400',
  },
  {
    role:     'Reviewer',
    email:    'reviewer@healthcare.internal',
    name:     'Dr. Sarah Chen',
    color:    'from-cyan-500/20 to-blue-500/20',
    border:   'border-cyan-500/20',
    textColor:'text-cyan-400',
  },
  {
    role:     'Provider',
    email:    'provider@healthcare.internal',
    name:     'Dr. James Miller',
    color:    'from-emerald-500/20 to-teal-500/20',
    border:   'border-emerald-500/20',
    textColor:'text-emerald-400',
  },
]

export function LoginPage() {
  const [showPw, setShowPw]       = useState(false)
  const [apiError, setApiError]   = useState<string | null>(null)
  const { mutate: login, isPending } = useLogin()

  const { register, handleSubmit, setValue, watch, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { rememberMe: false },
  })
  const email = watch('email')

  const onSubmit = (data: FormData) => {
    setApiError(null)
    login(
      { email: data.email, password: data.password, rememberMe: data.rememberMe },
      { onError: (e: any) => setApiError(e?.message ?? 'Invalid email or password') }
    )
  }

  return (
    <AuthLayout>
      {/* Mobile logo */}
      <div className="flex items-center gap-3 mb-8 lg:hidden">
        <div className="w-9 h-9 rounded-xl bg-cyan-500/15 border border-cyan-500/20 flex items-center justify-center">
          <Stethoscope className="w-4.5 h-4.5 text-cyan-400" />
        </div>
        <p className="text-[var(--text-1)] font-semibold">PA Review Platform</p>
      </div>

      {/* Heading */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[var(--text-1)]">Welcome back</h1>
        <p className="text-[var(--text-3)] text-sm mt-1">Sign in to your clinical account</p>
      </div>

      {/* Demo quick-access */}
      <div className="grid grid-cols-3 gap-2 mb-6">
        {DEMO_ACCOUNTS.map((a) => (
          <motion.button
            key={a.role}
            type="button"
            whileHover={{ scale: 1.02, y: -1 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => { setValue('email', a.email); setValue('password', 'demo') }}
            className={cn(
              'flex flex-col items-start px-3 py-2.5 rounded-xl border text-left transition-all',
              `bg-gradient-to-br ${a.color} ${a.border}`,
              email === a.email && 'ring-1 ring-cyan-500/40',
            )}
          >
            <span className={cn('text-xs font-semibold', a.textColor)}>{a.role}</span>
            <span className="text-[10px] text-[var(--text-4)] mt-0.5 truncate w-full">{a.name}</span>
          </motion.button>
        ))}
      </div>

      <div className="relative mb-5">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-[var(--border)]" />
        </div>
        <div className="relative flex justify-center text-xs">
          <span className="px-3 bg-[var(--bg)] text-[var(--text-4)]">or enter credentials</span>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {/* API error */}
        <AnimatePresence>
          {apiError && (
            <motion.div
              initial={{ opacity: 0, y: -8, height: 0 }}
              animate={{ opacity: 1, y: 0, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm overflow-hidden"
            >
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{apiError}</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Email */}
        <div>
          <label className="section-label mb-1 block">Email address</label>
          <input
            {...register('email')}
            type="email"
            autoComplete="email"
            placeholder="clinician@hospital.org"
            className={cn('input w-full', errors.email && 'border-red-500/50 focus:border-red-500')}
          />
          {errors.email && (
            <p className="text-xs text-red-400 mt-1">{errors.email.message}</p>
          )}
        </div>

        {/* Password */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="section-label">Password</label>
            <Link
              to={ROUTES.FORGOT_PASSWORD}
              className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors"
            >
              Forgot password?
            </Link>
          </div>
          <div className="relative">
            <input
              {...register('password')}
              type={showPw ? 'text' : 'password'}
              autoComplete="current-password"
              placeholder="••••••••"
              className={cn('input w-full pr-10', errors.password && 'border-red-500/50 focus:border-red-500')}
            />
            <button
              type="button"
              onClick={() => setShowPw((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-3)] hover:text-[var(--text-2)] transition-colors"
              aria-label={showPw ? 'Hide password' : 'Show password'}
            >
              {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          {errors.password && (
            <p className="text-xs text-red-400 mt-1">{errors.password.message}</p>
          )}
        </div>

        {/* Remember me */}
        <label className="flex items-center gap-2.5 cursor-pointer">
          <div className="relative">
            <input {...register('rememberMe')} type="checkbox" className="sr-only peer" />
            <div className="w-4 h-4 rounded border border-[var(--border)] peer-checked:bg-cyan-500 peer-checked:border-cyan-500 transition-all flex items-center justify-center">
              <svg className="hidden peer-checked:block w-2.5 h-2.5 text-white" fill="currentColor" viewBox="0 0 12 12">
                <path d="M10 3L5 8.5 2 5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
              </svg>
            </div>
          </div>
          <span className="text-sm text-[var(--text-2)]">Keep me signed in for 30 days</span>
        </label>

        {/* Submit */}
        <motion.button
          type="submit"
          disabled={isPending}
          whileHover={!isPending ? { scale: 1.01 } : {}}
          whileTap={!isPending ? { scale: 0.98 } : {}}
          className={cn(
            'w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-bold text-white',
            'bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500',
            'shadow-[0_0_20px_rgba(14,165,233,0.25)] hover:shadow-[0_0_28px_rgba(14,165,233,0.4)]',
            'transition-all disabled:opacity-60 disabled:cursor-not-allowed',
          )}
        >
          {isPending ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Authenticating…
            </>
          ) : (
            <>
              <Lock className="w-4 h-4" />
              Sign in securely
              <ChevronRight className="w-4 h-4 ml-auto opacity-60" />
            </>
          )}
        </motion.button>
      </form>

      {/* Footer */}
      <p className="text-center text-xs text-[var(--text-4)] mt-6 leading-relaxed">
        By signing in you acknowledge this system contains{' '}
        <span className="text-[var(--text-3)]">Protected Health Information (PHI)</span>{' '}
        and agree to maintain confidentiality per HIPAA.
      </p>
    </AuthLayout>
  )
}
