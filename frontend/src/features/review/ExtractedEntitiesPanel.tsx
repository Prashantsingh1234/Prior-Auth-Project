import { motion } from 'framer-motion'
import { User, Building2, Pill, Stethoscope, Calendar, Hash } from 'lucide-react'
import { ConfidenceBar } from '@/components/common/ConfidenceBar'
import { cn } from '@/lib/utils'

interface Entity {
  id: string
  type: string
  value: string
  context: string
  confidence: number
  source: string
}

const ENTITY_ICONS: Record<string, React.ElementType> = {
  PATIENT:    User,
  PROVIDER:   Building2,
  MEDICATION: Pill,
  DIAGNOSIS:  Stethoscope,
  DATE:       Calendar,
  CPT_CODE:   Hash,
  ICD_CODE:   Hash,
}

const ENTITY_COLOR: Record<string, string> = {
  PATIENT:    'bg-sky-500/10 border-sky-500/25 text-sky-400',
  PROVIDER:   'bg-violet-500/10 border-violet-500/25 text-violet-400',
  MEDICATION: 'bg-amber-500/10 border-amber-500/25 text-amber-400',
  DIAGNOSIS:  'bg-red-500/10 border-red-500/25 text-red-400',
  DATE:       'bg-slate-500/10 border-slate-500/25 text-slate-400',
  CPT_CODE:   'bg-emerald-500/10 border-emerald-500/25 text-emerald-400',
  ICD_CODE:   'bg-orange-500/10 border-orange-500/25 text-orange-400',
}

const MOCK_ENTITIES: Entity[] = [
  { id: 'e1', type: 'PATIENT',    value: 'Maria Gonzalez',              context: 'PATIENT: MARIA GONZALEZ',          confidence: 0.99, source: 'page 1' },
  { id: 'e2', type: 'DIAGNOSIS',  value: 'Severe osteoarthritis M17.11',context: 'severe osteoarthritis of the right knee (ICD-10: M17.11)', confidence: 0.97, source: 'page 1' },
  { id: 'e3', type: 'CPT_CODE',   value: 'CPT 27447',                   context: 'total knee arthroplasty (CPT 27447)', confidence: 0.98, source: 'page 2' },
  { id: 'e4', type: 'ICD_CODE',   value: 'M25.361',                     context: 'right knee pain M25.361',           confidence: 0.95, source: 'page 1' },
  { id: 'e5', type: 'PROVIDER',   value: 'Dr. Robert Stein, MD',        context: 'ATTENDING: Dr. Robert Stein, MD',   confidence: 0.99, source: 'page 1' },
  { id: 'e6', type: 'MEDICATION', value: 'Naproxen 500mg BID × 3m',    context: 'NSAIDs: Naproxen 500mg BID × 3 months', confidence: 0.93, source: 'page 2' },
  { id: 'e7', type: 'DATE',       value: '2024-01-15',                  context: 'DATE OF SERVICE: 2024-01-15',        confidence: 0.99, source: 'page 1' },
  { id: 'e8', type: 'DATE',       value: '2024-02-15',                  context: 'Scheduled 2024-02-15',              confidence: 0.96, source: 'page 3' },
]

const ENTITY_TYPE_GROUPS = [
  { type: 'DIAGNOSIS',  label: 'Diagnoses' },
  { type: 'CPT_CODE',   label: 'Procedures' },
  { type: 'ICD_CODE',   label: 'ICD Codes' },
  { type: 'MEDICATION', label: 'Medications' },
  { type: 'PROVIDER',   label: 'Providers' },
  { type: 'DATE',       label: 'Dates' },
]

export function ExtractedEntitiesPanel() {
  const grouped = ENTITY_TYPE_GROUPS.map((g) => ({
    ...g,
    entities: MOCK_ENTITIES.filter((e) => e.type === g.type),
  })).filter((g) => g.entities.length > 0)

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-1)]">Extracted Clinical Entities</h3>
          <p className="text-xs text-[var(--text-3)] mt-0.5">{MOCK_ENTITIES.length} entities extracted via NER</p>
        </div>
        <span className="chip bg-emerald-500/10 text-emerald-400 border-emerald-500/20">
          High confidence
        </span>
      </div>

      {grouped.map(({ type, label, entities }) => {
        const Icon = ENTITY_ICONS[type] ?? Hash
        const colorClass = ENTITY_COLOR[type] ?? 'bg-slate-500/10 border-slate-500/25 text-slate-400'
        return (
          <div key={type}>
            <div className="flex items-center gap-2 mb-2.5">
              <span className={cn('inline-flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full border', colorClass)}>
                <Icon className="w-3 h-3" />
                {label}
              </span>
              <span className="text-xs text-[var(--text-3)]">{entities.length}</span>
            </div>
            <div className="space-y-2">
              {entities.map((entity, i) => (
                <motion.div
                  key={entity.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="card p-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-[var(--text-1)]">{entity.value}</p>
                      <p className="text-xs text-[var(--text-3)] mt-0.5 italic leading-snug">
                        "…{entity.context}…"
                      </p>
                      <p className="text-xs text-[var(--text-3)] mt-1">{entity.source}</p>
                    </div>
                    <div className="flex-shrink-0 w-20">
                      <ConfidenceBar value={entity.confidence} size="sm" showPercent />
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}