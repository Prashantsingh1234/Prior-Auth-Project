import { forwardRef } from 'react'
import { Loader2 } from 'lucide-react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)] disabled:pointer-events-none disabled:opacity-50 select-none',
  {
    variants: {
      variant: {
        primary:  'bg-brand-500 text-white hover:bg-brand-600 active:bg-brand-700 shadow-sm',
        ghost:    'text-[var(--text-2)] hover:bg-[var(--elevated)] hover:text-[var(--text-1)]',
        outline:  'border border-[var(--border)] text-[var(--text-1)] hover:bg-[var(--elevated)]',
        approve:  'bg-emerald-600 text-white hover:bg-emerald-700 active:bg-emerald-800 shadow-approve',
        deny:     'bg-red-600    text-white hover:bg-red-700    active:bg-red-800    shadow-deny',
        pend:     'bg-amber-500  text-white hover:bg-amber-600  active:bg-amber-700',
        escalate: 'bg-violet-600 text-white hover:bg-violet-700 active:bg-violet-800',
        danger:   'bg-red-600    text-white hover:bg-red-700',
      },
      size: {
        xs: 'h-6  px-2   text-xs',
        sm: 'h-7  px-3   text-xs',
        md: 'h-9  px-4   text-sm',
        lg: 'h-11 px-6   text-base',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?:   boolean
  leftIcon?:  React.ReactNode
  rightIcon?: React.ReactNode
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, loading, disabled, leftIcon, rightIcon, children, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading
        ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
        : leftIcon
      }
      {children}
      {!loading && rightIcon}
    </button>
  )
)
Button.displayName = 'Button'
