import { useState } from 'react'
import { Search, Download } from 'lucide-react'

const LOGS = [
  { id: 'EVT-1042', time: '2024-05-18 10:42:31', actor: 'dr.mills@clinic.com',     role: 'provider', action: 'PA_SUBMITTED',       resource: 'PA-2024-010', ip: '192.168.1.45' },
  { id: 'EVT-1041', time: '2024-05-18 10:15:08', actor: 'james.carter@ins.com',    role: 'reviewer', action: 'CASE_APPROVED',       resource: 'PA-2024-007', ip: '10.0.0.12'    },
  { id: 'EVT-1040', time: '2024-05-18 09:58:22', actor: 'admin@system.com',        role: 'admin',    action: 'POLICY_UPDATED',      resource: 'POL-MRI-001', ip: '10.0.0.1'     },
  { id: 'EVT-1039', time: '2024-05-18 09:30:47', actor: 'lisa.park@ins.com',       role: 'reviewer', action: 'CASE_DENIED',         resource: 'PA-2024-004', ip: '10.0.0.15'    },
  { id: 'EVT-1038', time: '2024-05-18 09:12:05', actor: 'admin@system.com',        role: 'admin',    action: 'USER_CREATED',        resource: 'dr.torres@…', ip: '10.0.0.1'     },
  { id: 'EVT-1037', time: '2024-05-18 08:55:19', actor: 'dr.white@clinic.com',     role: 'provider', action: 'CLARIFICATION_SENT',  resource: 'CLR-001',     ip: '192.168.1.22' },
  { id: 'EVT-1036', time: '2024-05-18 08:44:33', actor: 'james.carter@ins.com',    role: 'reviewer', action: 'CASE_IN_REVIEW',      resource: 'PA-2024-009', ip: '10.0.0.12'    },
  { id: 'EVT-1035', time: '2024-05-17 17:30:00', actor: 'admin@system.com',        role: 'admin',    action: 'USER_DEACTIVATED',    resource: 'old.user@…',  ip: '10.0.0.1'     },
  { id: 'EVT-1034', time: '2024-05-17 16:22:14', actor: 'dr.mills@clinic.com',     role: 'provider', action: 'DOC_UPLOADED',        resource: 'PA-2024-008', ip: '192.168.1.45' },
  { id: 'EVT-1033', time: '2024-05-17 15:10:55', actor: 'mark.a@insurance.com',    role: 'reviewer', action: 'CLARIFICATION_REQ',   resource: 'PA-2024-006', ip: '10.0.0.18'    },
]

const ACTION_STYLE: Record<string, string> = {
  PA_SUBMITTED:       'bg-blue-100 text-blue-700',
  CASE_APPROVED:      'bg-green-100 text-green-700',
  CASE_DENIED:        'bg-red-100 text-red-700',
  CASE_IN_REVIEW:     'bg-indigo-100 text-indigo-700',
  POLICY_UPDATED:     'bg-gray-100 text-gray-700',
  USER_CREATED:       'bg-purple-100 text-purple-700',
  USER_DEACTIVATED:   'bg-orange-100 text-orange-700',
  CLARIFICATION_SENT: 'bg-amber-100 text-amber-700',
  CLARIFICATION_REQ:  'bg-amber-100 text-amber-700',
  DOC_UPLOADED:       'bg-teal-100 text-teal-700',
}

const ALL_ACTIONS = ['All Actions', ...Array.from(new Set(LOGS.map((l) => l.action)))]
const ALL_ROLES   = ['All Roles', 'provider', 'reviewer', 'admin']

export default function AuditLogsPage() {
  const [search, setSearch]   = useState('')
  const [action, setAction]   = useState('All Actions')
  const [role, setRole]       = useState('All Roles')

  const filtered = LOGS.filter((l) => {
    const matchSearch = !search || l.actor.includes(search) || l.resource.includes(search) || l.id.includes(search)
    const matchAction = action === 'All Actions' || l.action === action
    const matchRole   = role === 'All Roles' || l.role === role
    return matchSearch && matchAction && matchRole
  })

  return (
    <div>
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Audit Logs</h1>
          <p className="page-subtitle">Full system event trail</p>
        </div>
        <button className="btn-secondary flex items-center gap-1.5">
          <Download className="w-4 h-4" />
          Export CSV
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-5">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by actor, resource, or event ID…"
            className="input pl-9 w-72"
          />
        </div>
        <select value={action} onChange={(e) => setAction(e.target.value)} className="input w-auto">
          {ALL_ACTIONS.map((a) => <option key={a}>{a}</option>)}
        </select>
        <select value={role} onChange={(e) => setRole(e.target.value)} className="input w-auto capitalize">
          {ALL_ROLES.map((r) => <option key={r}>{r}</option>)}
        </select>
        <span className="text-sm text-gray-400 ml-auto">{filtered.length} events</span>
      </div>

      <div className="card overflow-hidden">
        <table className="data-table">
          <thead>
            <tr>
              <th>Event ID</th>
              <th>Timestamp</th>
              <th>Actor</th>
              <th>Role</th>
              <th>Action</th>
              <th>Resource</th>
              <th>IP Address</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={7} className="text-center py-10 text-gray-400">No events match your filters.</td></tr>
            ) : filtered.map((l) => (
              <tr key={l.id}>
                <td className="font-mono text-xs text-gray-500">{l.id}</td>
                <td className="text-xs text-gray-500 whitespace-nowrap">{l.time}</td>
                <td className="text-sm text-gray-700">{l.actor}</td>
                <td>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${
                    l.role === 'admin' ? 'bg-purple-100 text-purple-700' :
                    l.role === 'reviewer' ? 'bg-blue-100 text-blue-700' :
                    'bg-gray-100 text-gray-600'
                  }`}>{l.role}</span>
                </td>
                <td>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium font-mono ${ACTION_STYLE[l.action] ?? 'bg-gray-100 text-gray-600'}`}>
                    {l.action}
                  </span>
                </td>
                <td className="font-mono text-xs text-blue-600">{l.resource}</td>
                <td className="font-mono text-xs text-gray-400">{l.ip}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
