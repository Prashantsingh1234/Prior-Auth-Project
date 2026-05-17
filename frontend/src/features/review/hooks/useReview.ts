import { useMutation, useQueryClient } from '@tanstack/react-query'
import { reviewApi } from '@/api/review'
import { queryKeys } from '@/lib/queryKeys'
import { useErrorHandler } from '@/hooks/useErrorHandler'
import type { PACase, CaseStatus } from '@/api/types'

// ─── Shared helpers ───────────────────────────────────────────────────────────

function optimisticStatus(
  qc: ReturnType<typeof useQueryClient>,
  caseId: string,
  status: CaseStatus,
): PACase | undefined {
  const key      = queryKeys.cases.detail(caseId)
  const snapshot = qc.getQueryData<PACase>(key)
  qc.setQueryData<PACase>(key, (prev) => prev ? { ...prev, status } : prev)
  return snapshot
}

function rollback(qc: ReturnType<typeof useQueryClient>, caseId: string, snapshot: PACase | undefined) {
  if (snapshot) qc.setQueryData(queryKeys.cases.detail(caseId), snapshot)
}

function invalidate(qc: ReturnType<typeof useQueryClient>, caseId: string) {
  qc.invalidateQueries({ queryKey: queryKeys.cases.detail(caseId) })
  qc.invalidateQueries({ queryKey: queryKeys.cases.queue() })
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useReview(caseId: string) {
  const qc                             = useQueryClient()
  const { handleError, handleSuccess } = useErrorHandler()

  const approve = useMutation({
    mutationFn: (rationale: string) => reviewApi.approve(caseId, { rationale }),

    onMutate: async () => {
      await qc.cancelQueries({ queryKey: queryKeys.cases.detail(caseId) })
      return { snapshot: optimisticStatus(qc, caseId, 'APPROVED') }
    },
    onError: (e, _v, ctx) => {
      rollback(qc, caseId, ctx?.snapshot)
      handleError(e, 'Failed to approve case')
    },
    onSuccess: (updated) => {
      qc.setQueryData(queryKeys.cases.detail(caseId), updated)
      handleSuccess('Case approved', `Case ${caseId} has been approved`)
    },
    onSettled: () => invalidate(qc, caseId),
  })

  const deny = useMutation({
    mutationFn: (rationale: string) => reviewApi.deny(caseId, { rationale }),

    onMutate: async () => {
      await qc.cancelQueries({ queryKey: queryKeys.cases.detail(caseId) })
      return { snapshot: optimisticStatus(qc, caseId, 'DENIED') }
    },
    onError: (e, _v, ctx) => {
      rollback(qc, caseId, ctx?.snapshot)
      handleError(e, 'Failed to deny case')
    },
    onSuccess: (updated) => {
      qc.setQueryData(queryKeys.cases.detail(caseId), updated)
      handleSuccess('Case denied', `Case ${caseId} has been denied`)
    },
    onSettled: () => invalidate(qc, caseId),
  })

  const escalate = useMutation({
    mutationFn: (reason: string) => reviewApi.escalate(caseId, { reason }),

    onMutate: async () => {
      await qc.cancelQueries({ queryKey: queryKeys.cases.detail(caseId) })
      return { snapshot: optimisticStatus(qc, caseId, 'ESCALATED') }
    },
    onError: (e, _v, ctx) => {
      rollback(qc, caseId, ctx?.snapshot)
      handleError(e, 'Failed to escalate case')
    },
    onSuccess: (updated) => {
      qc.setQueryData(queryKeys.cases.detail(caseId), updated)
      handleSuccess('Case escalated')
    },
    onSettled: () => invalidate(qc, caseId),
  })

  const pend = useMutation({
    mutationFn: (reason: string) => reviewApi.pend(caseId, { rationale: reason, pending_reason: reason }),

    onMutate: async () => {
      await qc.cancelQueries({ queryKey: queryKeys.cases.detail(caseId) })
      return { snapshot: optimisticStatus(qc, caseId, 'PENDED') }
    },
    onError: (e, _v, ctx) => {
      rollback(qc, caseId, ctx?.snapshot)
      handleError(e, 'Failed to pend case')
    },
    onSuccess: (updated) => {
      qc.setQueryData(queryKeys.cases.detail(caseId), updated)
      handleSuccess('Case pended — info requested')
    },
    onSettled: () => invalidate(qc, caseId),
  })

  const assign = useMutation({
    mutationFn:  (reviewerId: string) => reviewApi.assign(caseId, reviewerId),
    onSuccess:   (updated) => {
      qc.setQueryData(queryKeys.cases.detail(caseId), updated)
      handleSuccess('Reviewer assigned')
    },
    onError:     (e) => handleError(e, 'Failed to assign reviewer'),
    onSettled:   () => invalidate(qc, caseId),
  })

  const isSubmitting = approve.isPending || deny.isPending || escalate.isPending || pend.isPending

  return { approve, deny, escalate, pend, assign, isSubmitting }
}
