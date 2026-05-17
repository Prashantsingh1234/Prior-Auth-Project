import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosError,
  type InternalAxiosRequestConfig,
} from 'axios'
import { APP_CONFIG } from '@/config/app.config'
import { tokenVault  } from '@/lib/tokenVault'
import type { ApiError } from '@/types'

// ─── Request ID ───────────────────────────────────────────────────────────────
// Each request gets a unique ID for server-side tracing (correlates FE errors
// with backend logs via the X-Request-ID header).

function generateRequestId(): string {
  const ts  = Date.now().toString(36)
  const rnd = Math.random().toString(36).slice(2, 7)
  return `req_${ts}_${rnd}`
}

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

function clearStoredSession() {
  tokenVault.clearTokens()
  localStorage.removeItem('pa-auth')   // clear persisted Zustand auth state
}

// ─── Axios singleton ──────────────────────────────────────────────────────────

let _instance: AxiosInstance | null = null

export function getHttpClient(): AxiosInstance {
  if (_instance) return _instance

  _instance = axios.create({
    baseURL: APP_CONFIG.api.baseUrl,
    timeout: APP_CONFIG.api.timeout,
    headers: {
      'Content-Type':  'application/json',
      'X-Client':      `pa-ui/${APP_CONFIG.version ?? '0.1.0'}`,
      'X-Requested-With': 'XMLHttpRequest',  // helps server distinguish AJAX from form posts
    },
  })

  // ── Request: attach JWT + tracing headers ─────────────────────────────────
  _instance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    const token = tokenVault.getAccessToken()
    if (token) config.headers.Authorization = `Bearer ${token}`

    // Unique ID per request — correlates FE errors with server logs
    config.headers['X-Request-ID'] = generateRequestId()

    return config
  })

  // ── Response: handle 401 with silent refresh ──────────────────────────────
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
              { headers: { 'Content-Type': 'application/json' } },
            )
            const newTokens = data.tokens
            tokenVault.updateAccessToken(newTokens.accessToken, newTokens.expiresAt)
            if (newTokens.refreshToken) {
              // Server rotated the refresh token — persist the new one
              tokenVault.setTokens(newTokens.accessToken, newTokens.expiresAt, newTokens.refreshToken)
            }
            drainQueue(newTokens.accessToken)
            originalRequest.headers.Authorization = `Bearer ${newTokens.accessToken}`
            return _instance!.request(originalRequest)
          } catch {
            drainQueue(null)
            clearStoredSession()
            window.location.href = '/login?reason=session_expired'
            return Promise.reject(error)
          } finally {
            _isRefreshing = false
          }
        } else {
          clearStoredSession()
          window.location.href = '/login?reason=session_expired'
        }
      }

      // ── Sanitise error before surfacing to UI ────────────────────────────
      // Never leak internal server details — map to the ApiError shape only.
      const apiError: ApiError = {
        statusCode:  status ?? 0,
        message:     sanitiseServerMessage(
                       (error.response?.data as any)?.detail ?? error.message,
                     ),
        fieldErrors: (error.response?.data as any)?.errors,
      }
      return Promise.reject(apiError)
    },
  )

  return _instance
}

// Strip any HTML/script content a backend error message might contain
function sanitiseServerMessage(raw: unknown): string {
  if (typeof raw !== 'string') return 'An unexpected error occurred'
  return raw.replace(/<[^>]*>/g, '').slice(0, 500).trim() || 'An unexpected error occurred'
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
