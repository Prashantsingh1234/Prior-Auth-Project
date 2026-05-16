import http from './http.service'
import type { PlatformMetrics, AnalyticsSeries, WorkflowLatency, OutcomeDistribution } from '@/types'

export const analyticsService = {
  getMetrics(): Promise<PlatformMetrics> {
    return http.get('/metrics')
  },

  getAccuracyTrend(days: number = 30): Promise<AnalyticsSeries[]> {
    return http.get('/analytics/accuracy', { params: { days } })
  },

  getVolumeTrend(days: number = 30): Promise<AnalyticsSeries[]> {
    return http.get('/analytics/volume', { params: { days } })
  },

  getLatencyBreakdown(): Promise<WorkflowLatency[]> {
    return http.get('/analytics/latency')
  },

  getOutcomeDistribution(): Promise<OutcomeDistribution[]> {
    return http.get('/analytics/outcomes')
  },
}