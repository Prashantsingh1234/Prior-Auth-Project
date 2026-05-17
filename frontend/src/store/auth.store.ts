import { create } from 'zustand'
import { persist, devtools } from 'zustand/middleware'
import type { AuthUser, AuthTokens, UserRole, Permission, MFAChallenge } from '@/types'
import { ROLE_PERMISSIONS } from '@/types'
import { tokenVault } from '@/lib/tokenVault'

interface AuthStore {
  // Core auth state
  user:            AuthUser | null
  tokens:          AuthTokens | null
  isAuthenticated: boolean
  isHydrated:      boolean

  // MFA / OTP pending state
  mfaChallenge:    MFAChallenge | null
  pendingEmail:    string | null

  // Session timeout state
  sessionWarning:  boolean
  sessionExpiredReason: 'idle' | 'token' | null

  // Auth actions
  setAuth:          (user: AuthUser, tokens: AuthTokens) => void
  clearAuth:        () => void
  setHydrated:      (v: boolean) => void
  updateTokens:     (tokens: AuthTokens) => void

  // MFA actions
  setMFAChallenge:  (challenge: MFAChallenge | null) => void
  setPendingEmail:  (email: string | null) => void

  // Session actions
  setSessionWarning:(v: boolean) => void
  setSessionExpired:(reason: 'idle' | 'token') => void

  // RBAC selectors
  can:         (permission: Permission) => boolean
  hasRole:     (role: UserRole) => boolean
  hasAnyRole:  (roles: UserRole[]) => boolean
}

export const useAuthStore = create<AuthStore>()(
  devtools(
    persist(
      (set, get) => ({
        user:                 null,
        tokens:               null,
        isAuthenticated:      false,
        isHydrated:           false,
        mfaChallenge:         null,
        pendingEmail:         null,
        sessionWarning:       false,
        sessionExpiredReason: null,

        setAuth: (user, tokens) => {
          // Store tokens in the secure vault — NOT in localStorage
          tokenVault.setTokens(tokens.accessToken, tokens.expiresAt, tokens.refreshToken)
          set(
            { user, tokens, isAuthenticated: true, mfaChallenge: null, pendingEmail: null, sessionWarning: false, sessionExpiredReason: null },
            false,
            'auth/setAuth',
          )
        },

        clearAuth: () => {
          tokenVault.clearTokens()
          set(
            { user: null, tokens: null, isAuthenticated: false, mfaChallenge: null, pendingEmail: null },
            false,
            'auth/clearAuth',
          )
        },

        setHydrated: (v) => set({ isHydrated: v }, false, 'auth/setHydrated'),

        updateTokens: (tokens) => {
          tokenVault.updateAccessToken(tokens.accessToken, tokens.expiresAt)
          set({ tokens }, false, 'auth/updateTokens')
        },

        setMFAChallenge: (challenge) =>
          set({ mfaChallenge: challenge }, false, 'auth/setMFAChallenge'),

        setPendingEmail: (email) =>
          set({ pendingEmail: email }, false, 'auth/setPendingEmail'),

        setSessionWarning: (v) =>
          set({ sessionWarning: v }, false, 'auth/setSessionWarning'),

        setSessionExpired: (reason) =>
          set({ sessionExpiredReason: reason }, false, 'auth/setSessionExpired'),

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
        partialize: (s) => ({
          user:            s.user,
          // tokens intentionally excluded — access token stays in memory,
          // refresh token stays in sessionStorage via tokenVault
          isAuthenticated: s.isAuthenticated,
          pendingEmail:    s.pendingEmail,
          mfaChallenge:    s.mfaChallenge,
        }),
        onRehydrateStorage: () => (state) => {
          state?.setHydrated(true)
        },
      }
    ),
    { name: 'AuthStore' }
  )
)
