import { NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard, FilePlus, FolderOpen, MessageSquare,
  Users, BookOpen, LogOut,
  ClipboardList, Shield,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

const PROVIDER_NAV: NavItem[] = [
  { to: '/provider/dashboard',      label: 'Dashboard',       icon: LayoutDashboard },
  { to: '/provider/submit',         label: 'Submit Request',  icon: FilePlus },
  { to: '/provider/cases',          label: 'My Cases',        icon: FolderOpen },
  { to: '/provider/clarifications', label: 'Clarifications',  icon: MessageSquare },
]

const REVIEWER_NAV: NavItem[] = [
  { to: '/reviewer/dashboard',      label: 'Dashboard',      icon: LayoutDashboard },
  { to: '/reviewer/queue',          label: 'Case Queue',     icon: ClipboardList },
  { to: '/reviewer/clarifications', label: 'Clarifications', icon: MessageSquare },
]

const ADMIN_NAV: NavItem[] = [
  { to: '/admin/dashboard', label: 'Dashboard',       icon: LayoutDashboard },
  { to: '/admin/users',     label: 'User Management', icon: Users },
  { to: '/admin/policies',  label: 'Policies',        icon: BookOpen },
]

const ROLE_LABELS: Record<string, string> = {
  provider: 'Provider Portal',
  reviewer: 'Reviewer Portal',
  admin:    'Admin Portal',
}

function NavGroup({ title, items }: { title: string; items: NavItem[] }) {
  return (
    <div className="mb-6">
      <p className="px-3 mb-1 text-xs font-semibold text-gray-400 uppercase tracking-wider">{title}</p>
      <nav className="space-y-0.5">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
                isActive
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900',
              )
            }
          >
            <item.icon className="w-4 h-4 shrink-0" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}

export function Sidebar() {
  const user = useAuthStore((s) => s.user)
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const navigate = useNavigate()

  const nav = user?.role === 'reviewer' ? REVIEWER_NAV
            : user?.role === 'admin'    ? ADMIN_NAV
            : PROVIDER_NAV

  function handleLogout() {
    clearAuth()
    navigate('/login')
  }

  return (
    <aside className="w-56 shrink-0 h-full flex flex-col bg-white border-r border-gray-200">

      {/* Brand */}
      <div className="h-14 flex items-center gap-2.5 px-4 border-b border-gray-200">
        <div className="w-7 h-7 rounded bg-blue-600 flex items-center justify-center">
          <Shield className="w-4 h-4 text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold text-gray-900 leading-none">PA Review</p>
          <p className="text-xs text-gray-400 mt-0.5">{ROLE_LABELS[user?.role ?? 'provider']}</p>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto p-3 pt-4">
        <NavGroup title="Menu" items={nav} />
      </div>

      {/* User footer */}
      <div className="border-t border-gray-200 p-3">
        <div className="flex items-center gap-2.5 px-2 py-1.5 mb-1">
          <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center text-xs font-semibold text-blue-700">
            {user?.name?.[0]?.toUpperCase() ?? 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">{user?.name ?? 'User'}</p>
            <p className="text-xs text-gray-400 capitalize">{user?.role}</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm text-gray-600 hover:bg-red-50 hover:text-red-600 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </aside>
  )
}
