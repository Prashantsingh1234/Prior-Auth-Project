import http from '@/services/http.service'

// ─── Metrics ──────────────────────────────────────────────────────────────────

export interface MetricsResponse {
  total_cases:     number
  approved_cases:  number
  denied_cases:    number
  pending_cases:   number
  in_review_cases: number
  approval_rate:   number
  denial_rate:     number
  avg_review_ms:   number
  ai_accuracy:     number
  week_delta: {
    total:    number
    approved: number
    denied:   number
    pending:  number
  }
}

// ─── Health ───────────────────────────────────────────────────────────────────

export type ServiceStatus = 'ok' | 'slow' | 'error'
export type HealthState   = 'healthy' | 'degraded' | 'unhealthy'

export interface HealthStatus {
  status:    HealthState
  version:   string
  timestamp: string
  uptime_s:  number
  checks: {
    database:    ServiceStatus
    ai_service:  ServiceStatus
    storage:     ServiceStatus
    policy_db:   ServiceStatus
  }
}

// ─── API ──────────────────────────────────────────────────────────────────────

export const metricsApi = {
  get():    Promise<MetricsResponse> { return http.get<MetricsResponse>('/metrics') },
  health(): Promise<HealthStatus>    { return http.get<HealthStatus>('/health') },
}
