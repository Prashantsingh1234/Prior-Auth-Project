import { z } from 'zod'

export const caseFiltersSchema = z.object({
  status:           z.array(z.string()).optional(),
  priority:         z.array(z.string()).optional(),
  aiRecommendation: z.array(z.string()).optional(),
  search:           z.string().optional(),
  dateFrom:         z.string().optional(),
  dateTo:           z.string().optional(),
})

export const submitCaseSchema = z.object({
  patientFirstName:  z.string().min(1, 'Required'),
  patientLastName:   z.string().min(1, 'Required'),
  patientMemberId:   z.string().min(1, 'Required'),
  patientDob:        z.string().min(1, 'Required'),
  providerNpi:       z.string().regex(/^\d{10}$/, 'NPI must be 10 digits'),
  providerName:      z.string().min(1, 'Required'),
  procedureCode:     z.string().min(1, 'Required'),
  diagnosisCodes:    z.array(z.string()).min(1, 'At least one diagnosis code required'),
  clinicalNotes:     z.string().min(50, 'Clinical notes must be at least 50 characters').max(50_000).optional(),
  priority:          z.enum(['ROUTINE', 'URGENT', 'EMERGENT']).default('ROUTINE'),
})

export type CaseFiltersFormData = z.infer<typeof caseFiltersSchema>
export type SubmitCaseFormData   = z.infer<typeof submitCaseSchema>