import { NavLink } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, FileText, BarChart3, Shield, BookOpen,
  ChevronLeft, ChevronRight, Activity, Lock, LogOut,
  Settings, Stethoscope, Users, ClipboardList,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useUIStore } from '@/store/uiStore'
import { useAuthStore } from '@/store/authStore'
import { useLogout } from '@/features/auth/hooks/useLogout'
import { usePermissions } from '@/hooks'
import type { Permission, UserRole } from '@/types'

// ─── Nav item definitions ─────────────────────────────────────────────────────

interface NavItem {
  to:         string
  icon:       React.ElementType
  label:      string
  permission?: Permission
  roles?:     UserRole[]
  badge?:     string | null
}

const PRIMARY_NAV: NavItem[] = [
  {
    to: '/dashboard',
    icon: LayoutDashboard,
    label: 'Dashboard',
  },
  {
    to: '/cases',
    icon: ClipboardList,
    label: 'Case Queue',
    permission: 'cases:read',
  },
  {
    to: '/analytics',
    icon: BarChart3,
    label: 'AI Analytics',
    permission: 'analytics:read',
  },
  {
    to: '/policies',
    icon: BookOpen,
    label: 'Policies',
    permission: 'policies:read',
  },
  {
    to: '/audit',
    icon: FileText,
    label: 'Audit Log',
    permission: 'audit:read',
  },
]

const ADMIN_NAV: NavItem[] = [
  {
    to: '/admin/users',
    icon: Users,
    label: 'User Management',
    permission: 'admin:users',
  },
  {
    to: '/settings',
    icon: Settings,
    label: 'Settings',
    permission: 'admin:settings',
  },
]

// ─── Sub-components ───────────────────────────────────────────────────────────

interface NavButtonProps {
  item:      NavItem
  collapsed: boolean
  visible:   boolean
}

function NavButton({ item: { to, icon: Icon, label, badge }, collapsed, visible }: NavButtonProps) {
  if (!visible) return null
  return (
    <NavLink key={to} to={to} end={to === '/dashboard'}>
      {({ isActive }) => (
        <motion.div
          whileHover={{ x: collapsed ? 0 : 2 }}
          whileTap={{ scale: 0.97 }}
          className={cn(
            'group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors relative cursor-pointer',
            isActive
              ? 'text-cyan-400 font-medium'
              : 'text-[var(--text-2)] hover:bg-[var(--elevated)] hover:text-[var(--text-1)]',
          )}
        >
          {/* Active indicator */}
          {isActive && (
            <motion.div
              layoutId="nav-indicator"
              className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-cyan-400 rounded-full"
              style={{ boxShadow: '0 0 8px rgba(14,165,233,0.6)' }}
            />
          )}

          {/* Active background */}
          {isActive && (
            <motion.div
              layoutId="nav-bg"
              className="absolute inset-0 rounded-lg"
              style={{ background: 'rgba(14,165,233,0.08)' }}
            />
          )}

          <Icon className="w-4 h-4 flex-shrink-0 relative z-10" />

          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: 'auto' }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ duration: 0.15 }}
                className="flex-1 flex items-center justify-between overflow-hidden relative z-10"
              >
                <span className="whitespace-nowrap">{label}</span>
                {badge && (
                  <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-cyan-500/20 text-cyan-400 font-semibold flex-shrink-0">
                    {badge}
                  </span>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}
    </NavLink>
  )
}

// ─── Main Sidebar ─────────────────────────────────────────────────────────────

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useUIStore()
  const { user } = useAuthStore()
  const { can } = usePermissions()
  const logout = useLogout()

  const collapsed = sidebarCollapsed

  function isVisible(item: NavItem): boolean {
    if (item.permission && !can(item.permission)) return false
    if (item.roles && !item.roles.includes(user?.role as UserRole)) return false
    return true
  }

  const visibleAdmin = ADMIN_NAV.filter(isVisible)

  return (
    <motion.aside
      animate={{ width: collapsed ? 64 : 256 }}
      transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
      className="fixed left-0 top-0 h-full z-30 flex flex-col overflow-hidden"
      style={{
        background: 'var(--surface)',
        borderRight: '1px solid var(--border)',
      }}
    >
      {/* Logo */}
      <div className="flex items-center h-16 px-4 border-b border-[var(--border)] gap-3 flex-shrink-0">
        <motion.div
          className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{
            background: 'linear-gradient(135deg, rgba(14,165,233,0.3), rgba(139,92,246,0.3))',
            border: '1px solid rgba(14,165,233,0.3)',
            boxShadow: '0 0 12px rgba(14,165,233,0.2)',
          }}
          animate={{ boxShadow: ['0 0 8px rgba(14,165,233,0.15)', '0 0 16px rgba(14,165,233,0.3)', '0 0 8px rgba(14,165,233,0.15)'] }}
          transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
        >
          <Stethoscope className="w-4 h-4 text-cyan-400" />
        </motion.div>
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.12 }}
              className="overflow-hidden"
            >
              <p className="text-sm font-bold text-[var(--text-1)] whitespace-nowrap leading-none">PA Review</p>
              <p className="text-[10px] text-[var(--text-4)] whitespace-nowrap mt-0.5">AI Platform</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* System status */}
      <AnimatePresence>
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mx-3 mt-3 px-3 py-2 rounded-lg flex items-center gap-2"
            style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)' }}
          >
            <Activity className="w-3 h-3 text-emerald-400 flex-shrink-0" />
            <span className="text-[11px] text-emerald-400 font-medium">All systems operational</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Primary navigation */}
      <nav className="flex-1 px-2 py-4 space-y-0.5 overflow-y-auto overflow-x-hidden">
        {PRIMARY_NAV.map((item) => (
          <NavButton key={item.to} item={item} collapsed={collapsed} visible={isVisible(item)} />
        ))}

        {/* Admin section */}
        {visibleAdmin.length > 0 && (
          <>
            <AnimatePresence>
              {!collapsed && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="pt-3 pb-1 px-3"
                >
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-4)]">
                    Admin
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
            {collapsed && <div className="my-2 mx-3 border-t border-[var(--border)]" />}
            {visibleAdmin.map((item) => (
              <NavButton key={item.to} item={item} collapsed={collapsed} visible={true} />
            ))}
          </>
        )}
      </nav>

      {/* Divider */}
      <div className="mx-3 border-t border-[var(--border)]" />

      {/* HIPAA badge */}
      <AnimatePresence>
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mx-3 my-2 px-3 py-2 rounded-lg flex items-center gap-2"
            style={{ background: 'var(--elevated)' }}
          >
            <Lock className="w-3 h-3 text-[var(--text-4)] flex-shrink-0" />
            <span className="text-[10px] text-[var(--text-4)]">HIPAA Compliant · SOC 2</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* User card */}
      <div className={cn('px-2 mx-1 py-2 rounded-lg', !collapsed && 'bg-[var(--elevated)] mb-1 mx-2')}>
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
               style={{ background: 'linear-gradient(135deg, rgba(14,165,233,0.8), rgba(139,92,246,0.8))' }}>
            {user?.name?.[0]?.toUpperCase() ?? 'U'}
          </div>
          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex-1 min-w-0"
              >
                <p className="text-xs font-medium text-[var(--text-1)] truncate leading-none">{user?.name ?? 'User'}</p>
                <p className="text-[10px] text-[var(--text-3)] capitalize mt-0.5">{user?.role ?? 'reviewer'}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Bottom actions */}
      <div className="px-2 pb-3 space-y-0.5">
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-[var(--text-2)] hover:bg-red-500/10 hover:text-red-400 transition-colors"
        >
          <LogOut className="w-4 h-4 flex-shrink-0" />
          <AnimatePresence>
            {!collapsed && (
              <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="whitespace-nowrap text-sm">
                Sign out
              </motion.span>
            )}
          </AnimatePresence>
        </button>

        <button
          onClick={toggleSidebar}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-[var(--text-3)] hover:bg-[var(--elevated)] hover:text-[var(--text-2)] transition-colors"
        >
          {collapsed
            ? <ChevronRight className="w-4 h-4 flex-shrink-0" />
            : <ChevronLeft className="w-4 h-4 flex-shrink-0" />
          }
          <AnimatePresence>
            {!collapsed && (
              <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="whitespace-nowrap text-sm">
                Collapse
              </motion.span>
            )}
          </AnimatePresence>
        </button>
      </div>
    </motion.aside>
  )
}
