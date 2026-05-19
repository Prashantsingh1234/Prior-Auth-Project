import http from './http.service'

type Api<T> = { success: boolean; data: T; meta: Record<string, unknown> }

// ── Types (match backend snake_case) ───────────────────────────────────────

export interface CaseListItem {
  case_id: string
  case_number: string
  status: string
  priority: string
  service_type: string | null
  patient_name: string
  provider_name: string
  submitted_at: string | null
  updated_at: string
  assigned_reviewer_id: string | null
  clarification_count: number
  ai_recommendation: string | null
}

export interface ClarificationItem {
  clarification_id: string
  question: string
  status: string
  attempt_number: number
  sent_at: string
  answered_at: string | null
  response: string | null
}

export interface CaseDetail {
  case_id: string
  case_number: string
  status: string
  priority: string
  service_type: string | null
  cpt_codes: string[]
  icd_codes: string[]
  ai_recommendation: string | null
  ai_confidence_score: number | null
  ai_rationale: string | null
  clarification_count: number
  submitted_at: string | null
  patient: {
    patient_id: string
    first_name: string
    last_name: string
    date_of_birth: string
    member_id: string | null
    gender: string | null
  }
  provider: {
    provider_id: string
    npi: string
    first_name: string | null
    last_name: string | null
    specialty: string | null
    organization: string | null
  }
  documents: Array<{
    document_id: string
    original_filename: string
    document_type: string
    ocr_status: string | null
    uploaded_at: string
  }>
  policy_criteria: Array<{
    criterion_id: string
    criterion_name: string
    description: string
    status: string
    evidence: string | null
  }>
  decision: {
    outcome: string
    rationale: string
    decided_at: string
  } | null
  clarifications: ClarificationItem[]
}

export interface ReviewResult {
  case_id: string
  case_number: string
  new_status: string
  action_type: string
  message: string
}

export interface PASubmitPayload {
  patient: {
    first_name: string
    last_name: string
    date_of_birth: string
    member_id: string
    gender?: string
  }
  provider: {
    npi: string
    first_name?: string
    last_name?: string
    specialty?: string
    organization_name?: string
  }
  service_type: string
  cpt_codes: string[]
  icd_codes: string[]
  clinical_notes?: string
  priority: string
  source_channel?: string
}

// ── Service ────────────────────────────────────────────────────────────────

export const casesService = {
  async listCases(params?: {
    status?: string[]
    priority?: string[]
    assigned_to_me?: boolean
    page?: number
    page_size?: number
  }): Promise<{ cases: CaseListItem[]; total: number }> {
    const qs = new URLSearchParams()
    params?.status?.forEach((s) => qs.append('status', s))
    params?.priority?.forEach((p) => qs.append('priority', p))
    if (params?.assigned_to_me) qs.set('assigned_to_me', 'true')
    if (params?.page) qs.set('page', String(params.page))
    if (params?.page_size) qs.set('page_size', String(params.page_size))

    const url = `/cases${qs.toString() ? `?${qs}` : ''}`
    const res = await http.get<Api<{ cases: CaseListItem[]; meta: { total_items?: number; total?: number } }>>(url)
    const meta = res.data.meta ?? {}
    return {
      cases: res.data.cases ?? [],
      total: (meta.total_items ?? meta.total ?? 0) as number,
    }
  },

  async getCaseDetail(caseId: string): Promise<CaseDetail> {
    const res = await http.get<Api<CaseDetail>>(`/cases/${caseId}`)
    return res.data
  },

  async submitPARequest(payload: PASubmitPayload): Promise<{ case_id: string; case_number: string; status: string }> {
    const res = await http.post<Api<{ case_id: string; case_number: string; status: string }>>('/pa-requests', payload)
    return res.data
  },

  async submitIntake(formData: FormData): Promise<{ case_id: string; case_number: string; status: string; message: string }> {
    const res = await http.upload<Api<{ case_id: string; case_number: string; status: string; message: string }>>(
      '/pa-requests/intake',
      formData,
    )
    return res.data
  },

  async approveCase(caseId: string, body: { rationale: string; override_reason?: string | null }): Promise<ReviewResult> {
    const res = await http.post<Api<ReviewResult>>(`/review/${caseId}/approve`, body)
    return res.data
  },

  async denyCase(caseId: string, body: { rationale: string; override_reason?: string | null; denial_reason_code?: string | null }): Promise<ReviewResult> {
    const res = await http.post<Api<ReviewResult>>(`/review/${caseId}/deny`, body)
    return res.data
  },

  async pendCase(caseId: string, body: { rationale: string; pending_reason: string }): Promise<ReviewResult> {
    const res = await http.post<Api<ReviewResult>>(`/review/${caseId}/pend`, body)
    return res.data
  },

  async escalateCase(caseId: string, body: { reason: string; escalate_to?: string | null }): Promise<ReviewResult> {
    const res = await http.post<Api<ReviewResult>>(`/review/${caseId}/escalate`, body)
    return res.data
  },

  async addNote(caseId: string, note: string): Promise<ReviewResult> {
    const res = await http.post<Api<ReviewResult>>(`/review/${caseId}/notes`, { note })
    return res.data
  },

  async uploadDocument(caseId: string, file: File, documentType = 'CLINICAL_NOTES', onProgress?: (pct: number) => void): Promise<void> {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('document_type', documentType)
    await http.upload(`/cases/${caseId}/documents`, fd, onProgress)
  },

  async getClarifications(caseId: string): Promise<ClarificationItem[]> {
    const res = await http.get<Api<ClarificationItem[]>>(`/clarification/${caseId}`)
    return Array.isArray(res.data) ? res.data : []
  },

  async respondToClarification(caseId: string, body: { clarification_id: string; response: string }): Promise<void> {
    await http.post(`/clarification/${caseId}/respond`, body)
  },
}
