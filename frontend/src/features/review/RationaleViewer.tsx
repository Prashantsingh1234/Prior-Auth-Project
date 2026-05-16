import { clsx } from 'clsx'
import { Brain, BookOpen, ChevronDown, ChevronUp, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import type { DecisionOutcome, PolicyCriterion } from '@/api/types'
import { ConfidenceBar, ConfidenceRing } from '@/components/common/ConfidenceBar'
import { RecommendationBadge } from '@/components/common/StatusBadge'

interface RationaleViewerProps {
  aiRecommendation: DecisionOutcome | null
  aiConfidenceScore: number | null
  aiRationale: string | null
  policyCriteria: PolicyCriterion[]
  isLoading?: boolean
}

export function RationaleViewer({
  aiRecommendation,
  aiConfidenceScore,
  aiRationale,
  policyCriteria,
  isLoading,
}: RationaleViewerProps) {
  const [showSources, setShowSources] = useState(true)

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => <div key={i} className="h-12 bg-slate-100 rounded-xl animate-pulse" />)}
      </div>
    )
  }

  if (!aiRecommendation && !aiRationale) {
    return (
      <div className="flex flex-col items-center justify-center h-32 gap-2 text-slate-400">
        <Brain className="w-7 h-7 opacity-40" />
        <span className="text-sm">AI analysis pending</span>
      </div>
    )
  }

  const allChunks = policyCriteria.flatMap((c) => c.source_chunks)
  const uniqueChunks = allChunks.filter(
    (chunk, idx) => allChunks.findIndex((c) => c.chunk_id === chunk.chunk_id) === idx,
  )

  return (
    <div className="flex flex-col gap-4 h-full overflow-y-auto pr-0.5">
      {/* AI recommendation header */}
      {(aiRecommendation || aiConfidenceScore != null) && (
        <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200">
          {aiConfidenceScore != null && (
            <ConfidenceRing score={aiConfidenceScore} size={52} />
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-semibold text-slate-500">AI Recommendation</span>
              {aiRecommendation && <RecommendationBadge recommendation={aiRecommendation} />}
            </div>
            {aiConfidenceScore != null && (
              <ConfidenceBar score={aiConfidenceScore} size="sm" />
            )}
          </div>
        </div>
      )}

      {/* Criteria summary */}
      {policyCriteria.length > 0 && (
        <div className="flex items-center gap-2 p-2.5 bg-white border border-slate-200 rounded-xl">
          <ShieldCheck className="w-4 h-4 text-brand-500 flex-shrink-0" />
          <div className="flex gap-3 text-xs flex-wrap">
            <span className="text-green-700 font-semibold">
              {policyCriteria.filter((c) => c.status === 'PASS').length} criteria met
            </span>
            <span className="text-red-700 font-semibold">
              {policyCriteria.filter((c) => c.status === 'FAIL').length} not met
            </span>
            <span className="text-amber-700 font-semibold">
              {policyCriteria.filter((c) => c.status === 'INSUFFICIENT_EVIDENCE').length} insufficient
            </span>
          </div>
        </div>
      )}

      {/* Main rationale text */}
      {aiRationale && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Brain className="w-4 h-4 text-brand-500" />
            <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wide">AI Rationale</h4>
          </div>
          <div className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap bg-white border border-slate-100 rounded-xl p-3">
            {aiRationale}
          </div>
        </div>
      )}

      {/* Policy sources */}
      {uniqueChunks.length > 0 && (
        <div>
          <button
            onClick={() => setShowSources((v) => !v)}
            className="flex items-center gap-2 w-full mb-2 text-left group"
          >
            <BookOpen className="w-4 h-4 text-slate-400 group-hover:text-brand-500 transition-colors" />
            <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wide flex-1">
              Policy Sources ({uniqueChunks.length})
            </h4>
            {showSources
              ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" />
              : <ChevronDown className="w-3.5 h-3.5 text-slate-400" />}
          </button>
          {showSources && (
            <div className="space-y-2">
              {uniqueChunks.map((chunk) => (
                <div key={chunk.chunk_id} className="bg-white border border-slate-200 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-semibold text-brand-700">{chunk.source}</span>
                    <span className={clsx(
                      'text-xs font-medium px-1.5 py-0.5 rounded',
                      chunk.relevance_score >= 0.85 ? 'text-green-700 bg-green-50' :
                      chunk.relevance_score >= 0.65 ? 'text-amber-700 bg-amber-50' :
                      'text-slate-600 bg-slate-50',
                    )}>
                      {Math.round(chunk.relevance_score * 100)}% relevance
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed line-clamp-3">{chunk.text}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
