import http from './http.service'
import type {
  LoginCredentials,
  LoginResponse,
  AuthUser,
  AuthTokens,
  MFAVerifyRequest,
  MFAVerifyResponse,
  OTPVerifyRequest,
  OTPVerifyResponse,
  ForgotPasswordRequest,
  ForgotPasswordResponse,
  ResetPasswordRequest,
} from '@/types'

export const authService = {
  login(credentials: LoginCredentials): Promise<LoginResponse> {
    return http.post('/auth/login', credentials)
  },

  logout(): Promise<void> {
    return http.post('/auth/logout')
  },

  refresh(refreshToken: string): Promise<{ tokens: AuthTokens }> {
    return http.post('/auth/refresh', { refreshToken })
  },

  me(): Promise<AuthUser> {
    return http.get('/auth/me')
  },

  // ── MFA ──────────────────────────────────────────────────────────────────
  verifyMFA(payload: MFAVerifyRequest): Promise<MFAVerifyResponse> {
    return http.post('/auth/mfa/verify', payload)
  },

  resendMFA(challengeId: string): Promise<void> {
    return http.post('/auth/mfa/resend', { challengeId })
  },

  // ── OTP ──────────────────────────────────────────────────────────────────
  verifyOTP(payload: OTPVerifyRequest): Promise<OTPVerifyResponse> {
    return http.post('/auth/otp/verify', payload)
  },

  // ── Forgot / Reset ────────────────────────────────────────────────────────
  forgotPassword(payload: ForgotPasswordRequest): Promise<ForgotPasswordResponse> {
    return http.post('/auth/forgot-password', payload)
  },

  resetPassword(payload: ResetPasswordRequest): Promise<void> {
    return http.post('/auth/reset-password', payload)
  },
}
