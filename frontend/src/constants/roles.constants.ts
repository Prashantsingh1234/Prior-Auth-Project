import type { UserRole, Permission } from '@/types'
import { ROLE_PERMISSIONS } from '@/types'

export function hasPermission(role: UserRole, permission: Permission): boolean {
  return ROLE_PERMISSIONS[role].includes(permission)
}

export function hasAnyPermission(role: UserRole, permissions: Permission[]): boolean {
  return permissions.some((p) => hasPermission(role, p))
}

export function hasAllPermissions(role: UserRole, permissions: Permission[]): boolean {
  return permissions.every((p) => hasPermission(role, p))
}

export const ROLE_LABEL: Record<UserRole, string> = {
  reviewer: 'Clinical Reviewer',
  admin:    'Administrator',
  provider: 'Provider',
}

export const ROLE_COLOR: Record<UserRole, string> = {
  reviewer: 'text-brand-400',
  admin:    'text-violet-400',
  provider: 'text-emerald-400',
}