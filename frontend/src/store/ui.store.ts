import { create } from 'zustand'
import { persist, devtools } from 'zustand/middleware'

export type Theme = 'light' | 'dark' | 'system'

export interface Notification {
  id:        string
  type:      'info' | 'success' | 'warning' | 'error'
  title:     string
  message?:  string
  timestamp: string
  read:      boolean
  caseId?:   string
  action?:   { label: string; href: string }
}

interface UIStore {
  // State
  theme:             Theme
  sidebarCollapsed:  boolean
  notifications:     Notification[]
  unreadCount:       number
  commandOpen:       boolean

  // Theme
  setTheme:   (t: Theme) => void
  applyTheme: () => void

  // Sidebar
  toggleSidebar:       () => void
  setSidebarCollapsed: (v: boolean) => void

  // Notifications
  addNotification:     (n: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void
  markRead:            (id: string) => void
  markAllRead:         () => void
  dismissNotification: (id: string) => void
  clearNotifications:  () => void

  // Command palette
  setCommandOpen: (v: boolean) => void
}

function applyThemeToDOM(theme: Theme): void {
  const root       = document.documentElement
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const dark        = theme === 'dark' || (theme === 'system' && prefersDark)
  root.classList.toggle('dark', dark)
}

export const useUIStore = create<UIStore>()(
  devtools(
    persist(
      (set, get) => ({
        theme:            'light',
        sidebarCollapsed: false,
        notifications:    [],
        unreadCount:      0,
        commandOpen:      false,

        setTheme: (theme) => {
          set({ theme }, false, 'ui/setTheme')
          applyThemeToDOM(theme)
        },
        applyTheme: () => applyThemeToDOM(get().theme),

        toggleSidebar:       () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed }), false, 'ui/toggleSidebar'),
        setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }, false, 'ui/setSidebar'),

        addNotification: (n) => set((s) => {
          const item: Notification = { ...n, id: crypto.randomUUID(), timestamp: new Date().toISOString(), read: false }
          const notifications      = [item, ...s.notifications.slice(0, 49)]
          return { notifications, unreadCount: notifications.filter((x) => !x.read).length }
        }, false, 'ui/addNotification'),

        markRead: (id) => set((s) => {
          const notifications = s.notifications.map((n) => n.id === id ? { ...n, read: true } : n)
          return { notifications, unreadCount: notifications.filter((x) => !x.read).length }
        }, false, 'ui/markRead'),

        markAllRead: () => set((s) => ({
          notifications: s.notifications.map((n) => ({ ...n, read: true })),
          unreadCount: 0,
        }), false, 'ui/markAllRead'),

        dismissNotification: (id) => set((s) => {
          const notifications = s.notifications.filter((n) => n.id !== id)
          return { notifications, unreadCount: notifications.filter((x) => !x.read).length }
        }, false, 'ui/dismiss'),

        clearNotifications: () => set({ notifications: [], unreadCount: 0 }, false, 'ui/clear'),
        setCommandOpen:     (v) => set({ commandOpen: v }, false, 'ui/command'),
      }),
      {
        name:       'pa-ui',
        partialize: (s) => ({ theme: s.theme, sidebarCollapsed: s.sidebarCollapsed }),
        onRehydrateStorage: () => (state) => { if (state) applyThemeToDOM(state.theme) },
      }
    ),
    { name: 'UIStore' }
  )
)