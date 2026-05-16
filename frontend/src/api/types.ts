// ─── Enums mirroring backend app/models/enums.py ────────────────────────────

export type CaseStatus =
  | 'SUBMITTED'
  | 'PROCESSING'
  | 'PENDING_CLARIFICATION'
  | 'UNDER_REVIEW'
  | 'APPROVED'
  | 'DENIED'
  | 'PENDED'
  | 'ESCALATED'
  | 'CANCELLED'

export type CasePriority = 'ROUTINE' | 'URGENT' | 'EMERGENT'

export type ServiceType =
  | 'IMAGING'
  | 'LABORATORY'
  | 'DURABLE_MEDICAL_EQUIPMENT'
  | 'MEDICATION'
  | 'PROCEDURE'
  | 'SPECIALTY_REFERRAL'
  | 'HOME_HEALTH'
  | 'INPATIENT_ADMISSION'
  | 'OUTPATIENT_SURGERY'
  | 'BEHAVIORAL_HEALTH'
  | 'OTHER'

export type DocumentType =
  | 'PRESCRIPTION'
  | 'LAB_REPORT'
  | 'MEDICAL_NECESSITY'
  | 'REFERRAL'
  | 'EHR_EXPORT'
  | 'IMAGING_REPORT'
  | 'OTHER'

export type EntityType =
  | 'PATIENT_DEMOGRAPHICS'
  | 'DIAGNOSIS_CODE'
  | 'PROCEDURE_CODE'
  | 'MEDICATION'
  | 'LAB_VALUE'
  | 'COMPLICATION'
  | 'OTHER'

export type CriterionStatus =
  | 'PASS'
  | 'FAIL'
  | 'INSUFFICIENT_EVIDENCE'
  | 'NOT_APPLICABLE'

export type DecisionOutcome = 'APPROVE' | 'DENY' | 'PEND'
export type DecisionSource = 'AI_RECOMMENDATION' | 'REVIEWER_OVERRIDE'

export type ReviewerActionType =
  | 'ASSIGNED'
  | 'APPROVED'
  | 'DENIED'
  | 'PENDED'
  | 'OVERRIDE_APPROVED'
  | 'OVERRIDE_DENIED'
  | 'REQUESTED_CLARIFICATION'
  | 'ESCALATED'
  | 'ADDED_NOTE'

export type ClarificationStatus = 'PENDING' | 'ANSWERED' | 'TIMEOUT' | 'ESCALATED'

export type UserRole = 'admin' | 'reviewer' | 'provider'

// ─── Auth ────────────────────────────────────────────────────────────────────

export interface UserPublic {
  user_id: string
  email: string
  username: string
  role: UserRole
  npi: string | null
  organization: string | null
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: UserPublic
}

export interface LoginRequest {
  username: string
  password: string
}

// ─── PA Case ─────────────────────────────────────────────────────────────────

export interface Patient {
  patient_id: string
  first_name: string
  last_name: string
  date_of_birth: string
  member_id: string
  plan_id: string | null
  gender: string | null
}

export interface Provider {
  provider_id: string
  first_name: string
  last_name: string
  npi: string
  specialty: string | null
  organization: string | null
  phone: string | null
  fax: string | null
}

export interface CaseDocument {
  document_id: string
  document_type: DocumentType
  original_filename: string
  file_size_bytes: number
  content_type: string
  ocr_confidence: number | null
  uploaded_at: string
  storage_path: string
}

export interface ExtractedEntity {
  entity_id: string
  entity_type: EntityType
  value: string
  normalized_value: string | null
  confidence: number
  source_document_id: string | null
  // text position for document highlighting
  page_number: number | null
  char_offset_start: number | null
  char_offset_end: number | null
  bounding_box: BoundingBox | null
}

export interface BoundingBox {
  x: number
  y: number
  width: number
  height: number
  page: number
}

export interface PolicyCriterion {
  criterion_id: string
  criterion_name: string
  description: string
  status: CriterionStatus
  evidence: string | null
  policy_reference: string | null
  source_chunks: PolicyChunk[]
}

export interface PolicyChunk {
  chunk_id: string
  text: string
  source: string
  relevance_score: number
}

export interface CaseDecision {
  decision_id: string
  outcome: DecisionOutcome
  source: DecisionSource
  rationale: string
  override_reason: string | null
  decided_by: string | null
  decided_at: string
}

export interface ClarificationRequest {
  clarification_id: string
  question: string
  generated_by: 'llm' | 'template'
  status: ClarificationStatus
  sent_at: string
  answered_at: string | null
  response: string | null
  attempt_number: number
}

export interface AuditEvent {
  event_id: string
  event_type: ReviewerActionType
  actor_id: string
  actor_name: string
  actor_role: UserRole
  timestamp: string
  note: string | null
  metadata: Record<string, unknown>
}

export interface PACase {
  case_id: string
  case_number: string
  status: CaseStatus
  priority: CasePriority
  service_type: ServiceType
  cpt_codes: string[]
  icd_codes: string[]
  ai_recommendation: DecisionOutcome | null
  ai_confidence_score: number | null
  ai_rationale: string | null
  clarification_count: number
  assigned_reviewer_id: string | null
  submitted_at: string
  updated_at: string
  patient: Patient
  provider: Provider
  documents: CaseDocument[]
  extracted_entities: ExtractedEntity[]
  policy_criteria: PolicyCriterion[]
  decision: CaseDecision | null
  clarifications: ClarificationRequest[]
  audit_trail: AuditEvent[]
}

export interface CaseListItem {
  case_id: string
  case_number: string
  status: CaseStatus
  priority: CasePriority
  service_type: ServiceType
  ai_recommendation: DecisionOutcome | null
  ai_confidence_score: number | null
  patient_name: string
  provider_name: string
  submitted_at: string
  updated_at: string
  assigned_reviewer_id: string | null
  clarification_count: number
}

// ─── Review Actions ───────────────────────────────────────────────────────────

export interface ApproveRequest {
  rationale: string
  override_reason?: string
}

export interface DenyRequest {
  rationale: string
  override_reason?: string
  denial_reason_code?: string
}

export interface PendRequest {
  rationale: string
  pending_reason: string
}

export interface EscalateRequest {
  reason: string
  escalate_to?: string
}

export interface AddNoteRequest {
  note: string
}

// ─── API Response envelope ────────────────────────────────────────────────────

export interface ApiResponse<T> {
  success: boolean
  data: T
  meta?: PaginationMeta
}

export interface ApiError {
  success: false
  error: {
    code: string
    message: string
    details?: Record<string, unknown>
    request_id?: string
  }
}

export interface PaginationMeta {
  page: number
  page_size: number
  total_items: number
  total_pages: number
  has_next: boolean
  has_previous: boolean
}

export interface CaseListResponse {
  cases: CaseListItem[]
  meta: PaginationMeta
}

// ─── Filter & sort ───────────────────────────────────────────────────────────

export interface CaseFilters {
  status?: CaseStatus[]
  priority?: CasePriority[]
  service_type?: ServiceType[]
  assigned_to_me?: boolean
  page?: number
  page_size?: number
  sort_by?: 'submitted_at' | 'updated_at' | 'priority' | 'status'
  sort_dir?: 'asc' | 'desc'
}
