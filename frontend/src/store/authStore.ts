import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { UserPublic } from '@/api/types'
import { clearTokens, setTokens } from '@/api/client'

interface AuthState {
  user: UserPublic | null
  isAuthenticated: boolean
  login: (user: UserPublic, accessToken: string, refreshToken: string, remember?: boolean) => void
  logout: () => void
  updateUser: (user: UserPublic) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,

      login: (user, accessToken, refreshToken, remember = false) => {
        setTokens(accessToken, refreshToken, remember)
        set({ user, isAuthenticated: true })
      },

      logout: () => {
        clearTokens()
        set({ user: null, isAuthenticated: false })
      },

      updateUser: (user) => set({ user }),
    }),
    {
      name: 'pa-auth',
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    },
  ),
)
