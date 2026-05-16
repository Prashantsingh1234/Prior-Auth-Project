import { useState } from 'react'
import { clsx } from 'clsx'
import { CheckCircle2, XCircle, AlertCircle, MinusCircle, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react'
import type { PolicyCriterion, CriterionStatus, PolicyChunk } from '@/api/types'
import { useReviewStore } from '@/store/reviewStore'

interface PolicyCriteriaPanelProps {
  criteria: PolicyCriterion[]
}

const STATUS_CONFIG: Record<CriterionStatus, {
  icon: React.ReactNode
  label: string
  color: string
  bg: string
  border: string
}> = {
  PASS: {
    icon: <CheckCircle2 className="w-4 h-4" />,
    label: 'Met',
    color: 'text-green-600',
    bg: 'bg-green-50',
    border: 'border-green-200',
  },
  FAIL: {
    icon: <XCircle className="w-4 h-4" />,
    label: 'Not Met',
    color: 'text-red-600',
    bg: 'bg-red-50',
    border: 'border-red-200',
  },
  INSUFFICIENT_EVIDENCE: {
    icon: <AlertCircle className="w-4 h-4" />,
    label: 'Insufficient Evidence',
    color: 'text-amber-600',
    bg: 'bg-amber-50',
    border: 'border-amber-200',
  },
  NOT_APPLICABLE: {
    icon: <MinusCircle className="w-4 h-4" />,
    label: 'N/A',
    color: 'text-slate-500',
    bg: 'bg-slate-50',
    border: 'border-slate-200',
  },
}

export function PolicyCriteriaPanel({ criteria }: PolicyCriteriaPanelProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())
  const { setHighlightedChunk, highlightedChunkId } = useReviewStore()

  const toggle = (id: string) =>
    setExpandedIds((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const passCount   = criteria.filter((c) => c.status === 'PASS').length
  const failCount   = criteria.filter((c) => c.status === 'FAIL').length
  const insuffCount = criteria.filter((c) => c.status === 'INSUFFICIENT_EVIDENCE').length

  if (criteria.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-slate-400 text-sm">
        No policy criteria available
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Summary bar */}
      <div className="flex gap-2 flex-wrap">
        <Pill icon={<CheckCircle2 className="w-3.5 h-3.5 text-green-600" />} label={`${passCount} Met`} color="text-green-700 bg-green-50 border-green-200" />
        <Pill icon={<XCircle className="w-3.5 h-3.5 text-red-600" />} label={`${failCount} Not Met`} color="text-red-700 bg-red-50 border-red-200" />
        <Pill icon={<AlertCircle className="w-3.5 h-3.5 text-amber-600" />} label={`${insuffCount} Insufficient`} color="text-amber-700 bg-amber-50 border-amber-200" />
      </div>

      <div className="flex-1 overflow-y-auto space-y-2 pr-0.5">
        {criteria.map((criterion, idx) => {
          const config = STATUS_CONFIG[criterion.status]
          const isOpen = expandedIds.has(criterion.criterion_id)

          return (
            <div
              key={criterion.criterion_id}
              className={clsx('rounded-lg border transition-all duration-150', config.border, config.bg)}
            >
              <button
                onClick={() => toggle(criterion.criterion_id)}
                className="w-full flex items-start gap-2.5 p-3 text-left"
              >
                <span className={clsx('mt-0.5 flex-shrink-0', config.color)}>{config.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs text-slate-400 font-mono">#{idx + 1}</span>
                    <span className={clsx('text-xs font-semibold px-1.5 py-0.5 rounded bg-white/60', config.color)}>
                      {config.label}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-slate-800 leading-snug">{criterion.criterion_name}</p>
                  {criterion.description && (
                    <p className="text-xs text-slate-500 mt-0.5 leading-snug">{criterion.description}</p>
                  )}
                </div>
                <span className="flex-shrink-0 text-slate-400 mt-0.5">
                  {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </span>
              </button>

              {isOpen && (
                <div className="px-3 pb-3 space-y-2.5 border-t border-white/60 pt-2.5">
                  {criterion.evidence && (
                    <div>
                      <p className="text-xs font-semibold text-slate-500 mb-1">Evidence from Record</p>
                      <blockquote className="text-xs text-slate-600 bg-white/70 border-l-2 border-current pl-2.5 py-1 rounded-r italic leading-relaxed">
                        "{criterion.evidence}"
                      </blockquote>
                    </div>
                  )}

                  {criterion.source_chunks.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-slate-500 mb-1">Policy References</p>
                      <div className="space-y-1">
                        {criterion.source_chunks.map((chunk) => (
                          <PolicyChunkCard
                            key={chunk.chunk_id}
                            chunk={chunk}
                            isActive={highlightedChunkId === chunk.chunk_id}
                            onToggle={() => setHighlightedChunk(
                              highlightedChunkId === chunk.chunk_id ? null : chunk.chunk_id,
                            )}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {criterion.policy_reference && (
                    <div className="flex items-center gap-1.5 text-xs text-brand-600">
                      <ExternalLink className="w-3 h-3" />
                      <span>{criterion.policy_reference}</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function PolicyChunkCard({
  chunk, isActive, onToggle,
}: { chunk: PolicyChunk; isActive: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      className={clsx(
        'w-full text-left text-xs p-2 rounded border transition-colors',
        isActive
          ? 'bg-brand-50 border-brand-300 text-brand-700'
          : 'bg-white/60 border-slate-200 text-slate-600 hover:border-brand-300',
      )}
    >
      <div className="flex items-center justify-between mb-0.5">
        <span className="font-medium">{chunk.source}</span>
        <span className="text-slate-400">{Math.round(chunk.relevance_score * 100)}% relevance</span>
      </div>
      <p className="text-slate-500 line-clamp-2">{chunk.text}</p>
    </button>
  )
}

function Pill({ icon, label, color }: { icon: React.ReactNode; label: string; color: string }) {
  return (
    <div className={clsx('flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-semibold', color)}>
      {icon}
      {label}
    </div>
  )
}
