import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface Notification {
  id: string
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  message: string
  timestamp: string
  read: boolean
  caseId?: string
}

interface UIState {
  theme: 'light' | 'dark' | 'system'
  sidebarCollapsed: boolean
  notifications: Notification[]
  commandOpen: boolean
  unreadCount: number

  setTheme: (t: UIState['theme']) => void
  applyTheme: () => void
  toggleSidebar: () => void
  setSidebarCollapsed: (v: boolean) => void
  addNotification: (n: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void
  markRead: (id: string) => void
  markAllRead: () => void
  dismissNotification: (id: string) => void
  clearNotifications: () => void
  setCommandOpen: (v: boolean) => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      theme: 'light',
      sidebarCollapsed: false,
      notifications: [],
      commandOpen: false,

      unreadCount: 0,

      setTheme: (theme) => {
        set({ theme })
        applyTheme(theme)
      },
      applyTheme: () => {
        const theme = useUIStore.getState().theme
        applyTheme(theme)
      },
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),

      addNotification: (n) => set((s) => {
        const updated = [
          { ...n, id: crypto.randomUUID(), timestamp: new Date().toISOString(), read: false },
          ...s.notifications.slice(0, 49),
        ]
        return { notifications: updated, unreadCount: updated.filter((x) => !x.read).length }
      }),

      markRead: (id) => set((s) => {
        const updated = s.notifications.map((n) => n.id === id ? { ...n, read: true } : n)
        return { notifications: updated, unreadCount: updated.filter((x) => !x.read).length }
      }),

      markAllRead: () => set((s) => ({
        notifications: s.notifications.map((n) => ({ ...n, read: true })),
        unreadCount: 0,
      })),

      dismissNotification: (id) => set((s) => {
        const updated = s.notifications.filter((n) => n.id !== id)
        return { notifications: updated, unreadCount: updated.filter((x) => !x.read).length }
      }),

      clearNotifications: () => set({ notifications: [], unreadCount: 0 }),
      setCommandOpen: (v) => set({ commandOpen: v }),
    }),
    {
      name: 'pa-ui',
      partialize: (s) => ({ theme: s.theme, sidebarCollapsed: s.sidebarCollapsed }),
      onRehydrateStorage: () => (state) => {
        if (state) applyTheme(state.theme)
      },
    },
  ),
)

function applyTheme(theme: UIState['theme']) {
  const root = document.documentElement
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const isDark = theme === 'dark' || (theme === 'system' && prefersDark)
  root.classList.toggle('dark', isDark)
}

