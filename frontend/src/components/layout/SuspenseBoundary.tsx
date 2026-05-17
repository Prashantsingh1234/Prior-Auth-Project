import { Suspense, type ReactNode } from 'react'
import { PageSkeleton, CardSkeleton } from '@/components/ui/Skeleton'

type Variant = 'page' | 'card' | 'table' | 'minimal'

interface Props {
  children:  ReactNode
  fallback?: ReactNode
  variant?:  Variant
}

function TableSkeleton() {
  return (
    <div className="space-y-px p-4">
      <div className="h-10 rounded-lg bg-[var(--elevated)] animate-pulse mb-2" />
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="h-12 rounded bg-[var(--elevated)]/60 animate-pulse" />
      ))}
    </div>
  )
}

function MinimalSkeleton() {
  return <div className="h-8 w-24 rounded-lg bg-[var(--elevated)] animate-pulse" />
}

const FALLBACKS: Record<Variant, ReactNode> = {
  page:    <PageSkeleton />,
  card:    <CardSkeleton />,
  table:   <TableSkeleton />,
  minimal: <MinimalSkeleton />,
}

export function SuspenseBoundary({ children, fallback, variant = 'page' }: Props) {
  return (
    <Suspense fallback={fallback ?? FALLBACKS[variant]}>
      {children}
    </Suspense>
  )
}
