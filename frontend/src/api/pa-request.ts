import http from '@/services/http.service'
import type { PACase, CasePriority } from './types'
import type { SubmitCaseFormData } from '@/schemas/case.schema'

// ─── Request shape (snake_case for backend) ───────────────────────────────────

export interface PARequestPayload {
  patient_first_name: string
  patient_last_name:  string
  patient_member_id:  string
  patient_dob:        string
  provider_npi:       string
  provider_name:      string
  procedure_code:     string
  diagnosis_codes:    string[]
  clinical_notes?:    string
  priority:           CasePriority
}

// ─── Form → wire transform ────────────────────────────────────────────────────

export function toPayload(form: SubmitCaseFormData): PARequestPayload {
  return {
    patient_first_name: form.patientFirstName,
    patient_last_name:  form.patientLastName,
    patient_member_id:  form.patientMemberId,
    patient_dob:        form.patientDob,
    provider_npi:       form.providerNpi,
    provider_name:      form.providerName,
    procedure_code:     form.procedureCode,
    diagnosis_codes:    form.diagnosisCodes,
    clinical_notes:     form.clinicalNotes,
    priority:           form.priority as CasePriority,
  }
}

// ─── API ──────────────────────────────────────────────────────────────────────

export const paRequestApi = {
  submit(payload: PARequestPayload): Promise<PACase> {
    return http.post<PACase, PARequestPayload>('/pa-request', payload)
  },
}
