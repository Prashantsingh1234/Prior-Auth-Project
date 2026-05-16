import { useState } from 'react'
import { clsx } from 'clsx'
import {
  CheckCircle2, XCircle, Clock, ArrowUpCircle, MessageSquare,
  X, AlertTriangle, ChevronDown, ChevronUp,
} from 'lucide-react'
import { useReviewStore } from '@/store/reviewStore'
import { useApprove, useDeny, usePend, useEscalate, useAddNote } from '@/hooks/useReview'
import type { PACase, ApproveRequest, DenyRequest, PendRequest, EscalateRequest } from '@/api/types'

type MutationLike<TBody> = {
  mutate: (variables: TBody) => void
  isPending: boolean
}

interface ReviewerActionsProps {
  caseData: PACase
}

export function ReviewerActions({ caseData }: ReviewerActionsProps) {
  const { activeModal, setActiveModal } = useReviewStore()

  const approveMutation = useApprove(caseData.case_id)
  const denyMutation    = useDeny(caseData.case_id)
  const pendMutation    = usePend(caseData.case_id)
  const escalateMutation = useEscalate(caseData.case_id)
  const noteMutation    = useAddNote(caseData.case_id)

  const isTerminal = ['APPROVED', 'DENIED', 'CANCELLED'].includes(caseData.status)
  const canReview  = !isTerminal

  return (
    <div className="flex flex-col gap-3">
      {isTerminal && (
        <div className="flex items-center gap-2 p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-500">
          <AlertTriangle className="w-4 h-4 text-slate-400 flex-shrink-0" />
          This case is {caseData.status.toLowerCase().replace(/_/g, ' ')} and cannot be modified.
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        <ActionButton icon={<CheckCircle2 className="w-4 h-4" />} label="Approve"  variant="approve"  disabled={!canReview} onClick={() => setActiveModal('approve')} />
        <ActionButton icon={<XCircle className="w-4 h-4" />}      label="Deny"     variant="deny"     disabled={!canReview} onClick={() => setActiveModal('deny')} />
        <ActionButton icon={<Clock className="w-4 h-4" />}        label="Pend"     variant="pend"     disabled={!canReview} onClick={() => setActiveModal('pend')} />
        <ActionButton icon={<ArrowUpCircle className="w-4 h-4" />} label="Escalate" variant="escalate" disabled={!canReview} onClick={() => setActiveModal('escalate')} />
      </div>

      <button
        onClick={() => setActiveModal('note')}
        className="flex items-center justify-center gap-2 py-2 px-3 text-sm font-medium text-slate-600 border border-slate-200 rounded-xl hover:bg-slate-50 hover:border-slate-300 transition-colors"
      >
        <MessageSquare className="w-4 h-4" />
        Add Note
      </button>

      {activeModal === 'approve' && (
        <ApproveModal
          mutation={approveMutation}
          onClose={() => setActiveModal(null)}
        />
      )}
      {activeModal === 'deny' && (
        <DenyModal
          mutation={denyMutation}
          onClose={() => setActiveModal(null)}
        />
      )}
      {activeModal === 'pend' && (
        <PendModal
          mutation={pendMutation}
          onClose={() => setActiveModal(null)}
        />
      )}
      {activeModal === 'escalate' && (
        <EscalateModal
          mutation={escalateMutation}
          onClose={() => setActiveModal(null)}
        />
      )}
      {activeModal === 'note' && (
        <NoteModal
          mutation={noteMutation}
          onClose={() => setActiveModal(null)}
        />
      )}
    </div>
  )
}

// ─── Shared styles ────────────────────────────────────────────────────────────

const VARIANT_STYLES: Record<string, string> = {
  approve:  'bg-approve  text-white hover:bg-approve/90  focus:ring-approve',
  deny:     'bg-deny     text-white hover:bg-deny/90     focus:ring-deny',
  pend:     'bg-pend     text-white hover:bg-pend/90     focus:ring-pend',
  escalate: 'bg-escalate text-white hover:bg-escalate/90 focus:ring-escalate',
}

function ActionButton({
  icon, label, variant, disabled, onClick,
}: {
  icon: React.ReactNode
  label: string
  variant: string
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        'flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl text-sm font-semibold transition-all duration-150',
        'focus:outline-none focus:ring-2 focus:ring-offset-2',
        VARIANT_STYLES[variant],
        disabled && 'opacity-40 cursor-not-allowed',
      )}
    >
      {icon}
      {label}
    </button>
  )
}

function ModalShell({
  title, children, onClose,
}: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl p-6 animate-fade-in">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-slate-900">{title}</h3>
          <button onClick={onClose} className="p-1 rounded text-slate-400 hover:text-slate-700 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

// ─── Action-specific modals ───────────────────────────────────────────────────

function ApproveModal({
  mutation, onClose,
}: { mutation: MutationLike<ApproveRequest>; onClose: () => void }) {
  const [rationale, setRationale] = useState('')
  const [override, setOverride]   = useState('')
  const [showOverride, setShow]   = useState(false)

  return (
    <ModalShell title="Approve Authorization" onClose={onClose}>
      <p className="text-sm text-slate-500 mb-4">Confirm approval of this prior authorization request.</p>
      <div className="mb-4">
        <label className="block text-xs font-medium text-slate-700 mb-1.5">Approval rationale (optional)</label>
        <textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          rows={3}
          placeholder="Enter rationale…"
          className="w-full text-sm border border-slate-200 rounded-lg p-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-brand-400 placeholder-slate-300"
        />
      </div>
      <OverrideSection override={override} setOverride={setOverride} show={showOverride} setShow={setShow} />
      <ModalActions
        variant="approve"
        label="Approve"
        isPending={mutation.isPending}
        canSubmit
        onClose={onClose}
        onSubmit={() => mutation.mutate({ rationale, override_reason: override || undefined })}
      />
    </ModalShell>
  )
}

function DenyModal({
  mutation, onClose,
}: { mutation: MutationLike<DenyRequest>; onClose: () => void }) {
  const [rationale, setRationale] = useState('')
  const [override, setOverride]   = useState('')
  const [showOverride, setShow]   = useState(false)

  return (
    <ModalShell title="Deny Authorization" onClose={onClose}>
      <p className="text-sm text-slate-500 mb-4">Provide the denial rationale. This will be included in the member notification.</p>
      <div className="mb-4">
        <label className="block text-xs font-medium text-slate-700 mb-1.5">
          Denial reason <span className="text-red-500">*</span>
        </label>
        <textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          rows={4}
          placeholder="Enter denial rationale…"
          className="w-full text-sm border border-slate-200 rounded-lg p-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-brand-400 placeholder-slate-300"
        />
        {rationale.length > 0 && rationale.trim().length < 10 && (
          <p className="text-xs text-red-500 mt-1">Minimum 10 characters required</p>
        )}
      </div>
      <OverrideSection override={override} setOverride={setOverride} show={showOverride} setShow={setShow} />
      <ModalActions
        variant="deny"
        label="Deny"
        isPending={mutation.isPending}
        canSubmit={rationale.trim().length >= 10}
        onClose={onClose}
        onSubmit={() => mutation.mutate({ rationale, override_reason: override || undefined })}
      />
    </ModalShell>
  )
}

function PendModal({
  mutation, onClose,
}: { mutation: MutationLike<PendRequest>; onClose: () => void }) {
  const [pendingReason, setPendingReason] = useState('')

  return (
    <ModalShell title="Pend for Clarification" onClose={onClose}>
      <p className="text-sm text-slate-500 mb-4">Request additional information before making a determination.</p>
      <div className="mb-4">
        <label className="block text-xs font-medium text-slate-700 mb-1.5">
          What information is needed? <span className="text-red-500">*</span>
        </label>
        <textarea
          value={pendingReason}
          onChange={(e) => setPendingReason(e.target.value)}
          rows={4}
          placeholder="Describe the required information…"
          className="w-full text-sm border border-slate-200 rounded-lg p-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-brand-400 placeholder-slate-300"
        />
      </div>
      <ModalActions
        variant="pend"
        label="Pend"
        isPending={mutation.isPending}
        canSubmit={pendingReason.trim().length >= 10}
        onClose={onClose}
        onSubmit={() => mutation.mutate({ rationale: pendingReason, pending_reason: pendingReason })}
      />
    </ModalShell>
  )
}

function EscalateModal({
  mutation, onClose,
}: { mutation: MutationLike<EscalateRequest>; onClose: () => void }) {
  const [reason, setReason] = useState('')

  return (
    <ModalShell title="Escalate Case" onClose={onClose}>
      <p className="text-sm text-slate-500 mb-4">Escalate to senior reviewer or medical director for complex determination.</p>
      <div className="mb-4">
        <label className="block text-xs font-medium text-slate-700 mb-1.5">
          Reason for escalation <span className="text-red-500">*</span>
        </label>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={4}
          placeholder="Explain why this case requires escalation…"
          className="w-full text-sm border border-slate-200 rounded-lg p-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-brand-400 placeholder-slate-300"
        />
      </div>
      <ModalActions
        variant="escalate"
        label="Escalate"
        isPending={mutation.isPending}
        canSubmit={reason.trim().length >= 10}
        onClose={onClose}
        onSubmit={() => mutation.mutate({ reason })}
      />
    </ModalShell>
  )
}

function NoteModal({
  mutation, onClose,
}: { mutation: MutationLike<{ note: string }>; onClose: () => void }) {
  const [note, setNote] = useState('')

  return (
    <ModalShell title="Add Note" onClose={onClose}>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={5}
        placeholder="Enter your note…"
        className="w-full text-sm border border-slate-200 rounded-lg p-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-brand-400 mb-4 placeholder-slate-300"
      />
      <ModalActions
        variant="approve"
        label="Save Note"
        isPending={mutation.isPending}
        canSubmit={note.trim().length >= 3}
        onClose={onClose}
        onSubmit={() => mutation.mutate({ note })}
        submitClass="bg-brand-600 hover:bg-brand-700 focus:ring-brand-500"
      />
    </ModalShell>
  )
}

// ─── Shared sub-components ────────────────────────────────────────────────────

function OverrideSection({
  override, setOverride, show, setShow,
}: {
  override: string
  setOverride: (v: string) => void
  show: boolean
  setShow: (v: boolean) => void
}) {
  return (
    <div className="mb-4">
      <button
        onClick={() => setShow(!show)}
        className="text-xs text-slate-500 hover:text-brand-600 transition-colors flex items-center gap-1"
      >
        {show ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        Override AI recommendation
      </button>
      {show && (
        <textarea
          value={override}
          onChange={(e) => setOverride(e.target.value)}
          rows={2}
          placeholder="Reason for overriding AI recommendation…"
          className="mt-2 w-full text-xs border border-amber-200 rounded-lg p-2 resize-none focus:outline-none focus:ring-2 focus:ring-amber-400 bg-amber-50 placeholder-amber-300"
        />
      )}
    </div>
  )
}

function ModalActions({
  variant, label, isPending, canSubmit, onClose, onSubmit, submitClass,
}: {
  variant: string
  label: string
  isPending: boolean
  canSubmit: boolean
  onClose: () => void
  onSubmit: () => void
  submitClass?: string
}) {
  return (
    <div className="flex gap-2 justify-end">
      <button
        onClick={onClose}
        className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors"
      >
        Cancel
      </button>
      <button
        onClick={onSubmit}
        disabled={!canSubmit || isPending}
        className={clsx(
          'px-5 py-2 text-sm font-semibold text-white rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-offset-2',
          submitClass ?? VARIANT_STYLES[variant],
          (!canSubmit || isPending) && 'opacity-50 cursor-not-allowed',
        )}
      >
        {isPending ? 'Submitting…' : label}
      </button>
    </div>
  )
}
