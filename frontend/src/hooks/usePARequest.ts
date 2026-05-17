import { useMutation, useQueryClient } from '@tanstack/react-query'
import { paRequestApi, toPayload } from '@/api/pa-request'
import { queryKeys } from '@/lib/queryKeys'
import { useErrorHandler } from '@/hooks/useErrorHandler'
import type { SubmitCaseFormData } from '@/schemas/case.schema'

export function usePARequest() {
  const qc                             = useQueryClient()
  const { handleSuccess, handleError } = useErrorHandler()

  const mutation = useMutation({
    mutationFn: (form: SubmitCaseFormData) => paRequestApi.submit(toPayload(form)),

    onSuccess: (newCase) => {
      // Seed detail cache immediately — navigating to the new case is instant
      qc.setQueryData(queryKeys.cases.detail(newCase.case_id), newCase)
      // Invalidate list + queue so they refetch with the new entry
      qc.invalidateQueries({ queryKey: queryKeys.cases.all() })
      handleSuccess('Request submitted', `Case ${newCase.case_number} created successfully`)
    },

    onError: (err) => handleError(err, 'Failed to submit PA request'),
  })

  return {
    submit:      mutation.mutate,
    submitAsync: mutation.mutateAsync,
    isPending:   mutation.isPending,
    isSuccess:   mutation.isSuccess,
    error:       mutation.error,
    result:      mutation.data,
    reset:       mutation.reset,
  }
}
