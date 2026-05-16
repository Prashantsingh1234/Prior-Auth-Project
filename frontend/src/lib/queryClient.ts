import { QueryClient } from '@tanstack/react-query'
import { APP_CONFIG } from '@/config/app.config'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime:            APP_CONFIG.cache.caseListStaleMs,
      gcTime:               5 * 60_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error: any) => {
        if (error?.statusCode >= 400 && error?.statusCode < 500) return false
        return failureCount < APP_CONFIG.api.retries
      },
    },
    mutations: { retry: 0 },
  },
})