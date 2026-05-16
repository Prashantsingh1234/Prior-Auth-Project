import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, XCircle, AlertTriangle, ArrowUpRight, User, Clock, Loader2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { cn, formatRelative } from '@/lib/utils'
import { ConfidenceBar } from '@/components/common/ConfidenceBar'

const schema = z.object({
  rationale: z.string().min(20, 'Please provide a rationale (min 20 characters)').max(2000),
})
type FormData = z.infer<typeof schema>

type DecisionType = 'approve' | 'deny' | 'pend' | 'escalate'

const DECISION_CFG = {
  approve:  { label: 'Approve',  icon: CheckCircle2,  btnClass: 'btn-approve',  confirmBg: 'bg-emerald-500/10 border-emerald-500/20', confirmText: 'text-emerald-400' },
  deny:     { label: 'Deny',     icon: XCircle,       btnClass: 'btn-deny',     confirmBg: 'bg-red-500/10 border-red-500/20',         confirmText: 'text-red-400' },
  pend:     { label: 'Request Info', icon: AlertTriangle, btnClass: 'btn-pend', confirmBg: 'bg-amber-500/10 border-amber-500/20',     confirmText: 'text-amber-400' },
  escalate: { label: 'Escalate', icon: ArrowUpRight,  btnClass: 'btn-ghost',    confirmBg: 'bg-violet-500/10 border-violet-500/20',   confirmText: 'text-violet-400' },
}

interface Props {
  caseData: {
    id: string
    caseNumber: string
    status: string
    aiRecommendation: string
    confidence: number
    patient: { firstName: string; lastName: string; memberId: string }
    procedure: string
    cptCode: string
  }
}

export function ReviewerActions({ caseData }: Props) {
  const navigate = useNavigate()
  const [selected, setSelected] = useState<DecisionType | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (data: FormData) => {
    if (!selected) return
    setSubmitting(true)
    await new Promise((r) => setTimeout(r, 1000))
    setSubmitting(false)
    setSubmitted(true)
    setTimeout(() => navigate('/dashboard'), 2000)
  }

  if (submitted) {
    const cfg = DECISION_CFG[selected!]
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="flex flex-col items-center justify-center h-full p-8 text-center"
      >
        <div className="w-16 h-16 rounded-full bg-emerald-500/15 flex items-center justify-center mb-4">
          <CheckCircle2 className="w-8 h-8 text-emerald-400" />
        </div>
        <p className="text-lg font-semibold text-[var(--text-1)]">Decision Recorded</p>
        <p className="text-sm text-[var(--text-3)] mt-1">
          Case {caseData.caseNumber} — {cfg.label}
        </p>
        <p className="text-xs text-[var(--text-3)] mt-4">Returning to queue…</p>
      </motion.div>
    )
  }

  return (
    <div className="p-5 space-y-5">
      {/* Case summary */}
      <div>
        <p className="section-label mb-2">Case Summary</p>
        <div className="space-y-1.5 text-sm">
          <div className="flex justify-between">
            <span className="text-[var(--text-3)]">Patient</span>
            <span className="text-[var(--text-1)] font-medium">
              {caseData.patient.firstName} {caseData.patient.lastName}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--text-3)]">Member ID</span>
            <span className="mono text-xs text-[var(--text-2)]">{caseData.patient.memberId}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--text-3)]">Procedure</span>
            <span className="text-[var(--text-1)] text-right max-w-40 leading-snug">{caseData.procedure}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--text-3)]">CPT Code</span>
            <span className="mono text-xs text-emerald-400">{caseData.cptCode}</span>
          </div>
        </div>
      </div>

      <div className="h-px bg-[var(--border)]" />

      {/* AI recommendation */}
      <div>
        <p className="section-label mb-2">AI Recommendation</p>
        <div className="p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/15">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-semibold text-emerald-400">Approve</span>
          </div>
          <ConfidenceBar value={caseData.confidence} size="sm" showLabel />
        </div>
      </div>

      <div className="h-px bg-[var(--border)]" />

      {/* Decision */}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <p className="section-label">Your Decision</p>

        <div className="grid grid-cols-2 gap-2">
          {(Object.entries(DECISION_CFG) as [DecisionType, typeof DECISION_CFG['approve']][]).map(([type, cfg]) => {
            const Icon = cfg.icon
            return (
              <button
                key={type}
                type="button"
                onClick={() => setSelected(type)}
                className={cn(
                  'btn btn-sm flex items-center justify-center gap-1.5 transition-all',
                  cfg.btnClass,
                  selected === type ? 'ring-2 ring-offset-2 ring-offset-[var(--surface)]' : '',
                  selected === type && type === 'approve' ? 'ring-emerald-500' : '',
                  selected === type && type === 'deny' ? 'ring-red-500' : '',
                  selected === type && type === 'pend' ? 'ring-amber-500' : '',
                  selected === type && type === 'escalate' ? 'ring-violet-500' : '',
                )}
              >
                <Icon className="w-3.5 h-3.5" />
                {cfg.label}
              </button>
            )
          })}
        </div>

        <AnimatePresence>
          {selected && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
            >
              <div className={cn('p-3 rounded-lg border mb-3', DECISION_CFG[selected].confirmBg)}>
                <p className={cn('text-xs font-medium', DECISION_CFG[selected].confirmText)}>
                  Recording: {DECISION_CFG[selected].label} — {caseData.caseNumber}
                </p>
              </div>

              <label className="section-label">Clinical Rationale *</label>
              <textarea
                {...register('rationale')}
                rows={5}
                className={cn(
                  'input mt-1 w-full resize-none',
                  errors.rationale && 'border-red-500/50'
                )}
                placeholder={`Document your clinical rationale for ${DECISION_CFG[selected].label.toLowerCase()}ing this request…`}
              />
              {errors.rationale && (
                <p className="text-xs text-red-400 mt-1">{errors.rationale.message}</p>
              )}

              <button
                type="submit"
                disabled={submitting}
                className={cn(
                  'btn w-full mt-3 flex items-center justify-center gap-2',
                  selected === 'approve' ? 'btn-approve' :
                  selected === 'deny' ? 'btn-deny' :
                  selected === 'pend' ? 'btn-pend' : 'btn-primary',
                  'disabled:opacity-60'
                )}
              >
                {submitting ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Submitting…</>
                ) : (
                  <>{DECISION_CFG[selected].label} Case</>
                )}
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </form>

      {/* Reviewer info */}
      <div className="flex items-center gap-2 text-xs text-[var(--text-3)]">
        <User className="w-3.5 h-3.5" />
        <span>Decision will be attributed to your account and audited</span>
      </div>
    </div>
  )
}