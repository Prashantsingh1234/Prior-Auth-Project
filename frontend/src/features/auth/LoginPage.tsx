import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store'
import { authService } from '@/services/auth.service'
import { Shield } from 'lucide-react'

const DEMO_ACCOUNTS = [
  { role: 'Provider', email: 'provider@pa-review.com', password: 'Provider@secure123!' },
  { role: 'Reviewer', email: 'reviewer@pa-review.com', password: 'Review@secure123!' },
  { role: 'Admin',    email: 'admin@pa-review.com',    password: 'Admin@secure123!' },
]

function roleHome(role?: string) {
  if (role === 'reviewer') return '/reviewer/dashboard'
  if (role === 'admin')    return '/admin/dashboard'
  return '/provider/dashboard'
}

export default function LoginPage() {
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  const setAuth  = useAuthStore((s) => s.setAuth)
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as any)?.from?.pathname ?? null

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await authService.login({ email, password })
      setAuth(res.user, res.tokens)
      navigate(from ?? roleHome(res.user.role), { replace: true })
    } catch {
      setError('Invalid email or password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-blue-600 mb-4">
            <Shield className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-xl font-semibold text-gray-900">PA Review Platform</h1>
          <p className="mt-1 text-sm text-gray-500">Sign in to your account</p>
        </div>

        {/* Form */}
        <div className="card p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input"
                placeholder="you@example.com"
                required
                autoFocus
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                placeholder="••••••••"
                required
              />
            </div>

            {error && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
                {error}
              </p>
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full py-2.5">
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>

        {/* Demo accounts */}
        <div className="mt-4">
          <p className="text-xs text-gray-400 text-center mb-2">Demo accounts</p>
          <div className="flex gap-2">
            {DEMO_ACCOUNTS.map((a) => (
              <button
                key={a.role}
                type="button"
                onClick={() => { setEmail(a.email); setPassword(a.password) }}
                className="flex-1 px-3 py-2 text-xs border border-gray-200 rounded-md bg-white hover:bg-gray-50 text-gray-600 transition-colors"
              >
                {a.role}
              </button>
            ))}
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-gray-400">
          HIPAA Compliant · All activity is logged
        </p>
      </div>
    </div>
  )
}
