import { useMutation } from '@tanstack/react-query'
import { authService } from '@/services'
import type { OTPVerifyRequest } from '@/types'

export function useVerifyOTP() {
  return useMutation({
    mutationFn: (payload: OTPVerifyRequest) => authService.verifyOTP(payload),
  })
}
