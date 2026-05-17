import { useQuery } from '@tanstack/react-query'
import { metricsApi } from '@/api/metrics'
import { queryKeys } from '@/lib/queryKeys'
import { APP_CONFIG } from '@/config/app.config'

export function useMetrics() {
  return useQuery({
    queryKey:        queryKeys.metrics.data(),
    queryFn:         () => metricsApi.get(),
    staleTime:       APP_CONFIG.cache.metricsStaleMs,
    gcTime:          5 * 60_000,
    refetchInterval: APP_CONFIG.cache.metricsStaleMs,
    // Keep showing last-known data while refetching
    placeholderData: (prev) => prev,
    // Don't retry on 4xx — metrics endpoint either works or it doesn't
    retry: (count, err: any) => err?.statusCode >= 500 && count < 2,
  })
}
