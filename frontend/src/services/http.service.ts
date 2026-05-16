import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosError,
  type InternalAxiosRequestConfig,
} from 'axios'
import { APP_CONFIG } from '@/config/app.config'
import type { ApiError } from '@/types'

// ─── Token refresh queue ──────────────────────────────────────────────────────
// Prevents duplicate refresh calls when multiple 401s arrive simultaneously.

let _isRefreshing = false
let _refreshQueue: Array<(accessToken: string | null) => void> = []

function enqueueAfterRefresh(cb: (token: string | null) => void) {
  _refreshQueue.push(cb)
}

function drainQueue(token: string | null) {
  _refreshQueue.forEach((cb) => cb(token))
  _refreshQueue = []
}

function readStoredState(): { accessToken?: string; refreshToken?: string } {
  try {
    const raw = localStorage.getItem('pa-auth')
    if (!raw) return {}
    const { state } = JSON.parse(raw)
    return {
      accessToken:  state?.tokens?.accessToken,
      refreshToken: state?.tokens?.refreshToken,
    }
  } catch {
    return {}
  }
}

function clearStoredAuth() {
  localStorage.removeItem('pa-auth')
}

function updateStoredTokens(tokens: { accessToken: string; expiresAt: number; refreshToken?: string }) {
  try {
    const raw = localStorage.getItem('pa-auth')
    if (!raw) return
    const parsed = JSON.parse(raw)
    parsed.state.tokens = { ...parsed.state.tokens, ...tokens }
    localStorage.setItem('pa-auth', JSON.stringify(parsed))
  } catch {
    // storage unavailable
  }
}

// ─── Axios singleton ──────────────────────────────────────────────────────────

let _instance: AxiosInstance | null = null

export function getHttpClient(): AxiosInstance {
  if (_instance) return _instance

  _instance = axios.create({
    baseURL: APP_CONFIG.api.baseUrl,
    timeout: APP_CONFIG.api.timeout,
    headers: {
      'Content-Type': 'application/json',
      'X-Client':     `pa-ui/${APP_CONFIG.version ?? '0.1.0'}`,
    },
  })

  // ── Request: attach JWT ────────────────────────────────────────────────────
  _instance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    const { accessToken } = readStoredState()
    if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
    return config
  })

  // ── Response: handle 401 with silent refresh ───────────────────────────────
  _instance.interceptors.response.use(
    (res) => res,
    async (error: AxiosError) => {
      const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
      const status = error.response?.status

      if (status === 401 && !originalRequest._retry) {
        const { refreshToken } = readStoredState()

        if (refreshToken) {
          if (_isRefreshing) {
            // Wait for the current refresh to finish
            return new Promise((resolve, reject) => {
              enqueueAfterRefresh((token) => {
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
            const { data } = await axios.post(
              `${APP_CONFIG.api.baseUrl}/auth/refresh`,
              { refreshToken },
              { headers: { 'Content-Type': 'application/json' } }
            )
            const newTokens = data.tokens
            updateStoredTokens(newTokens)
            drainQueue(newTokens.accessToken)
            originalRequest.headers.Authorization = `Bearer ${newTokens.accessToken}`
            return _instance!.request(originalRequest)
          } catch {
            drainQueue(null)
            clearStoredAuth()
            window.location.href = '/login?reason=session_expired'
            return Promise.reject(error)
          } finally {
            _isRefreshing = false
          }
        } else {
          clearStoredAuth()
          window.location.href = '/login?reason=session_expired'
        }
      }

      const apiError: ApiError = {
        statusCode:  status ?? 0,
        message:     (error.response?.data as any)?.detail
                     ?? error.message
                     ?? 'An unexpected error occurred',
        fieldErrors: (error.response?.data as any)?.errors,
      }
      return Promise.reject(apiError)
    }
  )

  return _instance
}

// ─── Typed helper methods ─────────────────────────────────────────────────────

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
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    }).then((r) => r.data)
  },
}

export default http
