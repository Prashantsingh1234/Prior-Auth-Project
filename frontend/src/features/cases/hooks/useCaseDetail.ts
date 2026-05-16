import { useQuery } from '@tanstack/react-query'
import { casesService } from '@/services'
import { APP_CONFIG } from '@/config/app.config'

export function useCaseDetail(caseId: string | undefined) {
  return useQuery({
    queryKey:  ['cases', 'detail', caseId],
    queryFn:   () => casesService.get(caseId!),
    enabled:   !!caseId,
    staleTime: APP_CONFIG.cache.caseDetailStaleMs,
  })
}