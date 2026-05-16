import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/store/authStore'
import { extractErrorMessage } from '@/api/client'

export function useLogin() {
  const { login } = useAuthStore()
  const navigate   = useNavigate()

  return useMutation({
    mutationFn: authApi.login,
    onSuccess: (data) => {
      login(data.user, data.access_token, data.refresh_token)
      toast.success(`Welcome back, ${data.user.username}`)
      navigate('/dashboard', { replace: true })
    },
    onError: (error) => {
      toast.error(extractErrorMessage(error))
    },
  })
}

export function useLogout() {
  const { logout } = useAuthStore()
  const navigate    = useNavigate()

  return useMutation({
    mutationFn: authApi.logout,
    onSettled: () => {
      logout()
      navigate('/login', { replace: true })
    },
  })
}
