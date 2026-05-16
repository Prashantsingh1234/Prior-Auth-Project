export type UserRole = 'reviewer' | 'admin' | 'provider'

export interface AuthUser {
  id: string
  name: string
  email: string
  role: UserRole
  organizationId?: string
  avatarUrl?: string
  permissions: Permission[]
  mfaEnabled?: boolean
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
  rememberMe?: boolean
}

export interface LoginResponse {
  user: AuthUser
  tokens: AuthTokens
  requiresMFA?: boolean
  mfaChallenge?: MFAChallenge
}

// ─── MFA ─────────────────────────────────────────────────────────────────────

export type MFAMethod = 'totp' | 'sms' | 'email' | 'backup_code'

export interface MFAChallenge {
  challengeId: string
  method: MFAMethod
  maskedContact?: string
  expiresAt: number
}

export interface MFAVerifyRequest {
  challengeId: string
  code: string
  method: MFAMethod
}

export interface MFAVerifyResponse {
  user: AuthUser
  tokens: AuthTokens
}

// ─── OTP ─────────────────────────────────────────────────────────────────────

export type OTPPurpose = 'mfa' | 'password_reset' | 'email_verification'

export interface OTPVerifyRequest {
  email: string
  code: string
  purpose: OTPPurpose
}

export interface OTPVerifyResponse {
  verified: boolean
  resetToken?: string
}

// ─── Forgot / Reset Password ──────────────────────────────────────────────────

export interface ForgotPasswordRequest {
  email: string
}

export interface ForgotPasswordResponse {
  message: string
  maskedEmail: string
}

export interface ResetPasswordRequest {
  resetToken: string
  newPassword: string
  confirmPassword: string
}

// ─── Session ──────────────────────────────────────────────────────────────────

export interface SessionInfo {
  lastActivity: number
  expiresAt: number
}

export type SessionTimeoutReason = 'expired' | 'manual' | 'forced'
