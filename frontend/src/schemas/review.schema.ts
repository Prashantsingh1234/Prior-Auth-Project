import { z } from 'zod'

export const decisionSchema = z.object({
  outcome:   z.enum(['APPROVED', 'DENIED', 'PENDED', 'ESCALATED']),
  rationale: z
    .string()
    .min(20,  'Rationale must be at least 20 characters')
    .max(2000, 'Rationale must be under 2000 characters'),
})

export const assignSchema = z.object({
  reviewerId: z.string().uuid('Invalid reviewer ID'),
})

export const clarificationResponseSchema = z.object({
  response: z.string().min(10, 'Response must be at least 10 characters').max(5000),
})

export type DecisionFormData               = z.infer<typeof decisionSchema>
export type AssignFormData                 = z.infer<typeof assignSchema>
export type ClarificationResponseFormData  = z.infer<typeof clarificationResponseSchema>