import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { authService } from '@/services'
import { useAuthStore } from '@/store'
import { ROLE_HOME, ROUTES } from '@/config/routes.config'
import type { MFAVerifyRequest } from '@/types'

export function useMFA() {
  const { setAuth, setMFAChallenge } = useAuthStore()
  const navigate = useNavigate()

  return useMutation({
    mutationFn: (payload: MFAVerifyRequest) => authService.verifyMFA(payload),
    onSuccess: (res) => {
      setMFAChallenge(null)
      setAuth(res.user, res.tokens)
      navigate(ROLE_HOME[res.user.role] ?? ROUTES.DASHBOARD, { replace: true })
    },
  })
}
