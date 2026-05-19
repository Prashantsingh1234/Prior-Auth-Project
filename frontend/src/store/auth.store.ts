import { create } from 'zustand'
import { persist, devtools } from 'zustand/middleware'
import { tokenVault } from '@/lib/tokenVault'
import { ROLE_PERMISSIONS } from '@/types'
import type { AuthUser, AuthTokens, UserRole, Permission } from '@/types'

interface AuthStore {
  user:            AuthUser | null
  tokens:          AuthTokens | null
  isAuthenticated: boolean

  setAuth:     (user: AuthUser, tokens: AuthTokens) => void
  clearAuth:   () => void
  updateTokens:(tokens: AuthTokens) => void

  can:        (permission: Permission) => boolean
  hasRole:    (role: UserRole) => boolean
}

export const useAuthStore = create<AuthStore>()(
  devtools(
    persist(
      (set, get) => ({
        user:            null,
        tokens:          null,
        isAuthenticated: false,

        setAuth: (user, tokens) => {
          tokenVault.setTokens(tokens.accessToken, tokens.expiresAt, tokens.refreshToken)
          set({ user, tokens, isAuthenticated: true }, false, 'auth/setAuth')
        },

        clearAuth: () => {
          tokenVault.clearTokens()
          set({ user: null, tokens: null, isAuthenticated: false }, false, 'auth/clearAuth')
        },

        updateTokens: (tokens) => {
          tokenVault.updateAccessToken(tokens.accessToken, tokens.expiresAt)
          set({ tokens }, false, 'auth/updateTokens')
        },

        can:     (permission) => {
          const role = get().user?.role
          if (!role) return false
          return ROLE_PERMISSIONS[role].includes(permission)
        },

        hasRole: (role) => get().user?.role === role,
      }),
      {
        name: 'pa-auth',
        partialize: (s) => ({ user: s.user, isAuthenticated: s.isAuthenticated }),
      }
    ),
    { name: 'AuthStore' }
  )
)
