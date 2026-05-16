export type UserRole = 'reviewer' | 'admin' | 'provider'

export interface AuthUser {
  id: string
  name: string
  email: string
  role: UserRole
  organizationId?: string
  avatarUrl?: string
  permissions: Permission[]
}

export type Permission =
  | 'cases:read'
  | 'cases:write'
  | 'cases:delete'
  | 'review:approve'
  | 'review:deny'
  | 'review:escalate'
  | 'review:assign'
  | 'analytics:read'
  | 'policies:read'
  | 'policies:write'
  | 'audit:read'
  | 'admin:users'
  | 'admin:settings'

export const ROLE_PERMISSIONS: Record<UserRole, Permission[]> = {
  provider: [
    'cases:read',
    'cases:write',
  ],
  reviewer: [
    'cases:read',
    'review:approve',
    'review:deny',
    'review:escalate',
    'analytics:read',
    'policies:read',
    'audit:read',
  ],
  admin: [
    'cases:read',
    'cases:write',
    'cases:delete',
    'review:approve',
    'review:deny',
    'review:escalate',
    'review:assign',
    'analytics:read',
    'policies:read',
    'policies:write',
    'audit:read',
    'admin:users',
    'admin:settings',
  ],
}

export interface AuthTokens {
  accessToken: string
  refreshToken?: string
  expiresAt: number
}

export interface AuthState {
  user: AuthUser | null
  tokens: AuthTokens | null
  isAuthenticated: boolean
  isLoading: boolean
}

export interface LoginCredentials {
  email: string
  password: string
}

export interface LoginResponse {
  user: AuthUser
  tokens: AuthTokens
}