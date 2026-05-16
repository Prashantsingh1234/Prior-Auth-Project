import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { CaseFilters } from '@/api/types'
import { casesApi } from '@/api/cases'

export const caseKeys = {
  all:    () => ['cases'] as const,
  lists:  () => [...caseKeys.all(), 'list'] as const,
  list:   (filters: CaseFilters) => [...caseKeys.lists(), filters] as const,
  detail: (id: string) => [...caseKeys.all(), 'detail', id] as const,
  queue:  () => [...caseKeys.all(), 'queue'] as const,
}

export function useCaseQueue(filters: CaseFilters = {}) {
  return useQuery({
    queryKey: caseKeys.queue(),
    queryFn:  () => casesApi.queue(filters),
    refetchInterval: 15_000,  // poll every 15 s for real-time queue updates
    staleTime: 10_000,
  })
}

export function useCaseList(filters: CaseFilters = {}) {
  return useQuery({
    queryKey: caseKeys.list(filters),
    queryFn:  () => casesApi.list(filters),
    staleTime: 30_000,
  })
}

export function useCase(caseId: string) {
  return useQuery({
    queryKey: caseKeys.detail(caseId),
    queryFn:  () => casesApi.get(caseId),
    enabled:  Boolean(caseId),
    refetchInterval: 10_000,  // poll active case for updates
    staleTime: 5_000,
  })
}

export function useInvalidateCase() {
  const queryClient = useQueryClient()
  return (caseId: string) => {
    queryClient.invalidateQueries({ queryKey: caseKeys.detail(caseId) })
    queryClient.invalidateQueries({ queryKey: caseKeys.queue() })
  }
}
