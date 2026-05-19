import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, Plus, RefreshCw } from 'lucide-react'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { casesService, type CaseListItem } from '@/services/cases.service'

const STATUS_FILTERS = [
  { label: 'All', value: '' },
  { label: 'Submitted', value: 'SUBMITTED' },
  { label: 'Processing', value: 'PROCESSING' },
  { label: 'In Review', value: 'UNDER_REVIEW' },
  { label: 'Info Requested', value: 'PENDING_CLARIFICATION' },
  { label: 'Approved', value: 'APPROVED' },
  { label: 'Denied', value: 'DENIED' },
  { label: 'Pended', value: 'PENDED' },
]

function formatDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function MyCasesPage() {
  const [cases, setCases]       = useState<CaseListItem[]>([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState<string | null>(null)
  const [search, setSearch]     = useState('')
  const [filter, setFilter]     = useState('')

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const params = filter ? { status: [filter] } : undefined
      const { cases: data } = await casesService.listCases(params)
      setCases(data)
    } catch (err: any) {
      setError(err?.message ?? 'Failed to load cases')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [filter])

  const filtered = cases.filter((c) => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      c.case_number.toLowerCase().includes(q) ||
      c.patient_name.toLowerCase().includes(q)
    )
  })

  return (
    <div>
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">My Cases</h1>
          <p className="page-subtitle">{loading ? 'Loading…' : `${cases.length} authorization request${cases.length !== 1 ? 's' : ''}`}</p>
        </div>
        <Link to="/provider/submit" className="btn-primary">
          <Plus className="w-4 h-4" />
          New Request
        </Link>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by patient or case number…"
            className="input pl-9 w-64"
          />
        </div>
        <div className="flex gap-1 flex-wrap">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={`px-3 py-1.5 text-xs rounded-md border transition-colors ${
                filter === f.value
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <button onClick={load} disabled={loading} className="ml-auto p-1.5 text-gray-400 hover:text-gray-600 disabled:opacity-40">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Error */}
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
                <th>Service Type</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Submitted</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr><td colSpan={7} className="text-center py-10 text-gray-400">No cases found.</td></tr>
              ) : filtered.map((c) => (
                <tr key={c.case_id}>
                  <td className="font-mono text-xs text-blue-600">{c.case_number}</td>
                  <td className="font-medium text-gray-900">{c.patient_name}</td>
                  <td className="text-gray-600 text-sm">{c.service_type?.replace(/_/g, ' ') ?? '—'}</td>
                  <td>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                      c.priority === 'EMERGENT' ? 'bg-red-100 text-red-700' :
                      c.priority === 'URGENT'   ? 'bg-amber-100 text-amber-700' :
                      'bg-gray-100 text-gray-600'
                    }`}>{c.priority}</span>
                  </td>
                  <td><StatusBadge status={c.status} /></td>
                  <td className="text-gray-500 text-sm">{formatDate(c.submitted_at)}</td>
                  <td>
                    {c.status === 'PENDING_CLARIFICATION' && (
                      <Link to="/provider/clarifications" className="text-xs text-blue-600 hover:text-blue-700 font-medium">Respond</Link>
                    )}
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
