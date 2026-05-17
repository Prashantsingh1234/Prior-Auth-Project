import http from '@/services/http.service'
import type {
  ApiResponse,
  ApproveRequest,
  DenyRequest,
  EscalateRequest,
  PACase,
  PendRequest,
  AddNoteRequest,
} from './types'
import type { ReviewDecisionPayload } from '@/hooks/useReviewDecision'

// ─── Unified decision endpoint ────────────────────────────────────────────────
// POST /review/{id}  — single entrypoint the backend dispatches by `outcome`

async function decide(caseId: string, payload: ReviewDecisionPayload): Promise<PACase> {
  const res = await http.post<ApiResponse<PACase>, ReviewDecisionPayload>(
    `/review/${caseId}`,
    payload,
  )
  return res.data
}

// ─── Per-action convenience wrappers (kept for backward compat) ───────────────

export const reviewApi = {
  decide,

  approve: (caseId: string, body: ApproveRequest): Promise<PACase> =>
    decide(caseId, { outcome: 'APPROVE', rationale: body.rationale, override_reason: body.override_reason }),

  deny: (caseId: string, body: DenyRequest): Promise<PACase> =>
    decide(caseId, { outcome: 'DENY', rationale: body.rationale, override_reason: body.override_reason, denial_reason_code: body.denial_reason_code }),

  pend: (caseId: string, body: PendRequest): Promise<PACase> =>
    decide(caseId, { outcome: 'PEND', rationale: `${body.rationale} — ${body.pending_reason}` }),

  escalate: async (caseId: string, body: EscalateRequest): Promise<PACase> => {
    const res = await http.post<ApiResponse<PACase>, EscalateRequest>(
      `/review/${caseId}/escalate`,
      body,
    )
    return res.data
  },

  addNote: (caseId: string, body: AddNoteRequest): Promise<void> =>
    http.post<void, AddNoteRequest>(`/review/${caseId}/notes`, body),

  assign: async (caseId: string, reviewerId: string): Promise<PACase> => {
    const res = await http.post<ApiResponse<PACase>>(`/review/${caseId}/assign`, { reviewer_id: reviewerId })
    return res.data
  },

  respondToClarification: (caseId: string, clarificationId: string, response: string): Promise<void> =>
    http.post<void>(`/review/${caseId}/clarifications/${clarificationId}/respond`, { response }),
}
