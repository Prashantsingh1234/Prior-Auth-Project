import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ClipboardList, Clock, CheckCircle, XCircle, AlertTriangle } from 'lucide-react'
import { StatCard } from '@/components/ui/StatCard'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { useAuthStore } from '@/store'
import { casesService, type CaseListItem } from '@/services/cases.service'

const PRIORITY_STYLE: Record<string, string> = {
  EMERGENT: 'text-red-700 bg-red-50',
  URGENT:   'text-amber-700 bg-amber-50',
  ROUTINE:  'text-gray-600 bg-gray-100',
}

function formatDate(iso: string | null) {
  if (!iso) return '—'
  const d = new Date(iso)
  const diff = Date.now() - d.getTime()
  if (diff < 3600000)   return `${Math.floor(diff / 60000)}m ago`
  if (diff < 86400000)  return `${Math.floor(diff / 3600000)}h ago`
  return `${Math.floor(diff / 86400000)}d ago`
}

export default function ReviewerDashboard() {
  const user = useAuthStore((s) => s.user)
  const [cases, setCases]     = useState<CaseListItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    casesService.listCases({ page_size: 10 })
      .then(({ cases }) => setCases(cases))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const inQueue   = cases.filter((c) => ['SUBMITTED', 'UNDER_REVIEW', 'ESCALATED', 'PENDED'].includes(c.status)).length
  const approved  = cases.filter((c) => c.status === 'APPROVED').length
  const denied    = cases.filter((c) => c.status === 'DENIED').length
  const urgent    = cases.filter((c) => ['EMERGENT', 'URGENT'].includes(c.priority)).length
  const preview   = cases.slice(0, 5)

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Reviewer Dashboard</h1>
        <p className="page-subtitle">Welcome back, {user?.name}</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="In Queue"       value={loading ? '…' : inQueue}  icon={ClipboardList} iconColor="text-blue-600" />
        <StatCard label="Avg. Review"    value="4.2h"                     icon={Clock}         iconColor="text-amber-500" sub="target: 6h" />
        <StatCard label="Approved"       value={loading ? '…' : approved} icon={CheckCircle}   iconColor="text-green-600" />
        <StatCard label="Denied"         value={loading ? '…' : denied}   icon={XCircle}       iconColor="text-red-600" />
      </div>

      {/* Queue preview */}
      <div className="card mb-6">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-gray-900">Pending Review</h2>
            {!loading && <span className="px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 rounded-full">{inQueue}</span>}
          </div>
          <Link to="/reviewer/queue" className="text-xs text-blue-600 hover:text-blue-700">Open queue →</Link>
        </div>
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Case #</th>
                <th>Patient</th>
                <th>Service</th>
                <th>Priority</th>
                <th>Age</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {preview.length === 0 ? (
                <tr><td colSpan={7} className="text-center py-8 text-gray-400">Queue is empty.</td></tr>
              ) : preview.map((c) => (
                <tr key={c.case_id}>
                  <td className="font-mono text-xs text-blue-600">{c.case_number}</td>
                  <td className="font-medium text-gray-900">{c.patient_name}</td>
                  <td className="text-gray-600 text-sm">{c.service_type?.replace(/_/g, ' ') ?? '—'}</td>
                  <td>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${PRIORITY_STYLE[c.priority] ?? 'text-gray-600 bg-gray-100'}`}>
                      {c.priority}
                    </span>
                  </td>
                  <td className="text-gray-500 text-sm">{formatDate(c.submitted_at)}</td>
                  <td><StatusBadge status={c.status} /></td>
                  <td>
                    <Link to={`/reviewer/case/${c.case_id}`} className="text-xs text-blue-600 hover:text-blue-700 font-medium">Review →</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {urgent > 0 && (
        <div className="flex items-start gap-3 px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <p>{urgent} case{urgent !== 1 ? 's' : ''} marked Urgent or Emergent and require{urgent === 1 ? 's' : ''} priority review.</p>
        </div>
      )}
    </div>
  )
}
