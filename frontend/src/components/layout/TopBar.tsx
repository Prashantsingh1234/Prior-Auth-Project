import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  Bell, Sun, Moon, Monitor, Search, Brain,
  ChevronDown, LogOut, Settings, User, Keyboard, Menu, X,
  Sparkles,
} from 'lucide-react'
import { useUIStore } from '@/store/uiStore'
import { useAuthStore } from '@/store/authStore'
import { useLogout } from '@/features/auth/hooks/useLogout'
import { useBreakpoint } from '@/hooks/useBreakpoint'
import { useHealth } from '@/hooks/useHealth'
import { cn } from '@/lib/utils'
import { ROUTES } from '@/config/routes.config'

export function TopBar() {
  const {
    theme, setTheme,
    unreadCount,
    commandOpen, setCommandOpen,
    notificationsPanelOpen, setNotificationsPanelOpen,
    aiPanelOpen, setAIPanelOpen,
    toggleMobileSidebar,
  } = useUIStore()

  const user    = useAuthStore((s) => s.user)
  const logout  = useLogout()
  const navigate = useNavigate()
  const isMd    = useBreakpoint('md')
  const health  = useHealth()

  const [userMenuOpen,   setUserMenuOpen]   = useState(false)
  const [searchExpanded, setSearchExpanded] = useState(false)
  const userMenuRef   = useRef<HTMLDivElement>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)

  // Close user menu on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Focus search input when expanded on mobile
  useEffect(() => {
    if (searchExpanded && !isMd) {
      setTimeout(() => searchInputRef.current?.focus(), 50)
    }
  }, [searchExpanded, isMd])

  const themeOptions: { value: 'light' | 'dark' | 'system'; icon: React.ElementType; label: string }[] = [
    { value: 'light',  icon: Sun,     label: 'Light'  },
    { value: 'dark',   icon: Moon,    label: 'Dark'   },
    { value: 'system', icon: Monitor, label: 'System' },
  ]

  return (
    <header
      className="h-14 flex items-center px-3 sm:px-4 gap-2 sm:gap-3 flex-shrink-0 sticky top-0 z-20"
      style={{
        background:   'var(--surface)',
        borderBottom: '1px solid var(--border)',
        backdropFilter: 'blur(12px)',
      }}
    >
      {/* Mobile hamburger */}
      <button
        onClick={toggleMobileSidebar}
        className="p-2 rounded-xl text-[var(--text-2)] hover:bg-[var(--elevated)] transition-colors md:hidden flex-shrink-0"
        aria-label="Open menu"
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* Mobile expanded search overlay */}
      <AnimatePresence>
        {searchExpanded && !isMd && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 z-10 flex items-center px-3 gap-2"
            style={{ background: 'var(--surface)' }}
          >
            <Search className="w-4 h-4 text-[var(--text-4)] flex-shrink-0" />
            <input
              ref={searchInputRef}
              placeholder="Search or jump to…"
              className="flex-1 bg-transparent text-sm text-[var(--text-1)] placeholder-[var(--text-4)] focus:outline-none"
              onKeyDown={(e) => { if (e.key === 'Escape') setSearchExpanded(false) }}
            />
            <button
              onClick={() => setSearchExpanded(false)}
              className="p-1.5 rounded-lg text-[var(--text-4)] hover:text-[var(--text-2)]"
            >
              <X className="w-4 h-4" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Desktop search / command palette trigger */}
      <button
        onClick={() => isMd ? setCommandOpen(!commandOpen) : setSearchExpanded(true)}
        className={cn(
          'flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm text-[var(--text-3)]',
          'hover:text-[var(--text-2)] hover:bg-[var(--elevated)] border border-[var(--border)] transition-all group',
          'hidden sm:flex flex-1 max-w-xs',
        )}
      >
        <Search className="w-3.5 h-3.5 text-[var(--text-4)]" />
        <span className="flex-1 text-left">Search or jump to…</span>
        <div className="flex items-center gap-1 opacity-60 group-hover:opacity-100 transition-opacity">
          <kbd className="text-[10px] font-mono bg-[var(--elevated)] border border-[var(--border)] px-1.5 py-0.5 rounded hidden lg:inline">
            ⌘K
          </kbd>
        </div>
      </button>

      {/* Mobile search icon (visible when not expanded) */}
      <button
        onClick={() => setSearchExpanded(true)}
        className="p-2 rounded-xl text-[var(--text-2)] hover:bg-[var(--elevated)] transition-colors sm:hidden"
        aria-label="Search"
      >
        <Search className="w-4 h-4" />
      </button>

      <div className="flex-1" />

      {/* System health pill — desktop only */}
      <AnimatePresence>
        {isMd && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className="hidden lg:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-[11px] font-medium"
            style={{
              background: health.isUnhealthy
                ? 'rgba(239,68,68,0.08)' : health.isDegraded
                ? 'rgba(245,158,11,0.08)' : 'rgba(16,185,129,0.07)',
              borderColor: health.isUnhealthy
                ? 'rgba(239,68,68,0.2)' : health.isDegraded
                ? 'rgba(245,158,11,0.2)' : 'rgba(16,185,129,0.2)',
              color: health.isUnhealthy ? '#ef4444' : health.isDegraded ? '#f59e0b' : '#10b981',
            }}
          >
            <span
              className={cn('health-dot', health.isUnhealthy ? 'health-dot-down' : health.isDegraded ? 'health-dot-degraded' : 'health-dot-ok')}
            />
            {health.isUnhealthy ? 'System Degraded' : health.isDegraded ? 'Partial Outage' : 'Operational'}
          </motion.div>
        )}
      </AnimatePresence>

      {/* AI Assistant toggle — premium gradient when active */}
      <motion.button
        onClick={() => setAIPanelOpen(!aiPanelOpen)}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.97 }}
        className={cn(
          'flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-xl text-xs font-medium transition-all border',
          aiPanelOpen
            ? 'text-white border-transparent'
            : 'text-[var(--text-2)] border-[var(--border)] hover:bg-[var(--elevated)] hover:text-violet-400 hover:border-violet-500/25',
        )}
        style={aiPanelOpen ? {
          background: 'linear-gradient(135deg, rgba(139,92,246,0.85) 0%, rgba(14,165,233,0.85) 100%)',
          boxShadow: '0 0 20px rgba(139,92,246,0.3), 0 2px 8px rgba(0,0,0,0.2)',
        } : {}}
      >
        <motion.div
          animate={aiPanelOpen ? {
            rotate: [0, 15, -10, 5, 0],
          } : {}}
          transition={{ duration: 0.5, ease: 'easeInOut' }}
        >
          {aiPanelOpen ? <Sparkles className="w-3.5 h-3.5" /> : <Brain className="w-3.5 h-3.5" />}
        </motion.div>
        <span className="hidden sm:inline">{aiPanelOpen ? 'AI Active' : 'AI Assistant'}</span>
      </motion.button>

      {/* Theme toggle — hidden on small mobile */}
      <div className="hidden sm:flex items-center gap-0.5 bg-[var(--elevated)] rounded-lg p-1 border border-[var(--border)]">
        {themeOptions.map(({ value, icon: Icon, label }) => (
          <button
            key={value}
            onClick={() => setTheme(value)}
            title={label}
            className={cn(
              'p-1.5 rounded-md transition-all',
              theme === value
                ? 'bg-[var(--surface)] text-[var(--text-1)] shadow-sm'
                : 'text-[var(--text-4)] hover:text-[var(--text-2)]',
            )}
          >
            <Icon className="w-3.5 h-3.5" />
          </button>
        ))}
      </div>

      {/* Notifications */}
      <button
        onClick={() => setNotificationsPanelOpen(!notificationsPanelOpen)}
        className={cn(
          'relative p-2 rounded-xl transition-all',
          notificationsPanelOpen
            ? 'bg-cyan-500/15 text-cyan-400'
            : 'text-[var(--text-2)] hover:bg-[var(--elevated)] hover:text-[var(--text-1)]',
        )}
        aria-label="Notifications"
      >
        <Bell className="w-4 h-4" />
        <AnimatePresence>
          {unreadCount > 0 && (
            <motion.span
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0 }}
              className="absolute top-1 right-1 min-w-[16px] h-4 px-0.5 rounded-full bg-cyan-500 text-white text-[9px] flex items-center justify-center font-bold leading-none"
            >
              {unreadCount > 9 ? '9+' : unreadCount}
            </motion.span>
          )}
        </AnimatePresence>
      </button>

      {/* Keyboard shortcut hint — desktop only */}
      <button
        onClick={() => setCommandOpen(true)}
        className="p-2 rounded-xl text-[var(--text-4)] hover:text-[var(--text-2)] hover:bg-[var(--elevated)] transition-all hidden lg:flex"
        title="Keyboard shortcuts"
      >
        <Keyboard className="w-4 h-4" />
      </button>

      {/* User menu */}
      <div ref={userMenuRef} className="relative">
        <button
          onClick={() => setUserMenuOpen((v) => !v)}
          className="flex items-center gap-2 px-2 py-1.5 rounded-xl hover:bg-[var(--elevated)] transition-colors group"
        >
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
            style={{ background: 'linear-gradient(135deg, rgba(14,165,233,0.9), rgba(139,92,246,0.9))' }}
          >
            {user?.name?.[0]?.toUpperCase() ?? 'U'}
          </div>
          <div className="hidden sm:block text-left">
            <p className="text-xs font-medium text-[var(--text-1)] leading-none">{user?.name ?? 'User'}</p>
            <p className="text-[10px] text-[var(--text-4)] capitalize mt-0.5">{user?.role ?? 'reviewer'}</p>
          </div>
          <ChevronDown className={cn('w-3.5 h-3.5 text-[var(--text-4)] transition-transform hidden sm:block', userMenuOpen && 'rotate-180')} />
        </button>

        <AnimatePresence>
          {userMenuOpen && (
            <motion.div
              initial={{ opacity: 0, y: -8, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.95 }}
              transition={{ duration: 0.12 }}
              className="absolute right-0 top-full mt-2 w-48 rounded-xl overflow-hidden shadow-card-lg z-50"
              style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            >
              <div className="px-4 py-3 border-b border-[var(--border)]">
                <p className="text-sm font-semibold text-[var(--text-1)]">{user?.name}</p>
                <p className="text-xs text-[var(--text-3)] mt-0.5">{user?.email}</p>
                <span
                  className="inline-block mt-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium capitalize"
                  style={{ background: 'rgba(14,165,233,0.1)', color: 'rgba(14,165,233,0.9)' }}
                >
                  {user?.role}
                </span>
              </div>

              {[
                { icon: User,     label: 'Profile',  onClick: () => { navigate(ROUTES.SETTINGS); setUserMenuOpen(false) } },
                { icon: Settings, label: 'Settings', onClick: () => { navigate(ROUTES.SETTINGS); setUserMenuOpen(false) } },
              ].map(({ icon: Icon, label, onClick }) => (
                <button
                  key={label}
                  onClick={onClick}
                  className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-[var(--text-2)] hover:bg-[var(--elevated)] hover:text-[var(--text-1)] transition-colors"
                >
                  <Icon className="w-4 h-4" />
                  {label}
                </button>
              ))}

              <div className="border-t border-[var(--border)]" />

              <button
                onClick={() => { logout(); setUserMenuOpen(false) }}
                className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-[var(--text-2)] hover:bg-red-500/10 hover:text-red-400 transition-colors"
              >
                <LogOut className="w-4 h-4" />
                Sign out
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </header>
  )
}
