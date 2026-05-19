import { useEffect, useState } from 'react'
import { MessageSquare, CheckCircle, RefreshCw } from 'lucide-react'
import { casesService, type CaseListItem, type ClarificationItem } from '@/services/cases.service'

interface ClarificationGroup {
  case: CaseListItem
  clarifications: ClarificationItem[]
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function ReviewerClarificationsPage() {
  const [tab, setTab]           = useState<'pending' | 'resolved'>('pending')
  const [groups, setGroups]     = useState<ClarificationGroup[]>([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const { cases } = await casesService.listCases({ status: ['PENDING_CLARIFICATION', 'UNDER_REVIEW'] })
      const enriched = await Promise.all(
        cases.map(async (c) => {
          try {
            const cls = await casesService.getClarifications(c.case_id)
            return cls.length > 0 ? { case: c, clarifications: cls } : null
          } catch { return null }
        })
      )
      setGroups(enriched.filter((g): g is ClarificationGroup => g !== null))
    } catch (err: any) {
      setError(err?.message ?? 'Failed to load clarifications')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const pendingGroups  = groups.filter((g) => g.clarifications.some((cl) => cl.status === 'PENDING'))
  const resolvedGroups = groups.filter((g) => g.clarifications.every((cl) => cl.status !== 'PENDING'))

  const display = tab === 'pending' ? pendingGroups : resolvedGroups

  return (
    <div>
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Clarification Requests</h1>
          <p className="page-subtitle">Provider responses to your information requests</p>
        </div>
        <button onClick={load} disabled={loading} className="p-1.5 text-gray-400 hover:text-gray-600 disabled:opacity-40">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="flex gap-1 mb-5">
        {(['pending', 'resolved'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 text-sm rounded-md capitalize transition-colors ${
              tab === t ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            {t} ({t === 'pending' ? pendingGroups.length : resolvedGroups.length})
          </button>
        ))}
      </div>

      {error && <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>}

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin rounded-full h-7 w-7 border-b-2 border-blue-600" />
        </div>
      ) : display.length === 0 ? (
        <div className="card p-12 text-center text-gray-400">
          <MessageSquare className="w-8 h-8 mx-auto mb-3 opacity-40" />
          <p>{tab === 'pending' ? 'No pending clarification requests.' : 'No resolved clarifications.'}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {display.map(({ case: c, clarifications }) => (
            <div key={c.case_id} className="card p-5">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <span className="font-mono text-xs text-blue-600">{c.case_number}</span>
                  <p className="font-medium text-gray-900 mt-0.5">{c.patient_name}</p>
                  <p className="text-sm text-gray-500">{c.service_type?.replace(/_/g, ' ') ?? '—'}</p>
                </div>
                {tab === 'pending' ? (
                  <span className="px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 rounded-full">Awaiting response</span>
                ) : (
                  <div className="flex items-center gap-1.5 text-green-700 bg-green-50 px-2.5 py-1 rounded-md text-xs font-medium">
                    <CheckCircle className="w-3.5 h-3.5" />
                    Responded
                  </div>
                )}
              </div>

              {clarifications.map((cl) => (
                <div key={cl.clarification_id} className="space-y-2 mb-3 last:mb-0">
                  <div className="bg-blue-50 border border-blue-100 rounded-md px-4 py-3">
                    <p className="text-xs font-semibold text-blue-700 mb-1">
                      Your Question (Attempt {cl.attempt_number}) · {formatDate(cl.sent_at)}
                    </p>
                    <p className="text-sm text-blue-900">{cl.question}</p>
                  </div>
                  {cl.response && (
                    <div className="bg-green-50 border border-green-100 rounded-md px-4 py-3">
                      <p className="text-xs font-semibold text-green-700 mb-1">
                        Provider Response · {cl.answered_at ? formatDate(cl.answered_at) : ''}
                      </p>
                      <p className="text-sm text-green-900">{cl.response}</p>
                    </div>
                  )}
                  {!cl.response && tab === 'pending' && (
                    <p className="text-xs text-gray-400 pl-1">Sent {formatDate(cl.sent_at)} · No response yet</p>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
