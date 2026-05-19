import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, FileText, CheckCircle, XCircle, Clock, AlertCircle,
  ChevronDown, ChevronUp, Send, AlertTriangle,
} from 'lucide-react'
import { casesService, type CaseDetail } from '@/services/cases.service'

type Decision = 'approve' | 'deny' | 'pend' | 'escalate'

function ConfidenceBar({ score }: { score: number | null }) {
  const pct = score != null ? (score > 1 ? score : score * 100) : 0
  const color = pct >= 80 ? 'bg-green-500' : pct >= 60 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
      <div className={`h-2 rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
    </div>
  )
}

export default function CaseReviewPage() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate   = useNavigate()

  const [caseData, setCaseData]   = useState<CaseDetail | null>(null)
  const [loading, setLoading]     = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [activeDoc, setActiveDoc] = useState(0)
  const [showOCR, setShowOCR]     = useState(false)
  const [decision, setDecision]   = useState<Decision | null>(null)
  const [notes, setNotes]         = useState('')
  const [pendReason, setPendReason] = useState('')
  const [escalateTo, setEscalateTo] = useState('')
  const [showClar, setShowClar]   = useState(false)
  const [clarQuestion, setClarQuestion] = useState('')

  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitted, setSubmitted]   = useState(false)

  useEffect(() => {
    if (!caseId) return
    casesService.getCaseDetail(caseId)
      .then(setCaseData)
      .catch((err) => setLoadError(err?.message ?? 'Failed to load case'))
      .finally(() => setLoading(false))
  }, [caseId])

  async function handleSubmit() {
    if (!decision || !caseId) return
    setSubmitError(null)

    // Validate
    if ((decision === 'deny' || decision === 'pend') && notes.trim().length < 10) {
      setSubmitError('Rationale must be at least 10 characters.')
      return
    }
    if (decision === 'pend' && pendReason.trim().length < 5) {
      setSubmitError('Pending reason must be at least 5 characters.')
      return
    }
    if (decision === 'escalate' && notes.trim().length < 10) {
      setSubmitError('Escalation reason must be at least 10 characters.')
      return
    }

    setSubmitting(true)
    try {
      if (decision === 'approve') {
        await casesService.approveCase(caseId, { rationale: notes || 'Approved by clinical reviewer' })
      } else if (decision === 'deny') {
        await casesService.denyCase(caseId, { rationale: notes })
      } else if (decision === 'pend') {
        await casesService.pendCase(caseId, { rationale: notes, pending_reason: pendReason })
      } else if (decision === 'escalate') {
        await casesService.escalateCase(caseId, {
          reason: notes,
          escalate_to: escalateTo.trim() || null,
        })
      }
      setSubmitted(true)
    } catch (err: any) {
      setSubmitError(err?.message ?? 'Submission failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  // ── Loading / error states ──────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    )
  }

  if (loadError || !caseData) {
    return (
      <div className="max-w-md mx-auto mt-20 text-center">
        <AlertCircle className="w-10 h-10 text-red-500 mx-auto mb-3" />
        <p className="text-gray-700 font-medium mb-1">Failed to load case</p>
        <p className="text-sm text-gray-500 mb-4">{loadError}</p>
        <button onClick={() => navigate(-1)} className="btn-secondary">Go Back</button>
      </div>
    )
  }

  // ── Success screen ──────────────────────────────────────────────────────
  if (submitted) {
    const label = decision === 'pend' ? 'Pended' : decision === 'escalate' ? 'Escalated' : decision === 'deny' ? 'Denied' : 'Approved'
    return (
      <div className="max-w-md mx-auto mt-24 text-center">
        <div className={`inline-flex items-center justify-center w-14 h-14 rounded-full mb-4 ${
          decision === 'approve' ? 'bg-green-100' :
          decision === 'deny'   ? 'bg-red-100'   :
          'bg-amber-100'
        }`}>
          {decision === 'approve' ? <CheckCircle className="w-7 h-7 text-green-600" /> :
           decision === 'deny'    ? <XCircle className="w-7 h-7 text-red-600" />       :
                                    <Clock className="w-7 h-7 text-amber-600" />}
        </div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Case {label}</h2>
        <p className="text-sm text-gray-500 mb-6">
          {caseData.case_number} — {caseData.patient.first_name} {caseData.patient.last_name} has been {label.toLowerCase()}.
        </p>
        <button onClick={() => navigate('/reviewer/queue')} className="btn-primary">Back to Queue</button>
      </div>
    )
  }

  const c = caseData
  const patientName = `${c.patient.first_name} ${c.patient.last_name}`
  const providerName = [c.provider.first_name, c.provider.last_name].filter(Boolean).join(' ') || c.provider.organization || `NPI ${c.provider.npi}`
  const confidence = c.ai_confidence_score != null ? (c.ai_confidence_score > 1 ? c.ai_confidence_score : c.ai_confidence_score * 100) : null

  return (
    <div className="flex flex-col h-full -m-6">
      {/* Top bar */}
      <div className="flex items-center gap-4 px-6 py-3 bg-white border-b border-gray-200 shrink-0">
        <button onClick={() => navigate(-1)} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors">
          <ArrowLeft className="w-4 h-4" />Back
        </button>
        <div className="h-4 w-px bg-gray-200" />
        <div className="flex items-center gap-3 min-w-0">
          <span className="font-mono text-sm text-blue-600 font-medium shrink-0">{c.case_number}</span>
          <span className="text-gray-400">·</span>
          <span className="font-medium text-gray-900 truncate">{patientName}</span>
          <span className="text-gray-400">·</span>
          <span className="text-gray-600 text-sm truncate">{c.service_type?.replace(/_/g, ' ') ?? '—'}</span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className={`px-2.5 py-1 text-xs font-medium rounded border ${
            c.priority === 'EMERGENT' ? 'text-red-700 bg-red-50 border-red-200' :
            c.priority === 'URGENT'   ? 'text-amber-700 bg-amber-50 border-amber-200' :
            'text-gray-600 bg-gray-100 border-gray-200'
          }`}>{c.priority}</span>
        </div>
      </div>

      {/* 3-panel body */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── LEFT: Documents ── */}
        <div className="w-80 shrink-0 border-r border-gray-200 bg-white flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-900">Supporting Documents</h2>
          </div>

          {c.documents.length > 0 ? (
            <>
              <div className="px-3 pt-3 space-y-1 shrink-0">
                {c.documents.map((doc, i) => (
                  <button
                    key={doc.document_id}
                    onClick={() => setActiveDoc(i)}
                    className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-md text-left transition-colors ${
                      activeDoc === i ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <FileText className="w-4 h-4 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs font-medium truncate">{doc.original_filename}</p>
                      <p className="text-xs text-gray-400 capitalize">{doc.document_type.replace(/_/g, ' ').toLowerCase()}</p>
                    </div>
                  </button>
                ))}
              </div>
              <div className="flex-1 mx-3 mt-3 mb-3 bg-gray-100 rounded-md flex flex-col items-center justify-center text-gray-400 min-h-0">
                <FileText className="w-8 h-8 mb-2 opacity-40" />
                <p className="text-xs text-center px-4">{c.documents[activeDoc]?.original_filename ?? '—'}</p>
                <p className="text-xs mt-1 opacity-60 capitalize">{c.documents[activeDoc]?.document_type.replace(/_/g, ' ').toLowerCase()}</p>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-300 px-4 text-center">
              <FileText className="w-8 h-8 mb-2 opacity-50" />
              <p className="text-xs">No documents uploaded</p>
            </div>
          )}

          {/* OCR text */}
          <div className="border-t border-gray-100 shrink-0">
            <button
              onClick={() => setShowOCR((v) => !v)}
              className="w-full flex items-center justify-between px-4 py-2.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
            >
              <span>AI Rationale / OCR Text</span>
              {showOCR ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
            {showOCR && (
              <div className="px-4 pb-3 max-h-48 overflow-y-auto">
                {c.ai_rationale ? (
                  <p className="text-xs text-gray-600 leading-relaxed">{c.ai_rationale}</p>
                ) : (
                  <p className="text-xs text-gray-400 italic">No AI rationale available.</p>
                )}
              </div>
            )}
          </div>
        </div>

        {/* ── CENTER: Case Analysis ── */}
        <div className="flex-1 overflow-y-auto bg-gray-50 p-5 space-y-4 min-w-0">

          {/* Case Details */}
          <div className="card p-4">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Case Details</h3>
            <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              <div><span className="text-gray-500">Patient:</span> <span className="font-medium">{patientName}</span></div>
              <div><span className="text-gray-500">DOB:</span> <span className="font-medium">{c.patient.date_of_birth || '—'}</span></div>
              <div><span className="text-gray-500">Member ID:</span> <span className="font-medium">{c.patient.member_id || '—'}</span></div>
              <div><span className="text-gray-500">Provider:</span> <span className="font-medium text-xs">{providerName}</span></div>
              <div><span className="text-gray-500">NPI:</span> <span className="font-mono text-xs">{c.provider.npi}</span></div>
              <div><span className="text-gray-500">Specialty:</span> <span className="font-medium text-xs">{c.provider.specialty || '—'}</span></div>
            </div>
            <div className="mt-3 pt-3 border-t border-gray-100 flex flex-wrap gap-2">
              {c.cpt_codes.map((code) => (
                <span key={code} className="px-2.5 py-1 bg-blue-50 text-blue-700 text-xs font-mono rounded border border-blue-100">CPT: {code}</span>
              ))}
              {c.icd_codes.map((code) => (
                <span key={code} className="px-2.5 py-1 bg-gray-100 text-gray-700 text-xs font-mono rounded">{code}</span>
              ))}
            </div>
          </div>

          {/* AI Recommendation */}
          <div className="card p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">AI Recommendation</h3>
              {confidence != null && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">Confidence</span>
                  <span className="text-sm font-bold text-gray-900">{Math.round(confidence)}%</span>
                </div>
              )}
            </div>

            {c.ai_recommendation ? (
              <>
                <div className={`flex items-center gap-3 px-4 py-3 rounded-lg mb-3 ${
                  c.ai_recommendation === 'APPROVE' ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
                }`}>
                  {c.ai_recommendation === 'APPROVE'
                    ? <CheckCircle className="w-5 h-5 text-green-600 shrink-0" />
                    : <XCircle className="w-5 h-5 text-red-600 shrink-0" />}
                  <div>
                    <p className={`text-sm font-semibold ${c.ai_recommendation === 'APPROVE' ? 'text-green-800' : 'text-red-800'}`}>
                      Recommend: {c.ai_recommendation}
                    </p>
                    {c.ai_rationale && <p className="text-xs text-gray-600 mt-0.5 line-clamp-2">{c.ai_rationale}</p>}
                  </div>
                </div>
                {confidence != null && <ConfidenceBar score={confidence} />}
              </>
            ) : (
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <Clock className="w-4 h-4" />
                AI evaluation pending — case is still being processed.
              </div>
            )}
          </div>

          {/* Policy Criteria */}
          {c.policy_criteria.length > 0 && (
            <div className="card p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Policy Criteria</h3>
                <span className="text-xs text-gray-500">
                  {c.policy_criteria.filter((cr) => cr.status === 'MET').length} / {c.policy_criteria.length} met
                </span>
              </div>
              <div className="space-y-2">
                {c.policy_criteria.map((cr) => (
                  <div key={cr.criterion_id} className="flex items-start gap-3">
                    {cr.status === 'MET'         && <CheckCircle className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />}
                    {cr.status === 'NOT_MET'     && <XCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />}
                    {cr.status !== 'MET' && cr.status !== 'NOT_MET' && <AlertCircle className="w-4 h-4 text-gray-300 shrink-0 mt-0.5" />}
                    <div className="min-w-0">
                      <p className={`text-sm ${
                        cr.status === 'MET' ? 'text-gray-800' :
                        cr.status === 'NOT_MET' ? 'text-red-700' :
                        'text-gray-400'
                      }`}>{cr.criterion_name || cr.description}</p>
                      {cr.evidence && <p className="text-xs text-gray-500 mt-0.5">{cr.evidence}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Clarification history */}
          {c.clarifications.length > 0 && (
            <div className="card p-4">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Clarification History</h3>
              <div className="space-y-3">
                {c.clarifications.map((cl) => (
                  <div key={cl.clarification_id} className="text-sm">
                    <div className="bg-blue-50 border border-blue-100 rounded px-3 py-2 mb-2">
                      <p className="text-xs font-semibold text-blue-700 mb-0.5">Question (Attempt {cl.attempt_number})</p>
                      <p className="text-blue-900">{cl.question}</p>
                    </div>
                    {cl.response && (
                      <div className="bg-green-50 border border-green-100 rounded px-3 py-2">
                        <p className="text-xs font-semibold text-green-700 mb-0.5">Provider Response</p>
                        <p className="text-green-900">{cl.response}</p>
                      </div>
                    )}
                    {!cl.response && (
                      <p className="text-xs text-amber-600 px-1">Awaiting provider response…</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── RIGHT: Reviewer Actions ── */}
        <div className="w-72 shrink-0 border-l border-gray-200 bg-white flex flex-col overflow-y-auto">
          <div className="px-4 py-3 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-900">Reviewer Decision</h2>
          </div>

          <div className="flex-1 p-4 space-y-4">
            {/* Decision buttons */}
            <div className="space-y-2">
              {([
                { value: 'approve',  label: 'Approve',  Icon: CheckCircle, active: 'border-green-500 bg-green-50 text-green-700', hover: 'hover:border-green-300 hover:bg-green-50' },
                { value: 'deny',     label: 'Deny',     Icon: XCircle,     active: 'border-red-500 bg-red-50 text-red-700',     hover: 'hover:border-red-300 hover:bg-red-50' },
                { value: 'pend',     label: 'Pend',     Icon: Clock,       active: 'border-amber-500 bg-amber-50 text-amber-700', hover: 'hover:border-amber-300 hover:bg-amber-50' },
                { value: 'escalate', label: 'Escalate', Icon: AlertTriangle, active: 'border-orange-500 bg-orange-50 text-orange-700', hover: 'hover:border-orange-300 hover:bg-orange-50' },
              ] as const).map(({ value, label, Icon, active, hover }) => (
                <button
                  key={value}
                  onClick={() => setDecision(value)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg border-2 transition-colors ${
                    decision === value ? active : `border-gray-200 ${hover} text-gray-700`
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span className="font-medium">{label}</span>
                </button>
              ))}
            </div>

            {/* Notes / Rationale */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">
                {decision === 'escalate' ? 'Escalation Reason *' : 'Clinical Rationale'}
                {(decision === 'deny' || decision === 'pend' || decision === 'escalate') && (
                  <span className="text-gray-400 font-normal ml-1">(min 10 chars)</span>
                )}
              </label>
              <textarea
                rows={4}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="input resize-none text-sm"
                placeholder={
                  decision === 'deny'     ? 'Clinical rationale for denial (required)…' :
                  decision === 'pend'     ? 'What additional information is needed?…' :
                  decision === 'escalate' ? 'Reason for escalating to senior reviewer…' :
                  'Add clinical rationale for your decision…'
                }
              />
            </div>

            {/* Pend-specific: pending reason */}
            {decision === 'pend' && (
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1.5">
                  Pending Reason Summary * <span className="text-gray-400 font-normal">(min 5 chars)</span>
                </label>
                <input
                  value={pendReason}
                  onChange={(e) => setPendReason(e.target.value)}
                  className="input text-sm"
                  placeholder="Short summary for provider notification…"
                />
              </div>
            )}

            {/* Escalate-specific: target reviewer */}
            {decision === 'escalate' && (
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1.5">Assign To (Reviewer ID, optional)</label>
                <input
                  value={escalateTo}
                  onChange={(e) => setEscalateTo(e.target.value)}
                  className="input text-sm font-mono"
                  placeholder="UUID of target reviewer…"
                />
              </div>
            )}

            {/* Request clarification */}
            <div className="border-t border-gray-100 pt-4">
              <button
                onClick={() => setShowClar((v) => !v)}
                className="flex items-center gap-2 text-xs font-medium text-blue-600 hover:text-blue-700"
              >
                <Send className="w-3.5 h-3.5" />
                Request Clarification from Provider
              </button>
              {showClar && (
                <div className="mt-2 space-y-2">
                  <textarea
                    rows={3}
                    value={clarQuestion}
                    onChange={(e) => setClarQuestion(e.target.value)}
                    className="input resize-none text-sm"
                    placeholder="What additional information do you need?"
                  />
                  <p className="text-xs text-gray-400">Use Pend or Escalate decision to officially request clarification.</p>
                </div>
              )}
            </div>

            {/* Submit error */}
            {submitError && (
              <div className="flex items-start gap-2 px-3 py-2 bg-red-50 border border-red-100 rounded text-xs text-red-700">
                <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                {submitError}
              </div>
            )}
          </div>

          {/* Submit button */}
          <div className="p-4 border-t border-gray-100 shrink-0">
            <button
              onClick={handleSubmit}
              disabled={!decision || submitting}
              className={`w-full py-2.5 rounded-md text-sm font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                decision === 'approve'   ? 'bg-green-600 hover:bg-green-700 text-white' :
                decision === 'deny'      ? 'bg-red-600 hover:bg-red-700 text-white' :
                decision === 'pend'      ? 'bg-amber-500 hover:bg-amber-600 text-white' :
                decision === 'escalate'  ? 'bg-orange-500 hover:bg-orange-600 text-white' :
                'bg-blue-600 hover:bg-blue-700 text-white'
              }`}
            >
              {submitting ? 'Submitting…' :
               decision ? `Submit — ${decision.charAt(0).toUpperCase() + decision.slice(1)}` :
               'Select a Decision'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
