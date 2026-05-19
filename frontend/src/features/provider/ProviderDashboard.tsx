import { useEffect, useState } from 'react'
import { FileText, Clock, CheckCircle, XCircle, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { StatCard } from '@/components/ui/StatCard'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { useAuthStore } from '@/store'
import { casesService, type CaseListItem } from '@/services/cases.service'

function formatDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export default function ProviderDashboard() {
  const user = useAuthStore((s) => s.user)
  const [cases, setCases]     = useState<CaseListItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    casesService.listCases({ page_size: 5 })
      .then(({ cases }) => setCases(cases))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const total    = cases.length
  const pending  = cases.filter((c) => ['SUBMITTED', 'PROCESSING', 'UNDER_REVIEW', 'PENDING_CLARIFICATION', 'PENDED', 'ESCALATED'].includes(c.status)).length
  const approved = cases.filter((c) => c.status === 'APPROVED').length
  const denied   = cases.filter((c) => c.status === 'DENIED').length

  return (
    <div>
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Welcome back, {user?.name}</p>
        </div>
        <Link to="/provider/submit" className="btn-primary">
          <Plus className="w-4 h-4" />
          New Request
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Submitted" value={loading ? '…' : total}    icon={FileText}    iconColor="text-blue-600" />
        <StatCard label="Pending Review"  value={loading ? '…' : pending}  icon={Clock}       iconColor="text-amber-500" />
        <StatCard label="Approved"        value={loading ? '…' : approved} icon={CheckCircle} iconColor="text-green-600" />
        <StatCard label="Denied"          value={loading ? '…' : denied}   icon={XCircle}     iconColor="text-red-600" />
      </div>

      {/* Recent cases */}
      <div className="card">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900">Recent Cases</h2>
          <Link to="/provider/cases" className="text-xs text-blue-600 hover:text-blue-700">View all →</Link>
        </div>
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
          </div>
        ) : cases.length === 0 ? (
          <div className="py-12 text-center text-sm text-gray-400">
            No cases yet. <Link to="/provider/submit" className="text-blue-600 hover:text-blue-700">Submit your first request →</Link>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Case #</th>
                <th>Patient</th>
                <th>Service Type</th>
                <th>Status</th>
                <th>Submitted</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.case_id}>
                  <td className="font-mono text-xs text-blue-600">{c.case_number}</td>
                  <td className="font-medium text-gray-900">{c.patient_name}</td>
                  <td className="text-gray-600 text-sm">{c.service_type?.replace(/_/g, ' ') ?? '—'}</td>
                  <td><StatusBadge status={c.status} /></td>
                  <td className="text-gray-500">{formatDate(c.submitted_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
