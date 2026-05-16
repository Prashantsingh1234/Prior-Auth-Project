import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { authService } from '@/services'
import { useAuthStore } from '@/store'
import { ROUTES, ROLE_HOME } from '@/config/routes.config'
import type { LoginCredentials } from '@/types'

export function useLogin() {
  const { setAuth, setMFAChallenge, setPendingEmail } = useAuthStore()
  const navigate = useNavigate()

  return useMutation({
    mutationFn: (credentials: LoginCredentials) => authService.login(credentials),
    onSuccess: (res, variables) => {
      if (res.requiresMFA && res.mfaChallenge) {
        // MFA required — store challenge and redirect
        setMFAChallenge(res.mfaChallenge)
        setPendingEmail(variables.email)
        navigate(ROUTES.MFA, { replace: true })
      } else {
        setAuth(res.user, res.tokens)
        navigate(ROLE_HOME[res.user.role] ?? ROUTES.DASHBOARD, { replace: true })
      }
    },
  })
}
