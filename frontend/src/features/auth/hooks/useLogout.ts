import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '@/store'
import { authService } from '@/services'
import { ROUTES } from '@/config/routes.config'

export function useLogout() {
  const clearAuth   = useAuthStore((s) => s.clearAuth)
  const navigate    = useNavigate()
  const queryClient = useQueryClient()

  return useCallback(async () => {
    try { await authService.logout() } catch { /* ignore logout errors */ }
    clearAuth()
    queryClient.clear()
    navigate(ROUTES.LOGIN, { replace: true })
  }, [clearAuth, navigate, queryClient])
}
