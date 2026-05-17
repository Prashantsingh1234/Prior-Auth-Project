import { z } from 'zod'

// ─── Sanitize helpers ─────────────────────────────────────────────────────────
// Validation (.min / .max) MUST come before .transform() — ZodEffects can't
// be chained with additional validators.

function safeString(maxLen: number, minLen = 0, minMsg = '') {
  return z
    .string()
    .min(minLen, minMsg || `Must be at least ${minLen} character${minLen === 1 ? '' : 's'}`)
    .max(maxLen, `Must be ${maxLen} characters or fewer`)
    .transform((v) => v.replace(/<[^>]*>/g, '').trim())  // strip HTML, trim whitespace
}

// ─── Case filters ─────────────────────────────────────────────────────────────

export const caseFiltersSchema = z.object({
  status:           z.array(z.string()).optional(),
  priority:         z.array(z.string()).optional(),
  aiRecommendation: z.array(z.string()).optional(),
  search:           z.string().max(200).transform((v) => v.replace(/<[^>]*>/g, '').trim()).optional(),
  dateFrom:         z.string().optional(),
  dateTo:           z.string().optional(),
})

export type CaseFiltersFormData = z.infer<typeof caseFiltersSchema>

// ─── Submit case ──────────────────────────────────────────────────────────────

export const submitCaseSchema = z.object({
  patientFirstName: safeString(100, 1, 'Required'),
  patientLastName:  safeString(100, 1, 'Required'),
  patientMemberId:  z.string().trim().min(1, 'Required').max(50)
                      .regex(/^[\w\-]+$/, 'Invalid member ID format'),
  patientDob:       z.string().min(1, 'Required'),
  providerNpi:      z.string().trim().regex(/^\d{10}$/, 'NPI must be exactly 10 digits'),
  providerName:     safeString(200, 1, 'Required'),
  procedureCode:    z.string().trim().min(1, 'Required').max(20)
                      .regex(/^[\w\-.]+$/, 'Invalid procedure code'),
  diagnosisCodes:   z.array(z.string().trim().max(20)).min(1, 'At least one diagnosis code required'),
  clinicalNotes:    safeString(50_000, 50, 'Clinical notes must be at least 50 characters').optional(),
  priority:         z.enum(['ROUTINE', 'URGENT', 'EMERGENT']).default('ROUTINE'),
})

export type SubmitCaseFormData = z.infer<typeof submitCaseSchema>
