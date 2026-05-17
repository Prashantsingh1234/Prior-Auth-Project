import type { ElementType, ReactNode } from 'react'

interface VisuallyHiddenProps {
  children: ReactNode
  as?: ElementType
  [key: string]: unknown
}

export function VisuallyHidden({ children, as: Component = 'span', ...props }: VisuallyHiddenProps) {
  return (
    <Component className="sr-only" {...props}>
      {children}
    </Component>
  )
}
