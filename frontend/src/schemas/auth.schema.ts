import { z } from 'zod'

// ─── Login ─────────────────────────────────────────────────────────────────────

export const loginSchema = z.object({
  email:    z.string().trim().email('Invalid email address').max(254),
  password: z.string().min(1, 'Password is required').max(128),
})

export type LoginFormData = z.infer<typeof loginSchema>

// ─── Password strength (used for set/reset flows, NOT login) ───────────────────

export const newPasswordSchema = z
  .string()
  .min(8,   'Must be at least 8 characters')
  .max(128, 'Too long')
  .regex(/[A-Z]/,        'Must contain an uppercase letter')
  .regex(/[a-z]/,        'Must contain a lowercase letter')
  .regex(/\d/,           'Must contain a number')
  .regex(/[^A-Za-z0-9]/, 'Must contain a special character')

// ─── Forgot password ───────────────────────────────────────────────────────────

export const forgotPasswordSchema = z.object({
  email: z.string().trim().email('Invalid email address').max(254),
})

export type ForgotPasswordFormData = z.infer<typeof forgotPasswordSchema>

// ─── Reset password ────────────────────────────────────────────────────────────

export const resetPasswordSchema = z
  .object({
    resetToken:      z.string().min(1),
    newPassword:     newPasswordSchema,
    confirmPassword: z.string(),
  })
  .refine((d) => d.newPassword === d.confirmPassword, {
    message: 'Passwords do not match',
    path:    ['confirmPassword'],
  })

export type ResetPasswordFormData = z.infer<typeof resetPasswordSchema>

// ─── MFA ───────────────────────────────────────────────────────────────────────

export const mfaSchema = z.object({
  code: z
    .string()
    .trim()
    .min(6,  'Code must be 6 digits')
    .max(8,  'Invalid code length')
    .regex(/^\d+$/, 'Code must be numeric'),
})

export type MFAFormData = z.infer<typeof mfaSchema>
