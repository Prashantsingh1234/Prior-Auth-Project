import http from './http.service'
import { ROLE_PERMISSIONS } from '@/types'
import type { LoginCredentials, LoginResponse, AuthUser, AuthTokens, UserRole } from '@/types'

function transformTokens(raw: any): AuthTokens {
  return {
    accessToken:  raw.access_token,
    refreshToken: raw.refresh_token,
    expiresAt:    Date.now() + (raw.expires_in ?? 1800) * 1000,
  }
}

function transformLogin(raw: any): LoginResponse {
  const role = (raw.user?.role ?? 'provider') as UserRole
  const user: AuthUser = {
    id:          raw.user.user_id,
    name:        raw.user.username,
    email:       raw.user.email,
    role,
    permissions: ROLE_PERMISSIONS[role] ?? [],
    organizationId: raw.user.organization ?? undefined,
  }
  return { user, tokens: transformTokens(raw) }
}

export const authService = {
  login(credentials: LoginCredentials): Promise<LoginResponse> {
    return http.post<any>('/auth/login', {
      username: credentials.email,
      password: credentials.password,
    }).then(transformLogin)
  },

  logout(): Promise<void> {
    return http.post('/auth/logout')
  },

  refresh(refreshToken: string): Promise<{ tokens: AuthTokens }> {
    return http.post<any>('/auth/refresh', { refresh_token: refreshToken })
      .then((data) => ({ tokens: transformTokens(data) }))
  },

  me(): Promise<AuthUser> {
    return http.get('/auth/me')
  },
}
