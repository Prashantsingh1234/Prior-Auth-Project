import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosError } from 'axios'
import { APP_CONFIG } from '@/config/app.config'
import type { ApiError } from '@/types'

// ─── Axios singleton ──────────────────────────────────────────────────────────

let _instance: AxiosInstance | null = null

export function getHttpClient(): AxiosInstance {
  if (_instance) return _instance

  _instance = axios.create({
    baseURL:         APP_CONFIG.api.baseUrl,
    timeout:         APP_CONFIG.api.timeout,
    headers: {
      'Content-Type': 'application/json',
      'X-Client':     `pa-ui/${APP_CONFIG.version}`,
    },
  })

  // ── Request: attach JWT ──────────────────────────────────────────────────
  _instance.interceptors.request.use((config) => {
    try {
      const raw = localStorage.getItem('pa-auth')
      if (raw) {
        const { state } = JSON.parse(raw)
        const token = state?.tokens?.accessToken
        if (token) config.headers.Authorization = `Bearer ${token}`
      }
    } catch {
      // storage unavailable
    }
    return config
  })

  // ── Response: normalise errors ───────────────────────────────────────────
  _instance.interceptors.response.use(
    (res) => res,
    async (error: AxiosError) => {
      const status = error.response?.status

      if (status === 401) {
        // Token expired — clear auth and redirect
        localStorage.removeItem('pa-auth')
        window.location.href = '/login'
      }

      const apiError: ApiError = {
        statusCode: status ?? 0,
        message:    (error.response?.data as any)?.detail
                    ?? error.message
                    ?? 'An unexpected error occurred',
        fieldErrors: (error.response?.data as any)?.errors,
      }
      return Promise.reject(apiError)
    }
  )

  return _instance
}

// ─── Typed helper methods ──────────────────────────────────────────────────────

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