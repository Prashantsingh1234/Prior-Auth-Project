import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { APP_CONFIG } from '@/config/app.config'

const queryClient = new QueryClient({
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

interface Props { children: React.ReactNode }

export function QueryProvider({ children }: Props) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {APP_CONFIG.features.enableDevTools && <ReactQueryDevtools buttonPosition="bottom-right" />}
    </QueryClientProvider>
  )
}

export { queryClient }