import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosError,
  type InternalAxiosRequestConfig,
} from 'axios'
import { tokenVault } from '@/lib/tokenVault'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'

function generateRequestId(): string {
  return `req_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`
}

let _isRefreshing = false
let _refreshQueue: Array<(token: string | null) => void> = []

function drainQueue(token: string | null) {
  _refreshQueue.forEach((cb) => cb(token))
  _refreshQueue = []
}

function clearSession() {
  tokenVault.clearTokens()
  localStorage.removeItem('pa-auth')
}

let _instance: AxiosInstance | null = null

export function getHttpClient(): AxiosInstance {
  if (_instance) return _instance

  _instance = axios.create({
    baseURL: BASE_URL,
    timeout: 30_000,
    headers: { 'Content-Type': 'application/json' },
  })

  _instance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    const token = tokenVault.getAccessToken()
    if (token) config.headers.Authorization = `Bearer ${token}`
    config.headers['X-Request-ID'] = generateRequestId()
    return config
  })

  _instance.interceptors.response.use(
    (res) => res,
    async (error: AxiosError) => {
      const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
      const status = error.response?.status

      if (status === 401 && !originalRequest._retry) {
        const refreshToken = tokenVault.getRefreshToken()

        if (refreshToken) {
          if (_isRefreshing) {
            return new Promise((resolve, reject) => {
              _refreshQueue.push((token) => {
                if (token) {
                  originalRequest.headers.Authorization = `Bearer ${token}`
                  resolve(_instance!.request(originalRequest))
                } else {
                  reject(error)
                }
              })
            })
          }

          originalRequest._retry = true
          _isRefreshing = true

          try {
            const { data } = await axios.post(`${BASE_URL}/auth/refresh`, { refresh_token: refreshToken })
            const { access_token, refresh_token, expires_in } = data
            const expiresAt = Date.now() + (expires_in ?? 1800) * 1000
            tokenVault.updateAccessToken(access_token, expiresAt)
            if (refresh_token) tokenVault.setTokens(access_token, expiresAt, refresh_token)
            drainQueue(access_token)
            originalRequest.headers.Authorization = `Bearer ${access_token}`
            return _instance!.request(originalRequest)
          } catch {
            drainQueue(null)
            clearSession()
            window.location.href = '/login'
            return Promise.reject(error)
          } finally {
            _isRefreshing = false
          }
        } else {
          clearSession()
          window.location.href = '/login'
        }
      }

      const message = (error.response?.data as any)?.detail ?? error.message ?? 'An unexpected error occurred'
      return Promise.reject({ statusCode: status ?? 0, message: String(message).slice(0, 500) })
    },
  )

  return _instance
}

const http = {
  get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return getHttpClient().get<T>(url, config).then((r) => r.data)
  },
  post<T, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig): Promise<T> {
    return getHttpClient().post<T>(url, data, config).then((r) => r.data)
  },
  put<T, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig): Promise<T> {
    return getHttpClient().put<T>(url, data, config).then((r) => r.data)
  },
  patch<T, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig): Promise<T> {
    return getHttpClient().patch<T>(url, data, config).then((r) => r.data)
  },
  delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return getHttpClient().delete<T>(url, config).then((r) => r.data)
  },
  upload<T>(url: string, formData: FormData, onProgress?: (pct: number) => void): Promise<T> {
    return getHttpClient().post<T>(url, formData, {
      // Do NOT set Content-Type manually — axios/browser must set it with the correct
      // multipart boundary. An explicit header without boundary causes 422 on the server.
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    }).then((r) => r.data)
  },
}

export default http
