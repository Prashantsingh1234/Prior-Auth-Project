import { useQuery } from '@tanstack/react-query'
import { metricsApi, type HealthState } from '@/api/metrics'
import { queryKeys } from '@/lib/queryKeys'

const POLL_MS = 30_000

export function useHealth() {
  const query = useQuery({
    queryKey:        queryKeys.health.status(),
    queryFn:         () => metricsApi.health(),
    staleTime:       POLL_MS / 2,
    refetchInterval: POLL_MS,
    // Single retry — health check is lightweight and failing twice means real issue
    retry:           1,
    retryDelay:      2_000,
    placeholderData: (prev) => prev,
  })

  const status: HealthState = query.data?.status ?? (query.isError ? 'unhealthy' : 'healthy')

  return {
    ...query,
    status,
    isDegraded:  status === 'degraded',
    isUnhealthy: status === 'unhealthy',
    checks:      query.data?.checks,
  }
}
