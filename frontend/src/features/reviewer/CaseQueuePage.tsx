import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, RefreshCw } from 'lucide-react'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { casesService, type CaseListItem } from '@/services/cases.service'

const STATUS_FILTERS = [
  { label: 'All', value: '' },
  { label: 'Under Review', value: 'UNDER_REVIEW' },
  { label: 'Escalated', value: 'ESCALATED' },
  { label: 'Pended', value: 'PENDED' },
  { label: 'Submitted', value: 'SUBMITTED' },
]

const PRIORITY_FILTERS = ['ALL', 'EMERGENT', 'URGENT', 'ROUTINE']

const PRIORITY_STYLE: Record<string, string> = {
  EMERGENT: 'text-red-700 bg-red-50 border border-red-200',
  URGENT:   'text-amber-700 bg-amber-50 border border-amber-200',
  ROUTINE:  'text-gray-600 bg-gray-100',
}

function formatDate(iso: string | null) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' +
         d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}

export default function CaseQueuePage() {
  const [cases, setCases]           = useState<CaseListItem[]>([])
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState<string | null>(null)
  const [search, setSearch]         = useState('')
  const [statusFilter, setStatus]   = useState('')
  const [priorityFilter, setPriority] = useState('ALL')

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, any> = {}
      if (statusFilter) params.status = [statusFilter]
      if (priorityFilter !== 'ALL') params.priority = [priorityFilter]
      const { cases: data } = await casesService.listCases(params)
      setCases(data)
    } catch (err: any) {
      setError(err?.message ?? 'Failed to load cases')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [statusFilter, priorityFilter])

  const filtered = cases.filter((c) => {
    if (!search) return true
    const q = search.toLowerCase()
    return c.case_number.toLowerCase().includes(q) || c.patient_name.toLowerCase().includes(q)
  })

  return (
    <div>
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Case Queue</h1>
          <p className="page-subtitle">{loading ? 'Loading…' : `${filtered.length} case${filtered.length !== 1 ? 's' : ''}`}</p>
        </div>
        <button onClick={load} disabled={loading} className="p-1.5 text-gray-400 hover:text-gray-600 disabled:opacity-40">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search patient or case #…"
            className="input pl-9 w-60"
          />
        </div>

        <select value={statusFilter} onChange={(e) => setStatus(e.target.value)} className="input w-auto">
          {STATUS_FILTERS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
        </select>

        <select value={priorityFilter} onChange={(e) => setPriority(e.target.value)} className="input w-auto">
          {PRIORITY_FILTERS.map((f) => <option key={f}>{f}</option>)}
        </select>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
      )}

      {/* Table */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="animate-spin rounded-full h-7 w-7 border-b-2 border-blue-600" />
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Case #</th>
                <th>Patient</th>
                <th>Service</th>
                <th>Priority</th>
                <th>Status</th>
                <th>AI Rec.</th>
                <th>Submitted</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr><td colSpan={8} className="text-center py-10 text-gray-400">No cases match your filters.</td></tr>
              ) : filtered.map((c) => (
                <tr key={c.case_id}>
                  <td className="font-mono text-xs text-blue-600">{c.case_number}</td>
                  <td className="font-medium text-gray-900">{c.patient_name}</td>
                  <td className="text-gray-600 text-sm">{c.service_type?.replace(/_/g, ' ') ?? '—'}</td>
                  <td>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${PRIORITY_STYLE[c.priority] ?? 'text-gray-600 bg-gray-100'}`}>
                      {c.priority}
                    </span>
                  </td>
                  <td><StatusBadge status={c.status} /></td>
                  <td>
                    {c.ai_recommendation ? (
                      <span className={`text-xs font-medium ${c.ai_recommendation === 'APPROVE' ? 'text-green-700' : 'text-red-700'}`}>
                        {c.ai_recommendation}
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400">Pending</span>
                    )}
                  </td>
                  <td className="text-gray-500 text-xs">{formatDate(c.submitted_at)}</td>
                  <td>
                    <Link
                      to={`/reviewer/case/${c.case_id}`}
                      className="px-3 py-1.5 text-xs font-medium text-blue-600 border border-blue-200 rounded-md hover:bg-blue-50 transition-colors"
                    >
                      Review
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
