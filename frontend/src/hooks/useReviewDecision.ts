import { useMutation, useQueryClient } from '@tanstack/react-query'
import http from '@/services/http.service'
import { queryKeys } from '@/lib/queryKeys'
import { useErrorHandler } from '@/hooks/useErrorHandler'
import type { PACase, DecisionOutcome, CaseStatus } from '@/api/types'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ReviewDecisionPayload {
  outcome:              DecisionOutcome
  rationale:            string
  override_reason?:     string
  denial_reason_code?:  string
}

// ─── Outcome → status mapping ─────────────────────────────────────────────────

const OUTCOME_TO_STATUS: Record<DecisionOutcome, CaseStatus> = {
  APPROVE: 'APPROVED',
  DENY:    'DENIED',
  PEND:    'PENDED',
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useReviewDecision(caseId: string) {
  const qc                             = useQueryClient()
  const { handleSuccess, handleError } = useErrorHandler()
  const key                            = queryKeys.cases.detail(caseId)

  const mutation = useMutation({
    mutationFn: (payload: ReviewDecisionPayload) =>
      http.post<PACase, ReviewDecisionPayload>(`/review/${caseId}`, payload),

    // ── Optimistic: reflect decision immediately in UI ───────────────────────
    onMutate: async (vars) => {
      await qc.cancelQueries({ queryKey: key })
      const snapshot = qc.getQueryData<PACase>(key)

      qc.setQueryData<PACase>(key, (prev) => {
        if (!prev) return prev
        return {
          ...prev,
          status: OUTCOME_TO_STATUS[vars.outcome] ?? prev.status,
          decision: {
            decision_id:     'optimistic',
            outcome:         vars.outcome,
            source:          'AI_RECOMMENDATION' as const,
            rationale:       vars.rationale,
            override_reason: vars.override_reason ?? null,
            decided_by:      null,
            decided_at:      new Date().toISOString(),
          },
        }
      })

      return { snapshot }
    },

    onError: (err, _vars, ctx) => {
      if (ctx?.snapshot) qc.setQueryData(key, ctx.snapshot)
      handleError(err, 'Failed to submit review decision')
    },

    onSuccess: (confirmed) => {
      // Replace optimistic data with server truth
      qc.setQueryData(key, confirmed)
      qc.invalidateQueries({ queryKey: queryKeys.cases.all() })
      handleSuccess('Decision submitted', `Case marked as ${confirmed.status.toLowerCase()}`)
    },
  })

  return {
    decide:    mutation.mutate,
    isPending: mutation.isPending,
    error:     mutation.error,
  }
}
