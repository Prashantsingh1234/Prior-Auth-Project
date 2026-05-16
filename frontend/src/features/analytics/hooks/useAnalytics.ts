import { useQuery } from '@tanstack/react-query'
import { analyticsService } from '@/services'
import { APP_CONFIG } from '@/config/app.config'

export function useMetrics() {
  return useQuery({
    queryKey:  ['analytics', 'metrics'],
    queryFn:   analyticsService.getMetrics,
    staleTime: APP_CONFIG.cache.metricsStaleMs,
    refetchInterval: APP_CONFIG.cache.metricsStaleMs,
  })
}

export function useAccuracyTrend(days = 30) {
  return useQuery({
    queryKey:  ['analytics', 'accuracy', days],
    queryFn:   () => analyticsService.getAccuracyTrend(days),
    staleTime: APP_CONFIG.cache.analyticsStaleMs,
  })
}

export function useOutcomes() {
  return useQuery({
    queryKey:  ['analytics', 'outcomes'],
    queryFn:   analyticsService.getOutcomeDistribution,
    staleTime: APP_CONFIG.cache.analyticsStaleMs,
  })
}

export function useLatency() {
  return useQuery({
    queryKey:  ['analytics', 'latency'],
    queryFn:   analyticsService.getLatencyBreakdown,
    staleTime: APP_CONFIG.cache.analyticsStaleMs,
  })
}