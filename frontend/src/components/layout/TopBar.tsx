import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Bell,
  Sun,
  Moon,
  Monitor,
  Search,
  X,
  CheckCircle2,
  AlertTriangle,
  Info,
  ChevronDown,
} from 'lucide-react'
import { useUIStore } from '@/store/uiStore'
import { useAuthStore } from '@/store/authStore'
import { cn, formatRelative } from '@/lib/utils'
import { useNavigate } from 'react-router-dom'

export function TopBar() {
  const { theme, setTheme, notifications, unreadCount, markAllRead, dismissNotification } = useUIStore()
  const user = useAuthStore((s) => s.user)
  const [notifOpen, setNotifOpen] = useState(false)
  const navigate = useNavigate()

  const themeOptions: { value: 'light' | 'dark' | 'system'; icon: React.ElementType }[] = [
    { value: 'light', icon: Sun },
    { value: 'dark', icon: Moon },
    { value: 'system', icon: Monitor },
  ]

  const notifIcon = {
    success: CheckCircle2,
    warning: AlertTriangle,
    info: Info,
    error: AlertTriangle,
  }
  const notifColor = {
    success: 'text-emerald-400',
    warning: 'text-amber-400',
    info: 'text-brand-400',
    error: 'text-red-400',
  }

  return (
    <header className="h-14 border-b border-[var(--border)] bg-[var(--surface)]/80 backdrop-blur-sm flex items-center px-6 gap-4 sticky top-0 z-20">
      {/* Search placeholder */}
      <button
        onClick={() => navigate('/dashboard')}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--elevated)] border border-[var(--border)] text-[var(--text-3)] text-sm hover:text-[var(--text-2)] transition-colors flex-1 max-w-xs"
      >
        <Search className="w-3.5 h-3.5" />
        <span>Search cases…</span>
        <kbd className="ml-auto text-xs bg-[var(--border)] px-1.5 py-0.5 rounded font-mono">⌘K</kbd>
      </button>

      <div className="flex-1" />

      {/* Theme toggle */}
      <div className="flex items-center gap-0.5 bg-[var(--elevated)] rounded-lg p-1 border border-[var(--border)]">
        {themeOptions.map(({ value, icon: Icon }) => (
          <button
            key={value}
            onClick={() => setTheme(value)}
            className={cn(
              'p-1.5 rounded-md transition-colors',
              theme === value
                ? 'bg-[var(--surface)] text-[var(--text-1)] shadow-sm'
                : 'text-[var(--text-3)] hover:text-[var(--text-2)]'
            )}
          >
            <Icon className="w-3.5 h-3.5" />
          </button>
        ))}
      </div>

      {/* Notifications */}
      <div className="relative">
        <button
          onClick={() => { setNotifOpen((v) => !v); if (notifOpen) markAllRead() }}
          className="relative p-2 rounded-lg text-[var(--text-2)] hover:bg-[var(--elevated)] hover:text-[var(--text-1)] transition-colors"
        >
          <Bell className="w-4 h-4" />
          {unreadCount > 0 && (
            <motion.span
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="absolute top-1 right-1 w-4 h-4 rounded-full bg-brand-500 text-white text-[10px] flex items-center justify-center font-bold"
            >
              {unreadCount > 9 ? '9+' : unreadCount}
            </motion.span>
          )}
        </button>

        <AnimatePresence>
          {notifOpen && (
            <motion.div
              initial={{ opacity: 0, y: -8, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="absolute right-0 top-full mt-2 w-80 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-card-lg overflow-hidden z-50"
            >
              <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
                <span className="text-sm font-semibold text-[var(--text-1)]">Notifications</span>
                <button
                  onClick={markAllRead}
                  className="text-xs text-brand-400 hover:text-brand-300 transition-colors"
                >
                  Mark all read
                </button>
              </div>
              <div className="max-h-72 overflow-y-auto">
                {notifications.length === 0 ? (
                  <p className="text-sm text-[var(--text-3)] text-center py-8">No notifications</p>
                ) : (
                  notifications.slice(0, 8).map((n) => {
                    const Icon = notifIcon[n.type]
                    return (
                      <motion.div
                        key={n.id}
                        layout
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0, x: 20 }}
                        className={cn(
                          'flex items-start gap-3 px-4 py-3 border-b border-[var(--border)] last:border-0',
                          !n.read && 'bg-brand-500/5'
                        )}
                      >
                        <Icon className={cn('w-4 h-4 mt-0.5 flex-shrink-0', notifColor[n.type])} />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-[var(--text-1)] font-medium leading-snug">{n.title}</p>
                          {n.message && (
                            <p className="text-xs text-[var(--text-3)] mt-0.5 truncate">{n.message}</p>
                          )}
                          <p className="text-xs text-[var(--text-3)] mt-1">{formatRelative(n.timestamp)}</p>
                        </div>
                        <button
                          onClick={() => dismissNotification(n.id)}
                          className="text-[var(--text-3)] hover:text-[var(--text-2)] flex-shrink-0"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </motion.div>
                    )
                  })
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* User avatar */}
      <button className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-[var(--elevated)] transition-colors group">
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-brand-400 to-violet-500 flex items-center justify-center text-white text-xs font-bold">
          {user?.name?.[0] ?? 'R'}
        </div>
        <span className="text-sm text-[var(--text-2)] group-hover:text-[var(--text-1)] transition-colors hidden sm:block">
          {user?.name ?? 'Reviewer'}
        </span>
        <ChevronDown className="w-3.5 h-3.5 text-[var(--text-3)]" />
      </button>
    </header>
  )
}