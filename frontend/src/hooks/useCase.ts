import { useQuery, useQueryClient } from '@tanstack/react-query'
import { casesApi } from '@/api/cases'
import { queryKeys } from '@/lib/queryKeys'
import { APP_CONFIG } from '@/config/app.config'
import type { CaseFilters, CaseStatus, PACase } from '@/api/types'

// ─── Polling strategy by status ───────────────────────────────────────────────
// Active statuses need frequent polling; terminal statuses don't need any.

function pollInterval(data: PACase | undefined): number | false {
  if (!data) return false
  switch (data.status as CaseStatus) {
    case 'SUBMITTED':
    case 'PROCESSING':
      return APP_CONFIG.ai.pollingIntervalMs        // 3 s — AI is running
    case 'UNDER_REVIEW':
      return 15_000                                 // 15 s — reviewer may act
    case 'PENDING_CLARIFICATION':
      return 30_000                                 // 30 s — waiting on provider
    default:
      return false                                  // terminal — no polling
  }
}

// ─── Hooks ────────────────────────────────────────────────────────────────────

export function useCase(caseId: string) {
  return useQuery({
    queryKey: queryKeys.cases.detail(caseId),
    queryFn:  () => casesApi.get(caseId),
    enabled:  Boolean(caseId),
    staleTime: APP_CONFIG.cache.caseDetailStaleMs,
    // Polling frequency adapts to case status
    refetchInterval: (query) => pollInterval(query.state.data),
    // Always show cached data while fetching in background
    placeholderData: (prev) => prev,
    retry: (count, err: any) => err?.statusCode !== 404 && count < APP_CONFIG.api.retries,
  })
}

export function useCaseList(filters: CaseFilters = {}) {
  return useQuery({
    queryKey: queryKeys.cases.list(filters),
    queryFn:  () => casesApi.list(filters),
    staleTime: APP_CONFIG.cache.caseListStaleMs,
    placeholderData: (prev) => prev,
  })
}

export function useCaseQueue(filters: Omit<CaseFilters, 'status'> = {}) {
  return useQuery({
    queryKey: queryKeys.cases.queue(),
    queryFn:  () => casesApi.queue(filters),
    staleTime: 10_000,
    refetchInterval: 15_000,
    placeholderData: (prev) => prev,
  })
}

export function useInvalidateCase() {
  const qc = useQueryClient()
  return (caseId: string) => {
    qc.invalidateQueries({ queryKey: queryKeys.cases.detail(caseId) })
    qc.invalidateQueries({ queryKey: queryKeys.cases.queue() })
    qc.invalidateQueries({ queryKey: queryKeys.cases.lists() })
  }
}

// Re-export legacy key shape so callers of the old `caseKeys` import don't break
export const caseKeys = queryKeys.cases
