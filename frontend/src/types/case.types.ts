// ─── Case domain ──────────────────────────────────────────────────────────────

export type CaseStatus =
  | 'SUBMITTED'
  | 'UNDER_REVIEW'
  | 'PENDING_INFO'
  | 'APPROVED'
  | 'DENIED'
  | 'ESCALATED'
  | 'WITHDRAWN'

export type CasePriority = 'ROUTINE' | 'URGENT' | 'EMERGENT'

export type AIRecommendation = 'APPROVE' | 'DENY' | 'REQUEST_INFO' | 'ESCALATE'

export type DecisionOutcome = 'APPROVED' | 'DENIED' | 'PENDED' | 'ESCALATED'

export interface Patient {
  id: string
  firstName: string
  lastName: string
  memberId: string
  dateOfBirth: string
  insurancePlanId: string
}

export interface Provider {
  id: string
  npi: string
  name: string
  specialty: string
  organizationName?: string
}

export interface ClinicalDocument {
  id: string
  caseId: string
  documentType: DocumentType
  filename: string
  sizeBytes: number
  pageCount: number
  uploadedAt: string
  ocrStatus: 'PENDING' | 'PROCESSING' | 'COMPLETE' | 'FAILED'
  extractedText?: string
}

export type DocumentType =
  | 'CLINICAL_NOTES'
  | 'LAB_RESULTS'
  | 'IMAGING_REPORT'
  | 'PHYSICIAN_ORDER'
  | 'REFERRAL_LETTER'
  | 'INSURANCE_CARD'
  | 'OTHER'

export interface ClinicalEntity {
  id: string
  entityType: EntityType
  value: string
  normalizedValue?: string
  context: string
  confidence: number
  pageNumber: number
  source: string
}

export type EntityType =
  | 'PATIENT'
  | 'PROVIDER'
  | 'DIAGNOSIS'
  | 'MEDICATION'
  | 'CPT_CODE'
  | 'ICD_CODE'
  | 'DATE'
  | 'LAB_VALUE'
  | 'PROCEDURE'

export interface PolicyMatch {
  id: string
  policyId: string
  policyName: string
  sectionRef: string
  similarityScore: number
  relevantText: string
}

export interface PolicyCriterion {
  id: string
  criterion: string
  status: 'MET' | 'NOT_MET' | 'INSUFFICIENT' | 'NOT_APPLICABLE'
  evidence: string
  policyRef: string
  confidence: number
}

export interface PACase {
  id: string
  caseNumber: string
  status: CaseStatus
  priority: CasePriority
  patient: Patient
  provider: Provider
  procedureCode: string
  procedureDescription: string
  diagnosisCodes: string[]
  clinicalNotes?: string
  submittedAt: string
  updatedAt: string
  assignedReviewerId?: string
  aiRecommendation?: AIRecommendation
  aiConfidence?: number
  documents: ClinicalDocument[]
  entities: ClinicalEntity[]
  policyMatches: PolicyMatch[]
  criteria: PolicyCriterion[]
  decision?: CaseDecision
  deletedAt?: string
}

export interface CaseDecision {
  id: string
  caseId: string
  outcome: DecisionOutcome
  rationale: string
  reviewerId: string
  reviewerName: string
  decidedAt: string
  source: 'HUMAN' | 'AI_ASSISTED'
}

export interface CaseListItem {
  id: string
  caseNumber: string
  status: CaseStatus
  priority: CasePriority
  patientName: string
  procedureCode: string
  procedureDescription: string
  submittedAt: string
  aiRecommendation?: AIRecommendation
  aiConfidence?: number
  assignedReviewerName?: string
}

export interface CaseFilters {
  status?: CaseStatus[]
  priority?: CasePriority[]
  aiRecommendation?: AIRecommendation[]
  assignedReviewerId?: string
  dateFrom?: string
  dateTo?: string
  search?: string
}

export interface PaginatedCases {
  items: CaseListItem[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}