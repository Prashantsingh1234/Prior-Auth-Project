import { motion } from 'framer-motion'
import { CheckCircle2, XCircle, AlertCircle, ChevronRight, BookOpen } from 'lucide-react'
import { ConfidenceBar } from '@/components/common/ConfidenceBar'
import { cn } from '@/lib/utils'

type CriterionStatus = 'MET' | 'NOT_MET' | 'INSUFFICIENT'

interface PolicyCriterion {
  id: string
  criterion: string
  status: CriterionStatus
  evidence: string
  policyRef: string
  confidence: number
}

const MOCK_CRITERIA: PolicyCriterion[] = [
  {
    id: 'cr1',
    criterion: 'Diagnosis of moderate to severe osteoarthritis confirmed by imaging',
    status: 'MET',
    evidence: 'X-ray (2024-01-10) shows severe tricompartmental osteoarthritis with bone-on-bone changes, significant joint space narrowing, subchondral sclerosis.',
    policyRef: 'Policy §4.2.1 — Radiographic Evidence',
    confidence: 0.97,
  },
  {
    id: 'cr2',
    criterion: 'Failure of conservative treatment (≥6 months of physical therapy)',
    status: 'MET',
    evidence: 'Patient completed 6 months physical therapy (24 sessions) with inadequate pain relief per clinical notes.',
    policyRef: 'Policy §4.2.2 — Conservative Treatment Failure',
    confidence: 0.95,
  },
  {
    id: 'cr3',
    criterion: 'Failure of pharmacological management (NSAIDs or equivalent)',
    status: 'MET',
    evidence: 'NSAIDs (Naproxen 500mg BID) discontinued after 3 months due to GI intolerance. No adequate NSAID trial achieved.',
    policyRef: 'Policy §4.2.3 — Pharmacological Management',
    confidence: 0.88,
  },
  {
    id: 'cr4',
    criterion: 'BMI within acceptable surgical range (< 40 kg/m²)',
    status: 'MET',
    evidence: 'Patient BMI: 28.4 kg/m² — within acceptable surgical range.',
    policyRef: 'Policy §4.2.5 — Surgical Eligibility',
    confidence: 0.99,
  },
  {
    id: 'cr5',
    criterion: 'Significant functional limitation documented',
    status: 'MET',
    evidence: 'Pain rated 9/10 significantly limiting ambulation. ROM reduced to 85° flexion with 15° flexion contracture.',
    policyRef: 'Policy §4.2.4 — Functional Impairment',
    confidence: 0.93,
  },
  {
    id: 'cr6',
    criterion: 'Pre-operative cardiac evaluation within 90 days',
    status: 'INSUFFICIENT',
    evidence: 'Pre-op evaluation mentioned but no specific cardiac clearance documentation found in submitted records.',
    policyRef: 'Policy §4.3.1 — Pre-surgical Clearance',
    confidence: 0.61,
  },
]

const STATUS_CFG = {
  MET:          { icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/5 border-emerald-500/15', label: 'Met' },
  NOT_MET:      { icon: XCircle,      color: 'text-red-400',     bg: 'bg-red-500/5 border-red-500/15',         label: 'Not Met' },
  INSUFFICIENT: { icon: AlertCircle,  color: 'text-amber-400',   bg: 'bg-amber-500/5 border-amber-500/15',     label: 'Insufficient' },
}

export function PolicyCriteriaPanel() {
  const metCount = MOCK_CRITERIA.filter((c) => c.status === 'MET').length
  const total = MOCK_CRITERIA.length

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-1)]">Policy Criteria Assessment</h3>
          <p className="text-xs text-[var(--text-3)] mt-0.5">Total Knee Arthroplasty — CPT 27447</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span className="text-sm font-semibold text-emerald-400">{metCount}/{total}</span>
          <span className="text-xs text-emerald-400/70">criteria met</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-2 rounded-full bg-[var(--elevated)] overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${(metCount / total) * 100}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-400"
        />
      </div>

      {/* Criteria list */}
      <div className="space-y-3">
        {MOCK_CRITERIA.map((c, i) => {
          const { icon: Icon, color, bg, label } = STATUS_CFG[c.status]
          return (
            <motion.div
              key={c.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
              className={cn('rounded-xl border p-4', bg)}
            >
              <div className="flex items-start gap-3">
                <Icon className={cn('w-4.5 h-4.5 mt-0.5 flex-shrink-0', color)} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-[var(--text-1)] leading-snug">{c.criterion}</p>
                    <span className={cn('text-xs font-semibold flex-shrink-0', color)}>{label}</span>
                  </div>

                  <p className="text-xs text-[var(--text-2)] mt-2 leading-relaxed">{c.evidence}</p>

                  <div className="flex items-center justify-between mt-3">
                    <div className="flex items-center gap-1.5 text-xs text-[var(--text-3)]">
                      <BookOpen className="w-3 h-3" />
                      {c.policyRef}
                    </div>
                    <div className="w-24">
                      <ConfidenceBar value={c.confidence} size="sm" showPercent />
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}