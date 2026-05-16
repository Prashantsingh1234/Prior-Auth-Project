import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SpinnerProps { size?: 'sm' | 'md' | 'lg'; className?: string }
const SIZE = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-8 h-8' }

export function Spinner({ size = 'md', className }: SpinnerProps) {
  return <Loader2 className={cn('animate-spin text-brand-400', SIZE[size], className)} />
}

export function FullPageSpinner() {
  return (
    <div className="flex items-center justify-center h-full min-h-64">
      <Spinner size="lg" />
    </div>
  )
}