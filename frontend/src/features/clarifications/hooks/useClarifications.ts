import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import http from '@/services/http.service'
import { useErrorHandler } from '@/hooks'
import type { Clarification } from '@/types'

export function useClarifications(caseId: string) {
  const qc = useQueryClient()
  const { handleError, handleSuccess } = useErrorHandler()

  const query = useQuery({
    queryKey: ['cases', 'clarifications', caseId],
    queryFn:  () => http.get<Clarification[]>(`/cases/${caseId}/clarifications`),
    enabled:  !!caseId,
  })

  const respond = useMutation({
    mutationFn: ({ clarificationId, response }: { clarificationId: string; response: string }) =>
      http.post(`/clarifications/${clarificationId}/respond`, { response }),
    onSuccess: () => {
      handleSuccess('Response submitted')
      qc.invalidateQueries({ queryKey: ['cases', 'clarifications', caseId] })
    },
    onError: (e) => handleError(e, 'Failed to submit response'),
  })

  return { ...query, respond }
}