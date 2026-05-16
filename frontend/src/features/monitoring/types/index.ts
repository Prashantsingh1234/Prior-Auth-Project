export type HealthStatus = 'healthy' | 'degraded' | 'down'

export interface ServiceHealth {
  name:      string
  status:    HealthStatus
  latencyMs: number
  message?:  string
}

export interface PlatformHealth {
  status:   HealthStatus
  services: ServiceHealth[]
  checkedAt: string
}