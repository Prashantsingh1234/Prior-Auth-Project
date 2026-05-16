import { NavLink, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard,
  Brain,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  Activity,
  Shield,
  LogOut,
  Settings,
  Stethoscope,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useUIStore } from '@/store/uiStore'
import { useAuthStore } from '@/store/authStore'

const NAV = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Case Queue', badge: null },
  { to: '/analytics', icon: BarChart3, label: 'AI Analytics', badge: null },
]

const BOTTOM_NAV = [
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useUIStore()
  const { user, clearAuth } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    clearAuth()
    navigate('/login')
  }

  return (
    <motion.aside
      animate={{ width: sidebarCollapsed ? 64 : 256 }}
      transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
      className="fixed left-0 top-0 h-full z-30 flex flex-col bg-[var(--surface)] border-r border-[var(--border)] overflow-hidden"
    >
      {/* Logo */}
      <div className="flex items-center h-16 px-4 border-b border-[var(--border)] gap-3 flex-shrink-0">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-violet-600 flex items-center justify-center shadow-glow flex-shrink-0">
          <Stethoscope className="w-4 h-4 text-white" />
        </div>
        <AnimatePresence>
          {!sidebarCollapsed && (
            <motion.div
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.15 }}
              className="overflow-hidden"
            >
              <p className="text-sm font-semibold text-[var(--text-1)] whitespace-nowrap">PA Review</p>
              <p className="text-xs text-[var(--text-3)] whitespace-nowrap">AI Platform</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* System status */}
      <AnimatePresence>
        {!sidebarCollapsed && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="mx-3 mt-3 px-3 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center gap-2"
          >
            <Activity className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
            <span className="text-xs text-emerald-400 font-medium">All systems operational</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-4 space-y-1">
        {NAV.map(({ to, icon: Icon, label, badge }) => (
          <NavLink key={to} to={to}>
            {({ isActive }) => (
              <motion.div
                whileHover={{ x: 2 }}
                whileTap={{ scale: 0.97 }}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors relative',
                  isActive
                    ? 'bg-brand-500/15 text-brand-400 font-medium'
                    : 'text-[var(--text-2)] hover:bg-[var(--elevated)] hover:text-[var(--text-1)]'
                )}
              >
                {isActive && (
                  <motion.div
                    layoutId="nav-indicator"
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-brand-400 rounded-full"
                  />
                )}
                <Icon className="w-4 h-4 flex-shrink-0" />
                <AnimatePresence>
                  {!sidebarCollapsed && (
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="flex-1 whitespace-nowrap"
                    >
                      {label}
                    </motion.span>
                  )}
                </AnimatePresence>
                {badge && !sidebarCollapsed && (
                  <span className="px-1.5 py-0.5 text-xs rounded-full bg-brand-500/20 text-brand-400 font-semibold">
                    {badge}
                  </span>
                )}
              </motion.div>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Divider */}
      <div className="mx-3 border-t border-[var(--border)]" />

      {/* HIPAA Badge */}
      <AnimatePresence>
        {!sidebarCollapsed && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="mx-3 my-3 px-3 py-2 rounded-lg bg-[var(--elevated)] flex items-center gap-2"
          >
            <Shield className="w-3.5 h-3.5 text-[var(--text-3)] flex-shrink-0" />
            <span className="text-xs text-[var(--text-3)]">HIPAA Compliant</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* User + Collapse */}
      <div className="px-2 pb-4 space-y-1">
        {/* User */}
        <div className={cn('flex items-center gap-3 px-3 py-2.5 rounded-lg', !sidebarCollapsed && 'bg-[var(--elevated)]')}>
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-brand-400 to-violet-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
            {user?.name?.[0] ?? 'R'}
          </div>
          <AnimatePresence>
            {!sidebarCollapsed && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex-1 min-w-0"
              >
                <p className="text-xs font-medium text-[var(--text-1)] truncate">{user?.name ?? 'Reviewer'}</p>
                <p className="text-xs text-[var(--text-3)] capitalize">{user?.role ?? 'reviewer'}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Logout */}
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-[var(--text-2)] hover:bg-red-500/10 hover:text-red-400 transition-colors"
        >
          <LogOut className="w-4 h-4 flex-shrink-0" />
          <AnimatePresence>
            {!sidebarCollapsed && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="whitespace-nowrap"
              >
                Sign out
              </motion.span>
            )}
          </AnimatePresence>
        </button>

        {/* Collapse toggle */}
        <button
          onClick={toggleSidebar}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-[var(--text-3)] hover:bg-[var(--elevated)] hover:text-[var(--text-2)] transition-colors"
        >
          {sidebarCollapsed
            ? <ChevronRight className="w-4 h-4 flex-shrink-0" />
            : <ChevronLeft className="w-4 h-4 flex-shrink-0" />
          }
          <AnimatePresence>
            {!sidebarCollapsed && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="whitespace-nowrap"
              >
                Collapse
              </motion.span>
            )}
          </AnimatePresence>
        </button>
      </div>
    </motion.aside>
  )
}