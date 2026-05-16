import { useMutation } from '@tanstack/react-query'
import { authService } from '@/services'
import { useAuthStore } from '@/store'
import type { ForgotPasswordRequest } from '@/types'

export function useForgotPassword() {
  const setPendingEmail = useAuthStore((s) => s.setPendingEmail)

  return useMutation({
    mutationFn: (payload: ForgotPasswordRequest) => authService.forgotPassword(payload),
    onSuccess: (_, variables) => {
      setPendingEmail(variables.email)
    },
  })
}
