import type { DecisionOutcome } from './case.types'

export interface ReviewAction {
  id: string
  caseId: string
  actionType: ReviewActionType
  performedBy: string
  performedByName: string
  performedAt: string
  metadata?: Record<string, unknown>
}

export type ReviewActionType =
  | 'OPENED'
  | 'APPROVED'
  | 'DENIED'
  | 'ESCALATED'
  | 'PENDED'
  | 'ASSIGNED'
  | 'NOTE_ADDED'
  | 'DOCUMENT_VIEWED'

export interface AuditEvent {
  id: string
  caseId: string
  eventType: AuditEventType
  description: string
  actorId: string
  actorRole: string
  actorName: string
  occurredAt: string
  metadata?: Record<string, unknown>
  ipAddress?: string
}

export type AuditEventType =
  | 'SUBMITTED'
  | 'ASSIGNED'
  | 'AI_PROCESSED'
  | 'REVIEWED'
  | 'APPROVED'
  | 'DENIED'
  | 'ESCALATED'
  | 'PENDED'
  | 'CLARIFICATION_REQUESTED'
  | 'CLARIFICATION_ANSWERED'
  | 'DOCUMENT_UPLOADED'
  | 'DOCUMENT_VIEWED'
  | 'STATUS_CHANGED'

export interface SubmitDecisionPayload {
  outcome: DecisionOutcome
  rationale: string
}

export interface AssignReviewerPayload {
  reviewerId: string
}