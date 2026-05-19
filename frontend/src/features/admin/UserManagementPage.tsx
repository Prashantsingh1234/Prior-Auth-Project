import { useState } from 'react'
import { Search, Plus, Shield, UserCheck, User, X, AlertCircle, CheckCircle } from 'lucide-react'
import { usersService, type UserPublic, type CreateUserPayload } from '@/services/users.service'

// Static display — no GET /users list endpoint exists on the backend
const PLACEHOLDER_USERS: (UserPublic & { placeholder: true })[] = [
  { user_id: '1', username: 'dr.mills', email: 'sarah.mills@clinic.com',    role: 'provider', is_active: true,  created_at: '2024-01-15', last_login_at: null, organization: 'Metro Clinic', placeholder: true },
  { user_id: '2', username: 'j.carter', email: 'james.carter@insurer.com',  role: 'reviewer', is_active: true,  created_at: '2024-01-20', last_login_at: null, organization: null,           placeholder: true },
  { user_id: '3', username: 'dr.white', email: 'ben.white@clinic.com',      role: 'provider', is_active: true,  created_at: '2024-02-01', last_login_at: null, organization: 'Metro Clinic', placeholder: true },
  { user_id: '4', username: 'l.park',   email: 'lisa.park@insurer.com',     role: 'reviewer', is_active: true,  created_at: '2024-02-10', last_login_at: null, organization: null,           placeholder: true },
  { user_id: '5', username: 'admin',    email: 'admin@system.com',           role: 'admin',    is_active: true,  created_at: '2024-01-01', last_login_at: null, organization: null,           placeholder: true },
]

const ROLE_ICON: Record<string, React.ReactNode> = {
  admin:    <Shield className="w-3.5 h-3.5" />,
  reviewer: <UserCheck className="w-3.5 h-3.5" />,
  provider: <User className="w-3.5 h-3.5" />,
}
const ROLE_STYLE: Record<string, string> = {
  admin:    'bg-purple-100 text-purple-700',
  reviewer: 'bg-blue-100 text-blue-700',
  provider: 'bg-gray-100 text-gray-700',
}

function initForm(): CreateUserPayload {
  return { email: '', username: '', password: '', role: 'provider', organization: '' }
}

export default function UserManagementPage() {
  const [search, setSearch]     = useState('')
  const [roleFilter, setRole]   = useState('All')
  const [showModal, setShowModal] = useState(false)
  const [form, setForm]         = useState<CreateUserPayload>(initForm)
  const [submitting, setSubmit] = useState(false)
  const [formError, setFormErr] = useState<string | null>(null)
  const [success, setSuccess]   = useState<string | null>(null)
  const [newUsers, setNewUsers] = useState<UserPublic[]>([])

  const allUsers = [...PLACEHOLDER_USERS, ...newUsers]

  const filtered = allUsers.filter((u) => {
    const q = search.toLowerCase()
    const matchSearch = !search || u.username.includes(q) || u.email.includes(q)
    const matchRole   = roleFilter === 'All' || u.role === roleFilter.toLowerCase()
    return matchSearch && matchRole
  })

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }))
  }

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault()
    setFormErr(null)
    setSubmit(true)
    try {
      const created = await usersService.createUser({
        ...form,
        organization: form.organization || undefined,
      })
      setNewUsers((u) => [...u, created])
      setSuccess(`User "${created.username}" created successfully.`)
      setForm(initForm())
      setTimeout(() => setShowModal(false), 1500)
    } catch (err: any) {
      setFormErr(err?.message ?? 'Failed to create user')
    } finally {
      setSubmit(false)
    }
  }

  return (
    <div>
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">User Management</h1>
          <p className="page-subtitle">{filtered.length} user{filtered.length !== 1 ? 's' : ''}</p>
        </div>
        <button onClick={() => { setShowModal(true); setFormErr(null); setSuccess(null) }} className="btn-primary">
          <Plus className="w-4 h-4" />
          Add User
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-5">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by username or email…"
            className="input pl-9 w-64"
          />
        </div>
        <select value={roleFilter} onChange={(e) => setRole(e.target.value)} className="input w-auto">
          {['All', 'Provider', 'Reviewer', 'Admin'].map((r) => <option key={r}>{r}</option>)}
        </select>
      </div>

      <div className="card overflow-hidden">
        <table className="data-table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Email</th>
              <th>Role</th>
              <th>Organization</th>
              <th>Status</th>
              <th>Joined</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((u) => (
              <tr key={u.user_id}>
                <td className="font-medium text-gray-900">{u.username}</td>
                <td className="text-gray-500 text-sm">{u.email}</td>
                <td>
                  <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium capitalize ${ROLE_STYLE[u.role]}`}>
                    {ROLE_ICON[u.role]}
                    {u.role}
                  </span>
                </td>
                <td className="text-gray-500 text-sm">{u.organization || '—'}</td>
                <td>
                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                    u.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                  }`}>
                    {u.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="text-gray-500 text-sm">
                  {new Date(u.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add User Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h2 className="text-base font-semibold text-gray-900">Add New User</h2>
              <button onClick={() => setShowModal(false)} className="p-1 text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="px-6 py-5 space-y-4">
              {formError && (
                <div className="flex items-center gap-2 px-3 py-2 bg-red-50 border border-red-100 rounded text-sm text-red-700">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  {formError}
                </div>
              )}
              {success && (
                <div className="flex items-center gap-2 px-3 py-2 bg-green-50 border border-green-100 rounded text-sm text-green-700">
                  <CheckCircle className="w-4 h-4 shrink-0" />
                  {success}
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Email *</label>
                  <input name="email" type="email" value={form.email} onChange={handleChange} className="input" required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Username *</label>
                  <input name="username" value={form.username} onChange={handleChange} className="input" minLength={3} required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Role *</label>
                  <select name="role" value={form.role} onChange={handleChange} className="input">
                    <option value="provider">Provider</option>
                    <option value="reviewer">Reviewer</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Password *</label>
                  <input
                    name="password"
                    type="password"
                    value={form.password}
                    onChange={handleChange}
                    className="input"
                    minLength={12}
                    placeholder="Min 12 chars, upper + lower + digit + special"
                    required
                  />
                </div>
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Organization</label>
                  <input name="organization" value={form.organization ?? ''} onChange={handleChange} className="input" placeholder="Optional" />
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <button type="submit" disabled={submitting} className="btn-primary flex-1 disabled:opacity-60">
                  {submitting ? 'Creating…' : 'Create User'}
                </button>
                <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
