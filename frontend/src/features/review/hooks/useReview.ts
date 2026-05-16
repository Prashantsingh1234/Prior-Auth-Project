import { useMutation, useQueryClient } from '@tanstack/react-query'
import { reviewService } from '@/services'
import { useErrorHandler } from '@/hooks'

export function useReview(caseId: string) {
  const qc = useQueryClient()
  const { handleError, handleSuccess } = useErrorHandler()

  const invalidate = () => qc.invalidateQueries({ queryKey: ['cases', 'detail', caseId] })

  const approve = useMutation({
    mutationFn: (rationale: string) => reviewService.approve(caseId, { rationale }),
    onSuccess: () => { handleSuccess('Case approved', `Case ${caseId} has been approved`); invalidate() },
    onError:   (e) => handleError(e, 'Failed to approve case'),
  })

  const deny = useMutation({
    mutationFn: (rationale: string) => reviewService.deny(caseId, { rationale }),
    onSuccess: () => { handleSuccess('Case denied', `Case ${caseId} has been denied`); invalidate() },
    onError:   (e) => handleError(e, 'Failed to deny case'),
  })

  const escalate = useMutation({
    mutationFn: (reason: string) => reviewService.escalate(caseId, { reason }),
    onSuccess: () => { handleSuccess('Case escalated'); invalidate() },
    onError:   (e) => handleError(e, 'Failed to escalate case'),
  })

  const pend = useMutation({
    mutationFn: (reason: string) => reviewService.pend(caseId, { reason }),
    onSuccess: () => { handleSuccess('Case pended — info requested'); invalidate() },
    onError:   (e) => handleError(e, 'Failed to pend case'),
  })

  const assign = useMutation({
    mutationFn: (reviewerId: string) => reviewService.assign(caseId, { reviewerId }),
    onSuccess: () => { handleSuccess('Reviewer assigned'); invalidate() },
    onError:   (e) => handleError(e, 'Failed to assign reviewer'),
  })

  const isSubmitting = approve.isPending || deny.isPending || escalate.isPending || pend.isPending

  return { approve, deny, escalate, pend, assign, isSubmitting }
}