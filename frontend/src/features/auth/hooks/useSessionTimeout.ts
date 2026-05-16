import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store'
import { authService } from '@/services'
import { ROUTES } from '@/config/routes.config'

const WARNING_THRESHOLD_MS = 5 * 60 * 1000   // show warning at 5 min remaining
const TICK_INTERVAL_MS     = 1_000            // update countdown every second

export function useSessionTimeout() {
  const { tokens, isAuthenticated, updateTokens, clearAuth, setSessionWarning } = useAuthStore()
  const navigate = useNavigate()

  const [millisRemaining, setMillisRemaining] = useState<number>(Infinity)
  const [showWarning, setShowWarning]         = useState(false)
  const [isContinuing, setIsContinuing]       = useState(false)

  // Tick: update remaining time, show warning, auto-logout
  useEffect(() => {
    if (!isAuthenticated || !tokens) return

    const tick = () => {
      const remaining = tokens.expiresAt - Date.now()
      setMillisRemaining(remaining)

      if (remaining <= 0) {
        clearAuth()
        setShowWarning(false)
        navigate(`${ROUTES.LOGIN}?reason=session_expired`, { replace: true })
        return
      }

      if (remaining <= WARNING_THRESHOLD_MS) {
        setShowWarning(true)
        setSessionWarning(true)
      }
    }

    tick()
    const interval = setInterval(tick, TICK_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [tokens, isAuthenticated, clearAuth, navigate, setSessionWarning])

  // Reset warning state on new tokens
  useEffect(() => {
    if (tokens && tokens.expiresAt - Date.now() > WARNING_THRESHOLD_MS) {
      setShowWarning(false)
      setSessionWarning(false)
    }
  }, [tokens, setSessionWarning])

  const continueSession = useCallback(async () => {
    if (!tokens?.refreshToken || isContinuing) return
    setIsContinuing(true)
    try {
      const res = await authService.refresh(tokens.refreshToken)
      updateTokens(res.tokens)
      setShowWarning(false)
      setSessionWarning(false)
    } catch {
      clearAuth()
      navigate(`${ROUTES.LOGIN}?reason=session_expired`, { replace: true })
    } finally {
      setIsContinuing(false)
    }
  }, [tokens, isContinuing, updateTokens, clearAuth, navigate, setSessionWarning])

  const signOut = useCallback(async () => {
    try { await authService.logout() } catch { /* ignore */ }
    clearAuth()
    navigate(ROUTES.LOGIN, { replace: true })
  }, [clearAuth, navigate])

  return { millisRemaining, showWarning, isContinuing, continueSession, signOut }
}
