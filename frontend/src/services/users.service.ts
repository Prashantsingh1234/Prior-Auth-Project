import http from './http.service'

export interface UserPublic {
  user_id: string
  email: string
  username: string
  role: string
  is_active: boolean
  created_at: string
  last_login_at: string | null
  organization: string | null
}

export interface CreateUserPayload {
  email: string
  username: string
  password: string
  role: 'admin' | 'reviewer' | 'provider'
  npi?: string
  organization?: string
}

export const usersService = {
  async createUser(payload: CreateUserPayload): Promise<UserPublic> {
    return http.post<UserPublic>('/users', payload)
  },

  async getUserById(userId: string): Promise<UserPublic> {
    return http.get<UserPublic>(`/users/${userId}`)
  },
}
