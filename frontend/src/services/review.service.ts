import http from './http.service'
import type { CaseDecision, AuditEvent, ReviewAction } from '@/types'
import type { SubmitDecisionPayload, AssignReviewerPayload } from '@/types'

const BASE = '/review'

export const reviewService = {
  approve(caseId: string, payload: { rationale: string }): Promise<CaseDecision> {
    return http.post(`${BASE}/${caseId}/approve`, payload)
  },

  deny(caseId: string, payload: { rationale: string }): Promise<CaseDecision> {
    return http.post(`${BASE}/${caseId}/deny`, payload)
  },

  escalate(caseId: string, payload: { reason: string }): Promise<void> {
    return http.post(`${BASE}/${caseId}/escalate`, payload)
  },

  pend(caseId: string, payload: { reason: string }): Promise<void> {
    return http.post(`${BASE}/${caseId}/pend`, payload)
  },

  assign(caseId: string, payload: AssignReviewerPayload): Promise<void> {
    return http.post(`${BASE}/${caseId}/assign`, payload)
  },

  getAuditTrail(caseId: string): Promise<AuditEvent[]> {
    return http.get(`${BASE}/${caseId}/audit`)
  },

  getActions(caseId: string): Promise<ReviewAction[]> {
    return http.get(`${BASE}/${caseId}/actions`)
  },

  submitClarificationResponse(clarificationId: string, response: string): Promise<void> {
    return http.post(`/clarifications/${clarificationId}/respond`, { response })
  },
}