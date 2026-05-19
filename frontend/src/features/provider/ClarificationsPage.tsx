import { useEffect, useState } from 'react'
import { MessageSquare, Send, Clock, RefreshCw, AlertCircle } from 'lucide-react'
import { casesService, type CaseListItem, type ClarificationItem } from '@/services/cases.service'

interface PendingClarification {
  case: CaseListItem
  clarification: ClarificationItem
}

export default function ProviderClarificationsPage() {
  const [pending, setPending]       = useState<PendingClarification[]>([])
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState<string | null>(null)
  const [responses, setResponses]   = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState<Record<string, boolean>>({})
  const [submitted, setSubmitted]   = useState<Set<string>>(new Set())

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const { cases } = await casesService.listCases({ status: ['PENDING_CLARIFICATION'] })
      const enriched = await Promise.all(
        cases.map(async (c) => {
          try {
            const clList = await casesService.getClarifications(c.case_id)
            const openCl = clList.find((cl) => cl.status === 'PENDING')
            return openCl ? { case: c, clarification: openCl } : null
          } catch {
            return null
          }
        })
      )
      setPending(enriched.filter((x): x is PendingClarification => x !== null))
    } catch (err: any) {
      setError(err?.message ?? 'Failed to load clarifications')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function handleSubmit(caseId: string, clarificationId: string) {
    const responseText = responses[clarificationId]?.trim()
    if (!responseText || responseText.length < 5) return

    setSubmitting((s) => ({ ...s, [clarificationId]: true }))
    try {
      await casesService.respondToClarification(caseId, {
        clarification_id: clarificationId,
        response: responseText,
      })
      setSubmitted((s) => new Set([...s, clarificationId]))
    } catch (err: any) {
      setError(err?.message ?? 'Failed to submit response')
    } finally {
      setSubmitting((s) => ({ ...s, [clarificationId]: false }))
    }
  }

  function daysSince(iso: string) {
    const diff = Date.now() - new Date(iso).getTime()
    return Math.floor(diff / 86400000)
  }

  if (loading) {
    return (
      <div>
        <div className="page-header">
          <h1 className="page-title">Clarification Requests</h1>
        </div>
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin rounded-full h-7 w-7 border-b-2 border-blue-600" />
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Clarification Requests</h1>
          <p className="page-subtitle">Reviewer requests requiring your response</p>
        </div>
        <button onClick={load} className="p-1.5 text-gray-400 hover:text-gray-600">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {pending.length === 0 ? (
        <div className="card p-12 text-center text-gray-400">
          <MessageSquare className="w-8 h-8 mx-auto mb-3 opacity-40" />
          <p className="font-medium text-gray-500">No open clarification requests</p>
          <p className="text-sm mt-1">You're all caught up.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {pending.map(({ case: c, clarification: cl }) => (
            <div key={cl.clarification_id} className="card p-5">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-xs text-blue-600">{c.case_number}</span>
                  </div>
                  <p className="font-medium text-gray-900">{c.patient_name}</p>
                  <p className="text-sm text-gray-500">{c.service_type?.replace(/_/g, ' ') ?? '—'}</p>
                </div>
                <div className="flex items-center gap-1.5 text-amber-600 bg-amber-50 px-2.5 py-1 rounded-md text-xs font-medium">
                  <Clock className="w-3.5 h-3.5" />
                  {daysSince(cl.sent_at)}d open
                </div>
              </div>

              <div className="bg-blue-50 border border-blue-100 rounded-md px-4 py-3 mb-4">
                <p className="text-xs font-semibold text-blue-700 mb-1">Reviewer Question</p>
                <p className="text-sm text-blue-900">{cl.question}</p>
              </div>

              {submitted.has(cl.clarification_id) ? (
                <div className="bg-green-50 border border-green-100 rounded-md px-4 py-3 text-sm text-green-700">
                  Response submitted. The reviewer has been notified and the case will be re-evaluated.
                </div>
              ) : (
                <div className="space-y-3">
                  <textarea
                    rows={4}
                    value={responses[cl.clarification_id] ?? ''}
                    onChange={(e) => setResponses((r) => ({ ...r, [cl.clarification_id]: e.target.value }))}
                    className="input resize-none"
                    placeholder="Type your response. Include relevant clinical details, dates, and documentation references."
                  />
                  <button
                    onClick={() => handleSubmit(c.case_id, cl.clarification_id)}
                    disabled={
                      !responses[cl.clarification_id]?.trim() ||
                      (responses[cl.clarification_id]?.trim().length ?? 0) < 5 ||
                      submitting[cl.clarification_id]
                    }
                    className="btn-primary disabled:opacity-40"
                  >
                    <Send className="w-4 h-4" />
                    {submitting[cl.clarification_id] ? 'Submitting…' : 'Submit Response'}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
