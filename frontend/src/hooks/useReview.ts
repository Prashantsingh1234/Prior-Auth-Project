import { useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { reviewApi } from '@/api/review'
import type {
  ApproveRequest, DenyRequest, EscalateRequest, PendRequest, AddNoteRequest,
} from '@/api/types'
import { useInvalidateCase } from './useCase'
import { useReviewStore } from '@/store/reviewStore'
import { extractErrorMessage } from '@/api/client'

function useReviewMutation<TBody>(
  caseId: string,
  mutationFn: (body: TBody) => Promise<unknown>,
  successMessage: string,
) {
  const invalidate = useInvalidateCase()
  const setModal   = useReviewStore((s) => s.setActiveModal)

  return useMutation({
    mutationFn,
    onSuccess: () => {
      toast.success(successMessage)
      setModal(null)
      invalidate(caseId)
    },
    onError: (error) => {
      toast.error(extractErrorMessage(error))
    },
  })
}

export function useApprove(caseId: string) {
  return useReviewMutation<ApproveRequest>(
    caseId,
    (body) => reviewApi.approve(caseId, body),
    'Case approved successfully',
  )
}

export function useDeny(caseId: string) {
  return useReviewMutation<DenyRequest>(
    caseId,
    (body) => reviewApi.deny(caseId, body),
    'Case denied',
  )
}

export function usePend(caseId: string) {
  return useReviewMutation<PendRequest>(
    caseId,
    (body) => reviewApi.pend(caseId, body),
    'Case pended — awaiting additional information',
  )
}

export function useEscalate(caseId: string) {
  return useReviewMutation<EscalateRequest>(
    caseId,
    (body) => reviewApi.escalate(caseId, body),
    'Case escalated to senior reviewer',
  )
}

export function useAddNote(caseId: string) {
  return useReviewMutation<AddNoteRequest>(
    caseId,
    (body) => reviewApi.addNote(caseId, body),
    'Note added',
  )
}

export function useRespondToClarification() {
  const invalidate = useInvalidateCase()

  return useMutation({
    mutationFn: ({
      caseId, clarificationId, response,
    }: { caseId: string; clarificationId: string; response: string }) =>
      reviewApi.respondToClarification(caseId, clarificationId, response),
    onSuccess: (_, vars) => {
      toast.success('Response submitted')
      invalidate(vars.caseId)
    },
    onError: (error: unknown) => {
      toast.error(extractErrorMessage(error))
    },
  })
}
