import { useEffect, useState } from 'react'
import { Users, FileText, ShieldCheck, Activity } from 'lucide-react'
import { StatCard } from '@/components/ui/StatCard'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { casesService, type CaseListItem } from '@/services/cases.service'

function formatTime(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}

export default function AdminDashboard() {
  const [cases, setCases]     = useState<CaseListItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    casesService.listCases({ page_size: 10 })
      .then(({ cases }) => setCases(cases))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const activeCount   = cases.filter((c) => !['APPROVED', 'DENIED', 'CANCELLED'].includes(c.status)).length
  const totalCount    = cases.length
  const approvedCount = cases.filter((c) => c.status === 'APPROVED').length
  const deniedCount   = cases.filter((c) => c.status === 'DENIED').length

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Admin Dashboard</h1>
        <p className="page-subtitle">System overview and activity</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Cases"    value={loading ? '…' : totalCount}    icon={FileText}    iconColor="text-blue-600" />
        <StatCard label="Active Cases"   value={loading ? '…' : activeCount}   icon={Activity}    iconColor="text-amber-500" />
        <StatCard label="Approved"       value={loading ? '…' : approvedCount} icon={ShieldCheck} iconColor="text-green-600" />
        <StatCard label="Denied"         value={loading ? '…' : deniedCount}   icon={Users}       iconColor="text-red-600" />
      </div>

      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900">Recent Cases</h2>
        </div>
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
          </div>
        ) : cases.length === 0 ? (
          <div className="py-10 text-center text-sm text-gray-400">No cases in the system yet.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Case #</th>
                <th>Patient</th>
                <th>Provider</th>
                <th>Priority</th>
                <th>Status</th>
                <th>AI Rec.</th>
                <th>Submitted</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.case_id}>
                  <td className="font-mono text-xs text-blue-600">{c.case_number}</td>
                  <td className="font-medium text-gray-900">{c.patient_name}</td>
                  <td className="text-gray-600 text-sm truncate max-w-[120px]">{c.provider_name}</td>
                  <td>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                      c.priority === 'EMERGENT' ? 'bg-red-100 text-red-700' :
                      c.priority === 'URGENT'   ? 'bg-amber-100 text-amber-700' :
                      'bg-gray-100 text-gray-600'
                    }`}>{c.priority}</span>
                  </td>
                  <td><StatusBadge status={c.status} /></td>
                  <td>
                    {c.ai_recommendation ? (
                      <span className={`text-xs font-medium ${c.ai_recommendation === 'APPROVE' ? 'text-green-700' : 'text-red-700'}`}>
                        {c.ai_recommendation}
                      </span>
                    ) : <span className="text-xs text-gray-400">Pending</span>}
                  </td>
                  <td className="text-gray-500 text-xs">{formatTime(c.submitted_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
