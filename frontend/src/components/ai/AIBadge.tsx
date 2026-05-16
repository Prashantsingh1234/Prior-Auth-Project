import { Brain } from 'lucide-react'
import { cn } from '@/lib/utils'

interface AIBadgeProps {
  modelId:  string
  tier:     'SMALL' | 'MEDIUM' | 'LARGE'
  className?: string
}

const TIER_COLOR = { SMALL: 'text-slate-400', MEDIUM: 'text-amber-400', LARGE: 'text-violet-400' }
const TIER_BG    = { SMALL: 'bg-slate-500/10', MEDIUM: 'bg-amber-500/10', LARGE: 'bg-violet-500/10' }

export function AIBadge({ modelId, tier, className }: AIBadgeProps) {
  return (
    <div className={cn('inline-flex items-center gap-1.5 px-2 py-1 rounded-full border border-[var(--border)]', TIER_BG[tier], className)}>
      <Brain className={cn('w-3 h-3', TIER_COLOR[tier])} />
      <span className={cn('text-xs font-medium', TIER_COLOR[tier])}>{modelId}</span>
    </div>
  )
}