import { memo, useCallback } from 'react'
import { NavLink } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, FileText, BarChart3, BookOpen,
  ChevronLeft, ChevronRight, Activity, LogOut,
  Settings, Users, ClipboardList, Brain, Upload, MessageCircle, Radio, MonitorDot, Table2, X,
  Shield,
} from 'lucide-react'
import { AIPulse } from '@/components/animations/AIPulse'
import { cn } from '@/lib/utils'
import { useUIStore } from '@/store/uiStore'
import { useAuthStore } from '@/store/authStore'
import { useLogout } from '@/features/auth/hooks/useLogout'
import { usePermissions } from '@/hooks'
import { useBreakpoint } from '@/hooks/useBreakpoint'
import { useHealth } from '@/hooks/useHealth'
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

interface NavGroup {
  label:  string
  items:  NavItem[]
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'OPERATIONS',
    items: [
      { to: '/dashboard',      icon: LayoutDashboard, label: 'Dashboard' },
      { to: '/cases',          icon: ClipboardList,   label: 'Case Queue',     permission: 'cases:read' },
      { to: '/workflow',       icon: Radio,           label: 'Mission Control', permission: 'cases:read' },
      { to: '/clarifications', icon: MessageCircle,   label: 'Clarifications', permission: 'cases:read', badge: '2' },
    ],
  },
  {
    label: 'INTELLIGENCE',
    items: [
      { to: '/analytics',  icon: BarChart3,  label: 'AI Analytics',  permission: 'analytics:read' },
      { to: '/reasoning',  icon: Brain,      label: 'AI Reasoning',  permission: 'cases:read' },
      { to: '/monitoring', icon: MonitorDot, label: 'AI Monitoring', permission: 'analytics:read' },
      { to: '/realtime',   icon: Activity,   label: 'Live Updates',  permission: 'cases:read' },
    ],
  },
  {
    label: 'DOCUMENTS',
    items: [
      { to: '/ingestion', icon: Upload,   label: 'Doc Intelligence', permission: 'cases:read' },
      { to: '/policies',  icon: BookOpen, label: 'Policies',         permission: 'policies:read' },
    ],
  },
  {
    label: 'DATA',
    items: [
      { to: '/tables', icon: Table2,   label: 'Data Tables', permission: 'cases:read' },
      { to: '/audit',  icon: FileText, label: 'Audit Log',   permission: 'audit:read' },
    ],
  },
]

const ADMIN_NAV: NavItem[] = [
  { to: '/admin/users', icon: Users,    label: 'User Management', permission: 'admin:users' },
  { to: '/settings',    icon: Settings, label: 'Settings',        permission: 'admin:settings' },
]

// ─── Nav button ───────────────────────────────────────────────────────────────

interface NavButtonProps {
  item:       NavItem
  collapsed:  boolean
  visible:    boolean
  onClose?:   () => void
  onPrefetch?: (route: string) => void
}

const NavButton = memo(function NavButton({ item: { to, icon: Icon, label, badge }, collapsed, visible, onClose, onPrefetch }: NavButtonProps) {
  if (!visible) return null
  return (
    <NavLink
      to={to}
      end={to === '/dashboard'}
      onClick={onClose}
      onMouseEnter={() => onPrefetch?.(to)}
      onFocus={() => onPrefetch?.(to)}
      aria-label={collapsed ? label : undefined}
    >
      {({ isActive }) => (
        <motion.div
          whileHover={{ x: collapsed ? 0 : 2 }}
          whileTap={{ scale: 0.97 }}
          aria-current={isActive ? 'page' : undefined}
          className={cn(
            'group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors relative cursor-pointer',
            'min-h-[44px] md:min-h-0',
            isActive
              ? 'text-cyan-400 font-medium'
              : 'text-[var(--text-2)] hover:bg-[var(--elevated)] hover:text-[var(--text-1)]',
          )}
        >
          {isActive && (
            <motion.div
              layoutId="nav-indicator"
              className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-cyan-400 rounded-full"
              style={{ boxShadow: '0 0 8px rgba(14,165,233,0.6)' }}
            />
          )}
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
})

// ─── Main Sidebar ─────────────────────────────────────────────────────────────

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useUIStore()
  const mobileSidebarOpen    = useUIStore((s) => s.mobileSidebarOpen)
  const setMobileSidebarOpen = useUIStore((s) => s.setMobileSidebarOpen)
  const { user }  = useAuthStore()
  const { can }   = usePermissions()
  const logout    = useLogout()
  const isDesktop = useBreakpoint('md')
  const health    = useHealth()

  const collapsed = isDesktop ? sidebarCollapsed : false

  const isVisible = useCallback((item: NavItem): boolean => {
    if (item.permission && !can(item.permission)) return false
    if (item.roles && !item.roles.includes(user?.role as UserRole)) return false
    return true
  }, [can, user?.role])

  const visibleAdmin = ADMIN_NAV.filter(isVisible)

  const handleNavClose = useCallback(() => {
    if (!isDesktop) setMobileSidebarOpen(false)
  }, [isDesktop, setMobileSidebarOpen])

  const handlePrefetch = useCallback((route: string) => {
    const chunkMap: Record<string, () => Promise<unknown>> = {
      '/dashboard':      () => import('@/features/dashboard/DashboardPage'),
      '/cases':          () => import('@/features/cases/pages/CaseListPage'),
      '/analytics':      () => import('@/features/analytics/pages/AnalyticsDashboard'),
      '/audit':          () => import('@/features/audit/AuditLogPage'),
      '/policies':       () => import('@/features/policies/PoliciesPage'),
      '/monitoring':     () => import('@/features/monitoring/MonitoringPage'),
      '/ingestion':      () => import('@/features/ingestion/DocumentIntelligencePage'),
      '/reasoning':      () => import('@/features/reasoning/ReasoningPage'),
      '/clarifications': () => import('@/features/clarifications/ClarificationPage'),
    }
    chunkMap[route]?.().catch(() => {})
  }, [])

  // Animation: desktop = width, mobile = x translate
  const animateProps = isDesktop
    ? { width: collapsed ? 64 : 256, x: 0 }
    : { width: 256, x: mobileSidebarOpen ? 0 : -256 }

  const healthColor  = health.isUnhealthy ? '#ef4444' : health.isDegraded ? '#f59e0b' : '#10b981'
  const healthLabel  = health.isUnhealthy ? 'System degraded' : health.isDegraded ? 'Partial outage' : 'All systems operational'
  const healthRingCls = health.isUnhealthy ? 'status-ring-offline' : health.isDegraded ? 'status-ring-degraded' : 'status-ring-online'

  return (
    <motion.aside
      animate={animateProps}
      transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
      className="fixed left-0 top-0 h-full z-30 flex flex-col overflow-hidden"
      style={{
        background:  'var(--surface)',
        borderRight: '1px solid var(--border)',
      }}
    >
      {/* Brand mark + mobile close */}
      <div className="flex items-center h-16 px-4 border-b border-[var(--border)] gap-3 flex-shrink-0">
        {/* Premium layered logo mark */}
        <motion.div
          className="relative w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{
            background: 'linear-gradient(145deg, rgba(14,165,233,0.25) 0%, rgba(139,92,246,0.25) 100%)',
            border: '1px solid rgba(14,165,233,0.25)',
            boxShadow: '0 0 0 1px rgba(139,92,246,0.1) inset',
          }}
          animate={{
            boxShadow: [
              '0 0 8px rgba(14,165,233,0.12), 0 0 0 1px rgba(139,92,246,0.1) inset',
              '0 0 18px rgba(14,165,233,0.28), 0 0 0 1px rgba(139,92,246,0.15) inset',
              '0 0 8px rgba(14,165,233,0.12), 0 0 0 1px rgba(139,92,246,0.1) inset',
            ],
          }}
          transition={{ duration: 3.5, repeat: Infinity, ease: 'easeInOut' }}
        >
          {/* Layered icon: cross + neural dot */}
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <rect x="6.5" y="2" width="3" height="12" rx="1.5" fill="url(#brandGrad)" />
            <rect x="2" y="6.5" width="12" height="3" rx="1.5" fill="url(#brandGrad)" />
            <circle cx="8" cy="8" r="2" fill="url(#brandGrad2)" opacity="0.9" />
            <defs>
              <linearGradient id="brandGrad" x1="0" y1="0" x2="16" y2="16" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#0ea5e9" />
                <stop offset="100%" stopColor="#8b5cf6" />
              </linearGradient>
              <linearGradient id="brandGrad2" x1="0" y1="0" x2="16" y2="16" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.9" />
              </linearGradient>
            </defs>
          </svg>
        </motion.div>

        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.12 }}
              className="overflow-hidden flex-1"
            >
              <p
                className="text-sm font-bold whitespace-nowrap leading-none text-gradient-brand"
                style={{ fontFamily: 'Manrope, sans-serif', letterSpacing: '-0.01em' }}
              >
                ClinicalAI
              </p>
              <p className="text-[10px] text-[var(--text-4)] whitespace-nowrap mt-0.5 tracking-wide">
                Utilization Management
              </p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Mobile close button */}
        {!isDesktop && (
          <button
            onClick={() => setMobileSidebarOpen(false)}
            className="ml-auto p-2 rounded-lg text-[var(--text-4)] hover:bg-[var(--elevated)] hover:text-[var(--text-1)] transition-colors"
            aria-label="Close menu"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* System health status */}
      <AnimatePresence>
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mx-3 mt-3 px-3 py-2 rounded-lg flex items-center gap-2"
            style={{
              background: health.isUnhealthy ? 'rgba(239,68,68,0.07)' : health.isDegraded ? 'rgba(245,158,11,0.07)' : 'rgba(16,185,129,0.07)',
              border: `1px solid ${healthColor}28`,
            }}
          >
            <AIPulse size={6} color={healthColor} rings={2} />
            <span className="text-[11px] font-medium" style={{ color: healthColor }}>{healthLabel}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Primary navigation — grouped */}
      <nav aria-label="Main navigation" className="flex-1 px-2 overflow-y-auto overflow-x-hidden">
        {NAV_GROUPS.map((group) => {
          const visibleItems = group.items.filter(isVisible)
          if (visibleItems.length === 0) return null
          return (
            <div key={group.label}>
              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.1 }}
                    className="nav-section-label"
                  >
                    {group.label}
                  </motion.span>
                )}
              </AnimatePresence>
              {collapsed && <div className="my-2 h-px bg-[var(--border)] mx-2 first:hidden" />}
              <div className="space-y-0.5 pb-1">
                {visibleItems.map((item) => (
                  <NavButton
                    key={item.to}
                    item={item}
                    collapsed={collapsed}
                    visible={true}
                    onClose={handleNavClose}
                    onPrefetch={handlePrefetch}
                  />
                ))}
              </div>
            </div>
          )
        })}

        {visibleAdmin.length > 0 && (
          <>
            <AnimatePresence>
              {!collapsed && (
                <motion.span
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="nav-section-label"
                >
                  ADMIN
                </motion.span>
              )}
            </AnimatePresence>
            {collapsed && <div className="my-2 h-px bg-[var(--border)] mx-2" />}
            <div className="space-y-0.5 pb-1">
              {visibleAdmin.map((item) => (
                <NavButton
                  key={item.to}
                  item={item}
                  collapsed={collapsed}
                  visible={true}
                  onClose={handleNavClose}
                  onPrefetch={handlePrefetch}
                />
              ))}
            </div>
          </>
        )}
      </nav>

      {/* Divider */}
      <div className="mx-3 border-t border-[var(--border)]" />

      {/* HIPAA / compliance badge */}
      <AnimatePresence>
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mx-3 my-2 px-3 py-1.5 rounded-lg flex items-center gap-2"
            style={{ background: 'var(--elevated)' }}
          >
            <Shield className="w-3 h-3 text-[var(--text-4)] flex-shrink-0" />
            <span className="text-[10px] text-[var(--text-4)]">HIPAA Compliant · SOC 2 Type II</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* User card */}
      <div className={cn('px-2 py-2', !collapsed && 'bg-[var(--elevated)] mb-1 mx-2 rounded-xl')}>
        <div className="flex items-center gap-2.5 px-1">
          <div className={cn('status-ring', healthRingCls, 'flex-shrink-0')}>
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-bold"
              style={{ background: 'linear-gradient(135deg, rgba(14,165,233,0.85), rgba(139,92,246,0.85))' }}
            >
              {user?.name?.[0]?.toUpperCase() ?? 'U'}
            </div>
          </div>
          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex-1 min-w-0"
              >
                <p className="text-xs font-semibold text-[var(--text-1)] truncate leading-none">{user?.name ?? 'User'}</p>
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
          aria-label="Sign out"
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

        {/* Collapse toggle — desktop only */}
        {isDesktop && (
          <button
            onClick={toggleSidebar}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-expanded={!collapsed}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-[var(--text-3)] hover:bg-[var(--elevated)] hover:text-[var(--text-2)] transition-colors"
          >
            {collapsed
              ? <ChevronRight className="w-4 h-4 flex-shrink-0" />
              : <ChevronLeft  className="w-4 h-4 flex-shrink-0" />
            }
            <AnimatePresence>
              {!collapsed && (
                <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="whitespace-nowrap text-sm">
                  Collapse
                </motion.span>
              )}
            </AnimatePresence>
          </button>
        )}
      </div>
    </motion.aside>
  )
}
