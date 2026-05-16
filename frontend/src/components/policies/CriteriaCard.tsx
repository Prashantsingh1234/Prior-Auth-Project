import { CheckCircle2, XCircle, AlertCircle, BookOpen } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ConfidenceBar } from '@/components/common/ConfidenceBar'
import type { PolicyCriterion } from '@/types'

const CFG = {
  MET:           { icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/5  border-emerald-500/15', label: 'Met' },
  NOT_MET:       { icon: XCircle,      color: 'text-red-400',     bg: 'bg-red-500/5      border-red-500/15',     label: 'Not Met' },
  INSUFFICIENT:  { icon: AlertCircle,  color: 'text-amber-400',   bg: 'bg-amber-500/5    border-amber-500/15',   label: 'Insufficient' },
  NOT_APPLICABLE:{ icon: AlertCircle,  color: 'text-slate-400',   bg: 'bg-slate-500/5    border-slate-500/15',   label: 'N/A' },
}

export function CriteriaCard({ criterion }: { criterion: PolicyCriterion }) {
  const { icon: Icon, color, bg, label } = CFG[criterion.status]
  return (
    <div className={cn('rounded-xl border p-4', bg)}>
      <div className="flex items-start gap-3">
        <Icon className={cn('w-4.5 h-4.5 mt-0.5 flex-shrink-0', color)} />
        <div className="flex-1">
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-medium text-[var(--text-1)] leading-snug">{criterion.criterion}</p>
            <span className={cn('text-xs font-semibold flex-shrink-0', color)}>{label}</span>
          </div>
          <p className="text-xs text-[var(--text-2)] mt-2 leading-relaxed">{criterion.evidence}</p>
          <div className="flex items-center justify-between mt-3">
            <div className="flex items-center gap-1.5 text-xs text-[var(--text-3)]">
              <BookOpen className="w-3 h-3" />
              {criterion.policyRef}
            </div>
            <div className="w-24">
              <ConfidenceBar value={criterion.confidence} size="sm" showPercent />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}