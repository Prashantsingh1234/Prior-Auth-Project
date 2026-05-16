import { useQuery } from '@tanstack/react-query'
import http from '@/services/http.service'
import type { PlatformHealth } from '../types'

export function useHealthCheck() {
  return useQuery({
    queryKey:        ['monitoring', 'health'],
    queryFn:         () => http.get<PlatformHealth>('/health/ready'),
    refetchInterval: 30_000,
    staleTime:       25_000,
    retry:           false,
  })
}