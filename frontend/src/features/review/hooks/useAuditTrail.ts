import { useQuery } from '@tanstack/react-query'
import { reviewService } from '@/services'

export function useAuditTrail(caseId: string) {
  return useQuery({
    queryKey: ['cases', 'audit', caseId],
    queryFn:  () => reviewService.getAuditTrail(caseId),
    enabled:  !!caseId,
    staleTime: 60_000,
  })
}