import { Suspense, type ReactNode } from 'react'
import { PageSkeleton } from '@/components/ui/Skeleton'

interface Props {
  children:  ReactNode
  fallback?: ReactNode
}

export function SuspenseBoundary({ children, fallback }: Props) {
  return (
    <Suspense fallback={fallback ?? <PageSkeleton />}>
      {children}
    </Suspense>
  )
}