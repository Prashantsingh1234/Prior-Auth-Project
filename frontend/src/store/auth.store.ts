import { create } from 'zustand'
import { persist, devtools } from 'zustand/middleware'
import type { AuthUser, AuthTokens, UserRole, Permission } from '@/types'
import { ROLE_PERMISSIONS } from '@/types'

interface AuthStore {
  // State
  user:            AuthUser | null
  tokens:          AuthTokens | null
  isAuthenticated: boolean
  isHydrated:      boolean

  // Actions
  setAuth:    (user: AuthUser, tokens: AuthTokens) => void
  clearAuth:  () => void
  setHydrated:(v: boolean) => void

  // Derived selectors
  can:         (permission: Permission) => boolean
  hasRole:     (role: UserRole) => boolean
  hasAnyRole:  (roles: UserRole[]) => boolean
}

export const useAuthStore = create<AuthStore>()(
  devtools(
    persist(
      (set, get) => ({
        user:            null,
        tokens:          null,
        isAuthenticated: false,
        isHydrated:      false,

        setAuth: (user, tokens) =>
          set({ user, tokens, isAuthenticated: true }, false, 'auth/setAuth'),

        clearAuth: () =>
          set({ user: null, tokens: null, isAuthenticated: false }, false, 'auth/clearAuth'),

        setHydrated: (v) => set({ isHydrated: v }, false, 'auth/setHydrated'),

        can: (permission) => {
          const role = get().user?.role
          if (!role) return false
          return ROLE_PERMISSIONS[role].includes(permission)
        },

        hasRole: (role) => get().user?.role === role,

        hasAnyRole: (roles) => {
          const current = get().user?.role
          return current ? roles.includes(current) : false
        },
      }),
      {
        name: 'pa-auth',
        partialize: (s) => ({ user: s.user, tokens: s.tokens, isAuthenticated: s.isAuthenticated }),
        onRehydrateStorage: () => (state) => {
          state?.setHydrated(true)
        },
      }
    ),
    { name: 'AuthStore' }
  )
)