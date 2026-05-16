import { type ElementType, type HTMLAttributes, forwardRef } from 'react'
import { cn } from '@/lib/utils'

type PolymorphicProps<E extends ElementType> = {
  as?: E
  className?: string
  children?: React.ReactNode
} & Omit<HTMLAttributes<HTMLElement>, 'as'>

// ─── Display ─────────────────────────────────────────────────────────────────
export const Display = forwardRef<HTMLHeadingElement, PolymorphicProps<'h1'>>(
  ({ as: Tag = 'h1', className, children, ...props }, ref) => (
    <Tag ref={ref} className={cn('type-display', className)} {...props}>
      {children}
    </Tag>
  )
)
Display.displayName = 'Display'

// ─── Headings ────────────────────────────────────────────────────────────────
export const H1 = forwardRef<HTMLHeadingElement, PolymorphicProps<'h1'>>(
  ({ as: Tag = 'h1', className, children, ...props }, ref) => (
    <Tag ref={ref} className={cn('type-h1', className)} {...props}>{children}</Tag>
  )
)
H1.displayName = 'H1'

export const H2 = forwardRef<HTMLHeadingElement, PolymorphicProps<'h2'>>(
  ({ as: Tag = 'h2', className, children, ...props }, ref) => (
    <Tag ref={ref} className={cn('type-h2', className)} {...props}>{children}</Tag>
  )
)
H2.displayName = 'H2'

export const H3 = forwardRef<HTMLHeadingElement, PolymorphicProps<'h3'>>(
  ({ as: Tag = 'h3', className, children, ...props }, ref) => (
    <Tag ref={ref} className={cn('type-h3', className)} {...props}>{children}</Tag>
  )
)
H3.displayName = 'H3'

export const H4 = forwardRef<HTMLHeadingElement, PolymorphicProps<'h4'>>(
  ({ as: Tag = 'h4', className, children, ...props }, ref) => (
    <Tag ref={ref} className={cn('type-h4', className)} {...props}>{children}</Tag>
  )
)
H4.displayName = 'H4'

// ─── Metric ──────────────────────────────────────────────────────────────────
interface MetricProps extends HTMLAttributes<HTMLSpanElement> {
  value: string | number
  label?: string
  size?: 'default' | 'sm'
}

export function Metric({ value, label, size = 'default', className, ...props }: MetricProps) {
  return (
    <div className={cn('flex flex-col gap-0.5', className)} {...props}>
      <span className={cn(size === 'sm' ? 'type-metric-sm' : 'type-metric')}>
        {value}
      </span>
      {label && (
        <span className="type-label text-[var(--text-3)]">{label}</span>
      )}
    </div>
  )
}

// ─── Body text ───────────────────────────────────────────────────────────────
export const Body = forwardRef<HTMLParagraphElement, PolymorphicProps<'p'>>(
  ({ as: Tag = 'p', className, children, ...props }, ref) => (
    <Tag ref={ref} className={cn('type-body', className)} {...props}>{children}</Tag>
  )
)
Body.displayName = 'Body'

export const BodySm = forwardRef<HTMLParagraphElement, PolymorphicProps<'p'>>(
  ({ as: Tag = 'p', className, children, ...props }, ref) => (
    <Tag ref={ref} className={cn('type-body-sm', className)} {...props}>{children}</Tag>
  )
)
BodySm.displayName = 'BodySm'

// ─── AI reasoning text ───────────────────────────────────────────────────────
export const AIReasoning = forwardRef<HTMLParagraphElement, PolymorphicProps<'p'>>(
  ({ as: Tag = 'p', className, children, ...props }, ref) => (
    <Tag ref={ref} className={cn('type-ai-reasoning', className)} {...props}>{children}</Tag>
  )
)
AIReasoning.displayName = 'AIReasoning'

// ─── Medical evidence text ────────────────────────────────────────────────────
export const Evidence = forwardRef<HTMLElement, PolymorphicProps<'blockquote'>>(
  ({ as: Tag = 'blockquote', className, children, ...props }, ref) => (
    <Tag ref={ref} className={cn('type-evidence', className)} {...props}>{children}</Tag>
  )
)
Evidence.displayName = 'Evidence'

// ─── Reviewer comment text ────────────────────────────────────────────────────
export const Comment = forwardRef<HTMLParagraphElement, PolymorphicProps<'p'>>(
  ({ as: Tag = 'p', className, children, ...props }, ref) => (
    <Tag ref={ref} className={cn('type-comment', className)} {...props}>{children}</Tag>
  )
)
Comment.displayName = 'Comment'

// ─── Audit log entry ─────────────────────────────────────────────────────────
export const AuditLog = forwardRef<HTMLElement, PolymorphicProps<'code'>>(
  ({ as: Tag = 'code', className, children, ...props }, ref) => (
    <Tag ref={ref} className={cn('type-audit', className)} {...props}>{children}</Tag>
  )
)
AuditLog.displayName = 'AuditLog'

// ─── Label ───────────────────────────────────────────────────────────────────
export const Label = forwardRef<HTMLSpanElement, PolymorphicProps<'span'>>(
  ({ as: Tag = 'span', className, children, ...props }, ref) => (
    <Tag ref={ref} className={cn('type-label', className)} {...props}>{children}</Tag>
  )
)
Label.displayName = 'Label'

// ─── Caption ─────────────────────────────────────────────────────────────────
export const Caption = forwardRef<HTMLSpanElement, PolymorphicProps<'span'>>(
  ({ as: Tag = 'span', className, children, ...props }, ref) => (
    <Tag ref={ref} className={cn('type-caption', className)} {...props}>{children}</Tag>
  )
)
Caption.displayName = 'Caption'

// ─── Section label (uppercase overline) ──────────────────────────────────────
export const SectionLabel = forwardRef<HTMLSpanElement, PolymorphicProps<'span'>>(
  ({ as: Tag = 'span', className, children, ...props }, ref) => (
    <Tag
      ref={ref}
      className={cn('section-label', className)}
      {...props}
    >
      {children}
    </Tag>
  )
)
SectionLabel.displayName = 'SectionLabel'

// ─── Code / monospace ────────────────────────────────────────────────────────
export const Code = forwardRef<HTMLElement, PolymorphicProps<'code'>>(
  ({ as: Tag = 'code', className, children, ...props }, ref) => (
    <Tag ref={ref} className={cn('type-code', className)} {...props}>{children}</Tag>
  )
)
Code.displayName = 'Code'

// ─── Prose container ──────────────────────────────────────────────────────────
interface ProseProps extends HTMLAttributes<HTMLDivElement> {
  size?: 'sm' | 'base' | 'lg'
}

export function Prose({ size = 'base', className, children, ...props }: ProseProps) {
  return (
    <div
      className={cn(
        'leading-relaxed text-[var(--text-2)]',
        size === 'sm' && 'text-sm',
        size === 'base' && 'text-base',
        size === 'lg' && 'text-lg',
        '[&>p+p]:mt-3 [&>ul]:mt-2 [&>ul]:list-disc [&>ul]:pl-5 [&>ol]:mt-2 [&>ol]:list-decimal [&>ol]:pl-5',
        '[&>li]:mt-1 [&>strong]:text-[var(--text-1)] [&>strong]:font-semibold',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}
