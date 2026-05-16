import http from './http.service'
import type { LoginCredentials, LoginResponse, AuthUser } from '@/types'

export const authService = {
  login(credentials: LoginCredentials): Promise<LoginResponse> {
    return http.post('/auth/login', credentials)
  },

  logout(): Promise<void> {
    return http.post('/auth/logout')
  },

  refresh(refreshToken: string): Promise<Pick<LoginResponse, 'tokens'>> {
    return http.post('/auth/refresh', { refreshToken })
  },

  me(): Promise<AuthUser> {
    return http.get('/auth/me')
  },
}