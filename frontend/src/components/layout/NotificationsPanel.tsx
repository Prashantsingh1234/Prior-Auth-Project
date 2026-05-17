import { useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  X, Bell, CheckCheck, Trash2,
  AlertTriangle, CheckCircle2, Info,
} from 'lucide-react'
import { useUIStore, type Notification } from '@/store/uiStore'
import { useFocusTrap } from '@/hooks/useFocusTrap'
import { cn, formatRelative } from '@/lib/utils'

type FilterTab = 'all' | 'cases' | 'ai' | 'system'

const ICON_MAP = {
  success: CheckCircle2,
  warning: AlertTriangle,
  error:   AlertTriangle,
  info:    Info,
}

const COLOR_MAP = {
  success: 'text-emerald-400',
  warning: 'text-amber-400',
  error:   'text-red-400',
  info:    'text-cyan-400',
}

function groupByDate(notifications: Notification[]) {
  const today     = new Date(); today.setHours(0, 0, 0, 0)
  const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1)

  const groups: { label: string; items: Notification[] }[] = [
    { label: 'Today',     items: [] },
    { label: 'Yesterday', items: [] },
    { label: 'Older',     items: [] },
  ]

  notifications.forEach((n) => {
    const d = new Date(n.timestamp); d.setHours(0, 0, 0, 0)
    if (d >= today)                       groups[0].items.push(n)
    else if (d >= yesterday && d < today) groups[1].items.push(n)
    else                                  groups[2].items.push(n)
  })

  return groups.filter((g) => g.items.length > 0)
}

function NotifItem({ n, onDismiss, onRead }: { n: Notification; onDismiss: () => void; onRead: () => void }) {
  const navigate = useNavigate()
  const Icon = ICON_MAP[n.type]

  function handleClick() {
    onRead()
    if (n.link) navigate(n.link)
    else if (n.caseId) navigate(`/review/${n.caseId}`)
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.2 }}
      className={cn(
        'group flex items-start gap-3 px-4 py-3 border-b border-[var(--border)] last:border-0',
        'hover:bg-[var(--elevated)] transition-colors',
        !n.read && 'bg-cyan-500/[0.03]',
      )}
    >
      <div className="relative mt-0.5 flex-shrink-0" aria-hidden="true">
        <Icon className={cn('w-4 h-4', COLOR_MAP[n.type])} />
        {!n.read && (
          <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-cyan-500" />
        )}
      </div>

      <button
        onClick={handleClick}
        className="flex-1 min-w-0 text-left"
        aria-label={`${n.title}${n.read ? '' : ' (unread)'}. ${n.message ?? ''}`}
      >
        <p className={cn('text-sm leading-snug', !n.read ? 'text-[var(--text-1)] font-medium' : 'text-[var(--text-2)]')}>
          {n.title}
        </p>
        {n.message && (
          <p className="text-xs text-[var(--text-3)] mt-0.5 line-clamp-2">{n.message}</p>
        )}
        <p className="text-[10px] text-[var(--text-4)] mt-1">{formatRelative(n.timestamp)}</p>
      </button>

      <button
        onClick={onDismiss}
        aria-label={`Dismiss: ${n.title}`}
        className="text-[var(--text-4)] hover:text-[var(--text-2)] transition-colors flex-shrink-0 mt-0.5 p-1 rounded opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
      >
        <X className="w-3.5 h-3.5" aria-hidden="true" />
      </button>
    </motion.div>
  )
}

export function NotificationsPanel() {
  const {
    notificationsPanelOpen, setNotificationsPanelOpen,
    notifications, unreadCount, markAllRead, markRead, dismissNotification,
  } = useUIStore()
  const [filter, setFilter] = useState<FilterTab>('all')
  const panelRef = useRef<HTMLDivElement>(null)

  useFocusTrap(panelRef, notificationsPanelOpen)

  const filtered = notifications.filter((n) => {
    if (filter === 'all')    return true
    if (filter === 'cases')  return !!n.caseId
    if (filter === 'ai')     return n.title.toLowerCase().includes('ai') || n.title.toLowerCase().includes('confidence')
    if (filter === 'system') return !n.caseId
    return true
  })

  const groups = groupByDate(filtered)

  const TABS: { id: FilterTab; label: string }[] = [
    { id: 'all',    label: 'All' },
    { id: 'cases',  label: 'Cases' },
    { id: 'ai',     label: 'AI' },
    { id: 'system', label: 'System' },
  ]

  return (
    <AnimatePresence>
      {notificationsPanelOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.3 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={() => setNotificationsPanelOpen(false)}
            className="fixed inset-0 z-[38] bg-black"
            aria-hidden="true"
          />

          {/* Panel */}
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="notif-panel-title"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 380, damping: 38 }}
            className="fixed right-0 top-0 h-full w-80 z-[39] flex flex-col shadow-card-xl"
            style={{ background: 'var(--surface)', borderLeft: '1px solid var(--border)' }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 h-14 border-b border-[var(--border)] flex-shrink-0">
              <div className="flex items-center gap-2.5">
                <Bell className="w-4 h-4 text-[var(--text-2)]" aria-hidden="true" />
                <span id="notif-panel-title" className="text-sm font-semibold text-[var(--text-1)]">Notifications</span>
                {unreadCount > 0 && (
                  <span
                    className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-cyan-500/20 text-cyan-400"
                    aria-label={`${unreadCount} unread`}
                  >
                    {unreadCount}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                {unreadCount > 0 && (
                  <button
                    onClick={markAllRead}
                    aria-label="Mark all notifications as read"
                    className="p-1.5 rounded-lg text-[var(--text-3)] hover:text-cyan-400 hover:bg-cyan-500/10 transition-colors"
                  >
                    <CheckCheck className="w-3.5 h-3.5" aria-hidden="true" />
                  </button>
                )}
                <button
                  onClick={() => setNotificationsPanelOpen(false)}
                  aria-label="Close notifications"
                  className="p-1.5 rounded-lg text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-[var(--elevated)] transition-colors"
                >
                  <X className="w-4 h-4" aria-hidden="true" />
                </button>
              </div>
            </div>

            {/* Filter tabs */}
            <div
              role="tablist"
              aria-label="Filter notifications"
              className="flex px-4 gap-0.5 py-2 border-b border-[var(--border)] flex-shrink-0"
            >
              {TABS.map((t) => (
                <button
                  key={t.id}
                  role="tab"
                  aria-selected={filter === t.id}
                  onClick={() => setFilter(t.id)}
                  className={cn(
                    'px-2.5 py-1 rounded-lg text-xs font-medium transition-colors',
                    filter === t.id
                      ? 'bg-cyan-500/15 text-cyan-400'
                      : 'text-[var(--text-3)] hover:text-[var(--text-2)] hover:bg-[var(--elevated)]',
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto" role="region" aria-label="Notification list" aria-live="polite">
              {filtered.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full gap-3 text-center p-8">
                  <div className="w-12 h-12 rounded-2xl bg-[var(--elevated)] flex items-center justify-center" aria-hidden="true">
                    <Bell className="w-5 h-5 text-[var(--text-4)]" />
                  </div>
                  <p className="text-sm text-[var(--text-3)]">No notifications</p>
                </div>
              ) : (
                groups.map((group) => (
                  <div key={group.label}>
                    <div className="px-4 py-2 bg-[var(--elevated)]/50">
                      <span className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-4)]">
                        {group.label}
                      </span>
                    </div>
                    <AnimatePresence>
                      {group.items.map((n) => (
                        <NotifItem
                          key={n.id}
                          n={n}
                          onDismiss={() => dismissNotification(n.id)}
                          onRead={() => markRead(n.id)}
                        />
                      ))}
                    </AnimatePresence>
                  </div>
                ))
              )}
            </div>

            {/* Footer */}
            {notifications.length > 0 && (
              <div className="border-t border-[var(--border)] p-3 flex-shrink-0">
                <button
                  onClick={() => useUIStore.getState().clearNotifications()}
                  className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs text-[var(--text-3)] hover:bg-red-500/10 hover:text-red-400 transition-colors"
                  aria-label="Clear all notifications"
                >
                  <Trash2 className="w-3.5 h-3.5" aria-hidden="true" />
                  Clear all notifications
                </button>
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
