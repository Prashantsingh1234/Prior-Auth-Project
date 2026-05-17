import { forwardRef } from 'react'
import { cn } from '@/lib/utils'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string
  label?: string
  hint?:  string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, error, label, hint, id, required, ...props }, ref) => {
    const inputId   = id ?? label?.toLowerCase().replace(/\s+/g, '-')
    const hintId    = inputId ? `${inputId}-hint`  : undefined
    const errorId   = inputId ? `${inputId}-error` : undefined
    const describedBy = [hint && hintId, error && errorId].filter(Boolean).join(' ') || undefined

    return (
      <div className="space-y-1">
        {label && (
          <label htmlFor={inputId} className="section-label">
            {label}
            {required && <span aria-hidden="true" className="ml-0.5 text-red-400">*</span>}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          aria-describedby={describedBy}
          aria-invalid={error ? true : undefined}
          aria-required={required || undefined}
          required={required}
          className={cn(
            'input w-full',
            error && 'border-red-500/50 focus:ring-red-500/30',
            className
          )}
          {...props}
        />
        {hint && !error && <p id={hintId} className="text-xs text-[var(--text-3)]">{hint}</p>}
        {error && <p id={errorId} role="alert" className="text-xs text-red-400">{error}</p>}
      </div>
    )
  }
)
Input.displayName = 'Input'

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: string
  label?: string
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, label, id, required, ...props }, ref) => {
    const textareaId = id ?? label?.toLowerCase().replace(/\s+/g, '-')
    const errorId    = textareaId ? `${textareaId}-error` : undefined

    return (
      <div className="space-y-1">
        {label && (
          <label htmlFor={textareaId} className="section-label">
            {label}
            {required && <span aria-hidden="true" className="ml-0.5 text-red-400">*</span>}
          </label>
        )}
        <textarea
          ref={ref}
          id={textareaId}
          aria-describedby={error && errorId ? errorId : undefined}
          aria-invalid={error ? true : undefined}
          aria-required={required || undefined}
          required={required}
          className={cn(
            'input w-full resize-none',
            error && 'border-red-500/50 focus:ring-red-500/30',
            className
          )}
          {...props}
        />
        {error && <p id={errorId} role="alert" className="text-xs text-red-400">{error}</p>}
      </div>
    )
  }
)
Textarea.displayName = 'Textarea'
