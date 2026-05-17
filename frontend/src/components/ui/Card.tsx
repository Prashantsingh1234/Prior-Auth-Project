import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hover?:  boolean
  padded?: boolean
}

export function Card({ className, hover, padded = true, children, onClick, style, id }: CardProps) {
  const base = cn(
    'rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-card',
    padded && 'p-5',
    hover  && 'cursor-pointer',
    className,
  )

  return (
    <motion.div
      className={base}
      whileHover={hover ? { y: -2, boxShadow: '0 8px 30px rgba(0,0,0,0.12)' } : undefined}
      transition={{ duration: 0.18, ease: [0.4, 0, 0.2, 1] }}
      onClick={onClick}
      style={style}
      id={id}
    >
      {children}
    </motion.div>
  )
}

export function CardHeader({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('flex items-center justify-between pb-4 mb-4 border-b border-[var(--border)]', className)} {...props}>
      {children}
    </div>
  )
}

export function CardTitle({ className, children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn('text-sm font-semibold text-[var(--text-1)]', className)} {...props}>
      {children}
    </p>
  )
}

export function CardDescription({ className, children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn('text-xs text-[var(--text-3)] mt-0.5', className)} {...props}>
      {children}
    </p>
  )
}
