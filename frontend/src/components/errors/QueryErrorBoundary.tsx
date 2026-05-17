import { Suspense } from 'react'
import { ErrorBoundary } from './ErrorBoundary'
import { APIErrorFallback } from './APIErrorFallback'
import { PageSkeleton, CardSkeleton } from '@/components/ui/Skeleton'

type Variant = 'page' | 'card' | 'inline'

interface QueryErrorBoundaryProps {
  children:   React.ReactNode
  variant?:   Variant
  title?:     string
  className?: string
}

const SKELETONS: Record<Variant, React.ReactNode> = {
  page:   <PageSkeleton />,
  card:   <CardSkeleton />,
  inline: <div className="h-8 shimmer animate-pulse rounded-md bg-[var(--elevated)]" />,
}

export function QueryErrorBoundary({
  children,
  variant = 'page',
  title,
  className,
}: QueryErrorBoundaryProps) {
  return (
    <ErrorBoundary
      fallback={(error, reset) => (
        <APIErrorFallback
          error={error}
          reset={reset}
          title={title}
          compact={variant === 'inline'}
          className={className}
        />
      )}
    >
      <Suspense fallback={SKELETONS[variant]}>
        {children}
      </Suspense>
    </ErrorBoundary>
  )
}
