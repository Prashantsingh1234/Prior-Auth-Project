import { useAuthStore } from '@/store'
import type { Permission, UserRole } from '@/types'

/**
 * Provides permission checks derived from the authenticated user's role.
 * All checks are memoised via Zustand selector — no re-render unless role changes.
 */
export function usePermissions() {
  const user = useAuthStore((s) => s.user)
  const can  = useAuthStore((s) => s.can)
  const hasRole     = useAuthStore((s) => s.hasRole)
  const hasAnyRole  = useAuthStore((s) => s.hasAnyRole)

  return {
    user,
    can,
    hasRole,
    hasAnyRole,
    isReviewer: hasRole('reviewer'),
    isAdmin:    hasRole('admin'),
    isProvider: hasRole('provider'),
    canApprove:  can('review:approve'),
    canDeny:     can('review:deny'),
    canEscalate: can('review:escalate'),
    canAssign:   can('review:assign'),
    canViewAnalytics: can('analytics:read'),
    canManageUsers:   can('admin:users'),
  }
}