import { useCaseQueue } from '@/hooks/useCase'
import { useAuthStore } from '@/store/authStore'
import { CaseQueue } from './CaseQueue'
import { ConfidenceRing } from '@/components/common/ConfidenceBar'
import { CheckCircle, XCircle, Clock, AlertTriangle, RefreshCw } from 'lucide-react'

export function ReviewerDashboard() {
  const user = useAuthStore((s) => s.user)
  const { data, isLoading, isFetching, refetch } = useCaseQueue()

  const cases = data?.cases ?? []
  const meta  = data?.meta

  // Derived stats from the queue
  const stats = {
    total:     meta?.total_items ?? 0,
    urgent:    cases.filter((c) => c.priority === 'URGENT' || c.priority === 'EMERGENT').length,
    pending:   cases.filter((c) => c.status === 'PENDING_CLARIFICATION').length,
    underReview: cases.filter((c) => c.status === 'UNDER_REVIEW').length,
    avgConfidence: cases.length > 0
      ? cases.reduce((s, c) => s + (c.ai_confidence_score ?? 0), 0) / cases.filter((c) => c.ai_confidence_score != null).length
      : null,
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">
            Good {getGreeting()}, {user?.username}
          </h2>
          <p className="text-slate-500 mt-0.5">
            {stats.total} case{stats.total !== 1 ? 's' : ''} in your review queue
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:text-brand-700 hover:bg-brand-50 rounded-lg transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <StatCard
          icon={<Clock className="w-5 h-5 text-violet-600" />}
          bg="bg-violet-50"
          label="Under Review"
          value={stats.underReview}
        />
        <StatCard
          icon={<AlertTriangle className="w-5 h-5 text-orange-600" />}
          bg="bg-orange-50"
          label="Urgent / Emergent"
          value={stats.urgent}
        />
        <StatCard
          icon={<XCircle className="w-5 h-5 text-amber-600" />}
          bg="bg-amber-50"
          label="Pending Clarification"
          value={stats.pending}
        />
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex items-center gap-3">
          <div className="bg-blue-50 rounded-lg p-2">
            {stats.avgConfidence != null ? (
              <ConfidenceRing score={stats.avgConfidence} size={40} />
            ) : (
              <CheckCircle className="w-5 h-5 text-blue-600" />
            )}
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">
              {stats.avgConfidence != null ? `${Math.round(stats.avgConfidence * 100)}%` : '—'}
            </p>
            <p className="text-xs text-slate-500">Avg AI Confidence</p>
          </div>
        </div>
      </div>

      {/* Queue */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-panel overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">Review Queue</h3>
          {isFetching && (
            <span className="text-xs text-slate-400 flex items-center gap-1">
              <RefreshCw className="w-3 h-3 animate-spin" />
              Updating
            </span>
          )}
        </div>
        <div className="p-4">
          <CaseQueue cases={cases} isLoading={isLoading} />
        </div>
        {meta && meta.total_pages > 1 && (
          <div className="px-5 py-3 border-t border-slate-100 text-xs text-slate-400 text-center">
            Showing page {meta.page} of {meta.total_pages} · {meta.total_items} total cases
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({
  icon, bg, label, value,
}: {
  icon: React.ReactNode
  bg: string
  label: string
  value: number
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 flex items-center gap-3">
      <div className={`${bg} rounded-lg p-2 flex-shrink-0`}>{icon}</div>
      <div>
        <p className="text-2xl font-bold text-slate-900">{value}</p>
        <p className="text-xs text-slate-500">{label}</p>
      </div>
    </div>
  )
}

function getGreeting(): string {
  const h = new Date().getHours()
  if (h < 12) return 'morning'
  if (h < 17) return 'afternoon'
  return 'evening'
}
