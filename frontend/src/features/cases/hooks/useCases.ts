import { useQuery } from '@tanstack/react-query'
import { casesService } from '@/services'
import { useCasesStore } from '@/store'
import { APP_CONFIG } from '@/config/app.config'

export function useCases() {
  const { filters, page, pageSize } = useCasesStore()

  return useQuery({
    queryKey: ['cases', 'list', filters, page, pageSize],
    queryFn:  () => casesService.list(filters, { page, pageSize }),
    staleTime: APP_CONFIG.cache.caseListStaleMs,
    placeholderData: (prev) => prev,
  })
}