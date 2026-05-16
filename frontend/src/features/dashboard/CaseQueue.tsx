import { useNavigate } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import { ChevronRight, AlertCircle, Clock, FileText } from 'lucide-react'
import { clsx } from 'clsx'
import type { CaseListItem } from '@/api/types'
import { StatusBadge, PriorityBadge, RecommendationBadge } from '@/components/common/StatusBadge'
import { ConfidenceBar } from '@/components/common/ConfidenceBar'

interface CaseQueueProps {
  cases: CaseListItem[]
  isLoading?: boolean
}

export function CaseQueue({ cases, isLoading }: CaseQueueProps) {
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />
        ))}
      </div>
    )
  }

  if (cases.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <FileText className="w-12 h-12 text-slate-300 mb-3" />
        <p className="text-slate-500 font-medium">No cases in queue</p>
        <p className="text-slate-400 text-sm mt-1">New cases will appear here automatically</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {cases.map((c) => (
        <CaseQueueItem key={c.case_id} caseItem={c} onClick={() => navigate(`/review/${c.case_id}`)} />
      ))}
    </div>
  )
}

interface CaseQueueItemProps {
  caseItem: CaseListItem
  onClick: () => void
}

export function CaseQueueItem({ caseItem: c, onClick }: CaseQueueItemProps) {
  const isUrgent = c.priority === 'URGENT' || c.priority === 'EMERGENT'

  return (
    <button
      onClick={onClick}
      className={clsx(
        'w-full text-left bg-white rounded-xl border p-4 hover:shadow-panel-md hover:border-brand-300 transition-all duration-150 group',
        isUrgent ? 'border-l-4 border-l-orange-400 border-t-slate-200 border-r-slate-200 border-b-slate-200' : 'border-slate-200',
      )}
    >
      <div className="flex items-start gap-3">
        {/* Priority icon */}
        <div
          className={clsx(
            'mt-0.5 w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
            c.priority === 'EMERGENT' ? 'bg-red-50' : c.priority === 'URGENT' ? 'bg-orange-50' : 'bg-slate-50',
          )}
        >
          {isUrgent ? (
            <AlertCircle className={clsx('w-4 h-4', c.priority === 'EMERGENT' ? 'text-red-500' : 'text-orange-500')} />
          ) : (
            <FileText className="w-4 h-4 text-slate-400" />
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-sm font-semibold text-slate-900 font-mono">{c.case_number}</span>
            <StatusBadge status={c.status} size="sm" />
            <PriorityBadge priority={c.priority} />
            {c.ai_recommendation && <RecommendationBadge recommendation={c.ai_recommendation} />}
          </div>

          <p className="text-sm text-slate-700 truncate">
            <span className="font-medium">{c.patient_name}</span>
            <span className="text-slate-400 mx-1.5">·</span>
            <span className="text-slate-500">{c.service_type.replace(/_/g, ' ')}</span>
          </p>
          <p className="text-xs text-slate-400 mt-0.5 truncate">{c.provider_name}</p>

          <div className="flex items-center gap-4 mt-2">
            {c.ai_confidence_score != null && (
              <ConfidenceBar
                score={c.ai_confidence_score}
                size="sm"
                className="w-32"
              />
            )}
            {c.clarification_count > 0 && (
              <span className="text-xs text-amber-600 font-medium">
                {c.clarification_count} clarification{c.clarification_count > 1 ? 's' : ''}
              </span>
            )}
            <span className="flex items-center gap-1 text-xs text-slate-400 ml-auto">
              <Clock className="w-3 h-3" />
              {formatDistanceToNow(new Date(c.submitted_at), { addSuffix: true })}
            </span>
          </div>
        </div>

        <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-brand-500 transition-colors flex-shrink-0 mt-2" />
      </div>
    </button>
  )
}
