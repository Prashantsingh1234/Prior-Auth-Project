import { useState, useMemo } from 'react'
import { clsx } from 'clsx'
import { Search, ChevronDown, ChevronUp, Eye } from 'lucide-react'
import type { ExtractedEntity } from '@/api/types'
import { useReviewStore } from '@/store/reviewStore'
import { ConfidenceBar } from '@/components/common/ConfidenceBar'

interface ExtractedEntitiesPanelProps {
  entities: ExtractedEntity[]
}

const ENTITY_LABELS: Record<string, string> = {
  PATIENT_DEMOGRAPHICS: 'Patient Demographics',
  DIAGNOSIS_CODE:       'Diagnosis Code',
  PROCEDURE_CODE:       'Procedure Code',
  MEDICATION:           'Medication',
  LAB_VALUE:            'Lab Value',
  COMPLICATION:         'Complication',
  OTHER:                'Other',
}

export function ExtractedEntitiesPanel({ entities }: ExtractedEntitiesPanelProps) {
  const [search, setSearch]       = useState('')
  const [activeType, setActive]   = useState<string>('All')
  const [showLowConf, setShowLow] = useState(true)

  const {
    highlightedEntityId,
    setHighlightedEntity,
    expandedEntityIds,
    toggleEntityExpanded,
  } = useReviewStore()

  const entityTypes = ['All', ...Array.from(new Set(entities.map((e) => e.entity_type)))]

  const filtered = useMemo(() => {
    let list = entities
    if (!showLowConf) list = list.filter((e) => e.confidence >= 0.65)
    if (activeType !== 'All') list = list.filter((e) => e.entity_type === activeType)
    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter(
        (e) => e.value.toLowerCase().includes(q) ||
               ENTITY_LABELS[e.entity_type]?.toLowerCase().includes(q),
      )
    }
    return list
  }, [entities, search, activeType, showLowConf])

  const handleHighlight = (entityId: string) => {
    setHighlightedEntity(highlightedEntityId === entityId ? null : entityId)
  }

  if (entities.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-32 text-slate-400 text-sm gap-2">
        <Search className="w-6 h-6 opacity-40" />
        No extracted entities
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2 h-full">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search entities…"
          className="w-full pl-8 pr-3 py-1.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-400 bg-white"
        />
      </div>

      {/* Type filter */}
      <div className="flex gap-1 flex-wrap">
        {entityTypes.map((type) => (
          <button
            key={type}
            onClick={() => setActive(type)}
            className={clsx(
              'px-2 py-0.5 text-xs rounded-full border transition-colors',
              activeType === type
                ? 'bg-brand-600 text-white border-brand-600'
                : 'text-slate-500 border-slate-200 hover:border-brand-400 hover:text-brand-600',
            )}
          >
            {ENTITY_LABELS[type] ?? type}
          </button>
        ))}
        <button
          onClick={() => setShowLow((v) => !v)}
          className={clsx(
            'ml-auto px-2 py-0.5 text-xs rounded-full border transition-colors flex items-center gap-1',
            !showLowConf ? 'bg-red-50 text-red-600 border-red-200' : 'text-slate-400 border-slate-200',
          )}
        >
          <Eye className="w-3 h-3" />
          Low conf
        </button>
      </div>

      <p className="text-xs text-slate-400">{filtered.length} of {entities.length} entities</p>

      {/* Entity list */}
      <div className="flex-1 overflow-y-auto space-y-1.5 pr-0.5">
        {filtered.map((entity) => {
          const isHighlighted = entity.entity_id === highlightedEntityId
          const isExpanded    = expandedEntityIds.has(entity.entity_id)
          const hasLocation   = entity.bounding_box != null

          return (
            <div
              key={entity.entity_id}
              className={clsx(
                'rounded-lg border transition-all duration-150',
                isHighlighted
                  ? 'border-yellow-400 bg-yellow-50 shadow-sm'
                  : 'border-slate-200 bg-white hover:border-slate-300',
              )}
            >
              <div className="flex items-start gap-2 p-2.5">
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-0.5">
                    {ENTITY_LABELS[entity.entity_type] ?? entity.entity_type.replace(/_/g, ' ')}
                  </p>
                  <p className={clsx(
                    'text-sm font-medium',
                    isHighlighted ? 'text-yellow-800' : 'text-slate-900',
                    !isExpanded && 'truncate',
                  )}>
                    {entity.normalized_value ?? entity.value}
                  </p>
                  {entity.normalized_value && entity.normalized_value !== entity.value && (
                    <p className="text-xs text-slate-400 mt-0.5 truncate">Raw: {entity.value}</p>
                  )}
                  <div className="mt-1.5">
                    <ConfidenceBar score={entity.confidence} size="sm" showLabel={false} />
                  </div>
                </div>

                <div className="flex flex-col gap-1 items-end flex-shrink-0">
                  {hasLocation && (
                    <button
                      onClick={() => handleHighlight(entity.entity_id)}
                      title={isHighlighted ? 'Remove highlight' : 'Jump to in document'}
                      className={clsx(
                        'p-1 rounded transition-colors',
                        isHighlighted ? 'text-yellow-600 hover:text-yellow-800' : 'text-slate-300 hover:text-brand-500',
                      )}
                    >
                      <Eye className="w-3.5 h-3.5" />
                    </button>
                  )}
                  {entity.value.length > 30 && (
                    <button
                      onClick={() => toggleEntityExpanded(entity.entity_id)}
                      className="p-1 rounded text-slate-300 hover:text-slate-600 transition-colors"
                    >
                      {isExpanded
                        ? <ChevronUp className="w-3.5 h-3.5" />
                        : <ChevronDown className="w-3.5 h-3.5" />}
                    </button>
                  )}
                </div>
              </div>

              {isExpanded && (
                <div className="px-2.5 pb-2.5 text-xs text-slate-400 border-t border-slate-100 pt-1.5">
                  {entity.bounding_box && <span>Page {entity.bounding_box.page} · </span>}
                  Confidence {Math.round(entity.confidence * 100)}%
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
