import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { authService } from '@/services'
import { useAuthStore } from '@/store'
import { useErrorHandler } from '@/hooks'
import { ROUTES } from '@/config/routes.config'
import type { LoginCredentials } from '@/types'

export function useLogin() {
  const { setAuth } = useAuthStore()
  const navigate    = useNavigate()
  const { handleError } = useErrorHandler()

  return useMutation({
    mutationFn: (credentials: LoginCredentials) => authService.login(credentials),
    onSuccess: ({ user, tokens }) => {
      setAuth(user, tokens)
      navigate(ROUTES.DASHBOARD, { replace: true })
    },
    onError: (error) => handleError(error, 'Invalid email or password'),
  })
}