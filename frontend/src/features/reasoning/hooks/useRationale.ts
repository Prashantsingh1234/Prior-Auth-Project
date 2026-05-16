import { useQuery } from '@tanstack/react-query'
import { casesService } from '@/services'
import { APP_CONFIG } from '@/config/app.config'

export function useRationale(caseId: string | undefined) {
  return useQuery({
    queryKey:  ['cases', 'ai-result', caseId],
    queryFn:   () => casesService.getAIResult(caseId!),
    enabled:   !!caseId,
    staleTime: APP_CONFIG.cache.caseDetailStaleMs,
    retry:     1,
  })
}