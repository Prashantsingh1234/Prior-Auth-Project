import { useQuery } from '@tanstack/react-query'
import http from '@/services/http.service'
import type { PolicyCriterion } from '@/types'

export function usePolicyCriteria(caseId: string | undefined) {
  return useQuery({
    queryKey: ['cases', 'criteria', caseId],
    queryFn:  () => http.get<PolicyCriterion[]>(`/cases/${caseId}/criteria`),
    enabled:  !!caseId,
    staleTime: 60_000,
  })
}