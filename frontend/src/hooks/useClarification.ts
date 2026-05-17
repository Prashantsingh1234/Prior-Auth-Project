import { useMutation, useQueryClient } from '@tanstack/react-query'
import { clarificationApi } from '@/api/clarification'
import { queryKeys } from '@/lib/queryKeys'
import { useErrorHandler } from '@/hooks/useErrorHandler'
import type { PACase } from '@/api/types'

interface RespondVariables {
  caseId:          string
  clarificationId: string
  response:        string
}

export function useClarification() {
  const qc                             = useQueryClient()
  const { handleSuccess, handleError } = useErrorHandler()

  return useMutation({
    mutationFn: ({ clarificationId, response }: RespondVariables) =>
      clarificationApi.respond(clarificationId, response),

    // ── Optimistic update ────────────────────────────────────────────────────
    onMutate: async ({ caseId, clarificationId }) => {
      await qc.cancelQueries({ queryKey: queryKeys.cases.detail(caseId) })
      const snapshot = qc.getQueryData<PACase>(queryKeys.cases.detail(caseId))

      qc.setQueryData<PACase>(queryKeys.cases.detail(caseId), (prev) => {
        if (!prev) return prev
        return {
          ...prev,
          clarifications: prev.clarifications.map((c) =>
            c.clarification_id === clarificationId
              ? { ...c, status: 'ANSWERED' as const, answered_at: new Date().toISOString() }
              : c,
          ),
        }
      })

      return { snapshot, caseId }
    },

    onError: (err, _vars, ctx) => {
      if (ctx?.snapshot) qc.setQueryData(queryKeys.cases.detail(ctx.caseId), ctx.snapshot)
      handleError(err, 'Failed to submit clarification response')
    },

    onSuccess: (_updated, { caseId }) => {
      // Replace optimistic data with server-confirmed data
      qc.invalidateQueries({ queryKey: queryKeys.cases.detail(caseId) })
      handleSuccess('Response submitted', 'Clarification response sent successfully')
    },
  })
}
