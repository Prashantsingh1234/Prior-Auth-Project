import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-full border font-medium whitespace-nowrap',
  {
    variants: {
      variant: {
        default:   'bg-slate-500/10   border-slate-500/20   text-slate-400',
        brand:     'bg-brand-500/15   border-brand-500/25   text-brand-400',
        success:   'bg-emerald-500/15 border-emerald-500/25 text-emerald-400',
        warning:   'bg-amber-500/15   border-amber-500/25   text-amber-400',
        danger:    'bg-red-500/15     border-red-500/25     text-red-400',
        violet:    'bg-violet-500/15  border-violet-500/25  text-violet-400',
        orange:    'bg-orange-500/15  border-orange-500/25  text-orange-400',
        sky:       'bg-sky-500/15     border-sky-500/25     text-sky-400',
      },
      size: {
        sm: 'px-2   py-0.5 text-[11px]',
        md: 'px-2.5 py-1   text-xs',
      },
    },
    defaultVariants: { variant: 'default', size: 'sm' },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  dot?: boolean
}

export function Badge({ className, variant, size, dot, children, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant, size }), className)} {...props}>
      {dot && <span className="w-1.5 h-1.5 rounded-full bg-current" />}
      {children}
    </span>
  )
}