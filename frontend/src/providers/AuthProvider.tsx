import { useEffect } from 'react'
import { useAuthStore } from '@/store'
import { APP_CONFIG } from '@/config/app.config'

interface Props { children: React.ReactNode }

/**
 * Handles proactive token expiry detection.
 * Checks every minute; clears auth and redirects if within the refresh buffer.
 */
export function AuthProvider({ children }: Props) {
  const { tokens, clearAuth } = useAuthStore()

  useEffect(() => {
    if (!tokens) return
    const interval = setInterval(() => {
      const expiresIn = tokens.expiresAt - Date.now()
      if (expiresIn < APP_CONFIG.auth.tokenRefreshBufferMs) {
        clearAuth()
        window.location.href = '/login'
      }
    }, 60_000)
    return () => clearInterval(interval)
  }, [tokens, clearAuth])

  return <>{children}</>
}