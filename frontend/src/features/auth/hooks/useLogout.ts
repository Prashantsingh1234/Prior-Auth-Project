import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store'
import { authService } from '@/services'
import { ROUTES } from '@/config/routes.config'

export function useLogout() {
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const navigate  = useNavigate()

  return useCallback(async () => {
    try { await authService.logout() } catch { /* ignore logout errors */ }
    clearAuth()
    navigate(ROUTES.LOGIN, { replace: true })
  }, [clearAuth, navigate])
}