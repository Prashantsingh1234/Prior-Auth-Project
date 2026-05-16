import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface Notification {
  id:        string
  type:      'info' | 'success' | 'warning' | 'error'
  title:     string
  message:   string
  timestamp: string
  read:      boolean
  caseId?:   string
  link?:     string
}

export interface WorkspaceTab {
  id:        string
  title:     string
  path:      string
  type:      'dashboard' | 'case' | 'review' | 'analytics' | 'page'
  caseId?:   string
  closeable: boolean
  status?:   string
}

// ─── State interface ──────────────────────────────────────────────────────────

interface UIState {
  // Theme
  theme: 'light' | 'dark' | 'system'

  // Sidebar
  sidebarCollapsed: boolean

  // Panels
  notificationsPanelOpen: boolean
  aiPanelOpen:            boolean
  commandOpen:            boolean

  // Notifications
  notifications: Notification[]
  unreadCount:   number

  // Workspace tabs
  workspaceTabs:  WorkspaceTab[]
  activeTabId:    string | null

  // Global search
  searchQuery:    string

  // ── Actions ────────────────────────────────────────────────────────────────

  // Theme
  setTheme:    (t: UIState['theme']) => void
  applyTheme:  () => void

  // Sidebar
  toggleSidebar:      () => void
  setSidebarCollapsed: (v: boolean) => void

  // Panels
  setNotificationsPanelOpen: (v: boolean) => void
  setAIPanelOpen:            (v: boolean) => void
  setCommandOpen:            (v: boolean) => void

  // Notifications
  addNotification:      (n: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void
  markRead:             (id: string) => void
  markAllRead:          () => void
  dismissNotification:  (id: string) => void
  clearNotifications:   () => void

  // Workspace tabs
  addTab:       (tab: Omit<WorkspaceTab, 'id'>) => void
  removeTab:    (id: string) => void
  setActiveTab: (id: string) => void
  closeAllTabs: () => void

  // Search
  setSearchQuery: (q: string) => void
}

// ─── Default tabs ─────────────────────────────────────────────────────────────

const DEFAULT_TABS: WorkspaceTab[] = [
  { id: 'tab-dashboard', title: 'Dashboard',  path: '/dashboard',  type: 'dashboard', closeable: false },
  { id: 'tab-cases',     title: 'Cases',      path: '/cases',      type: 'page',      closeable: false },
]

// ─── Store ───────────────────────────────────────────────────────────────────

export const useUIStore = create<UIState>()(
  persist(
    (set, get) => ({
      theme:                  'light',
      sidebarCollapsed:       false,
      notificationsPanelOpen: false,
      aiPanelOpen:            false,
      commandOpen:            false,
      notifications:          [],
      unreadCount:            0,
      workspaceTabs:          DEFAULT_TABS,
      activeTabId:            'tab-dashboard',
      searchQuery:            '',

      // ── Theme ─────────────────────────────────────────────────────────────
      setTheme: (theme) => {
        set({ theme })
        applyTheme(theme)
      },
      applyTheme: () => applyTheme(get().theme),

      // ── Sidebar ───────────────────────────────────────────────────────────
      toggleSidebar:       () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),

      // ── Panels ────────────────────────────────────────────────────────────
      setNotificationsPanelOpen: (v) => set({ notificationsPanelOpen: v }),
      setAIPanelOpen:            (v) => set({ aiPanelOpen: v }),
      setCommandOpen:            (v) => set({ commandOpen: v }),

      // ── Notifications ─────────────────────────────────────────────────────
      addNotification: (n) => set((s) => {
        const notif: Notification = {
          ...n,
          id:        crypto.randomUUID(),
          timestamp: new Date().toISOString(),
          read:      false,
        }
        const updated = [notif, ...s.notifications.slice(0, 49)]
        return { notifications: updated, unreadCount: updated.filter((x) => !x.read).length }
      }),

      markRead: (id) => set((s) => {
        const updated = s.notifications.map((n) => n.id === id ? { ...n, read: true } : n)
        return { notifications: updated, unreadCount: updated.filter((x) => !x.read).length }
      }),

      markAllRead: () => set((s) => ({
        notifications: s.notifications.map((n) => ({ ...n, read: true })),
        unreadCount:   0,
      })),

      dismissNotification: (id) => set((s) => {
        const updated = s.notifications.filter((n) => n.id !== id)
        return { notifications: updated, unreadCount: updated.filter((x) => !x.read).length }
      }),

      clearNotifications: () => set({ notifications: [], unreadCount: 0 }),

      // ── Workspace tabs ────────────────────────────────────────────────────
      addTab: (tab) => set((s) => {
        const exists = s.workspaceTabs.find((t) => t.path === tab.path)
        if (exists) return { activeTabId: exists.id }
        const newTab: WorkspaceTab = { ...tab, id: `tab-${crypto.randomUUID().slice(0, 8)}` }
        return {
          workspaceTabs: [...s.workspaceTabs, newTab],
          activeTabId:   newTab.id,
        }
      }),

      removeTab: (id) => set((s) => {
        const remaining = s.workspaceTabs.filter((t) => t.id !== id)
        const newActive = s.activeTabId === id
          ? (remaining.at(-1)?.id ?? null)
          : s.activeTabId
        return { workspaceTabs: remaining, activeTabId: newActive }
      }),

      setActiveTab: (id) => set({ activeTabId: id }),

      closeAllTabs: () => set((s) => ({
        workspaceTabs: s.workspaceTabs.filter((t) => !t.closeable),
        activeTabId:   s.workspaceTabs.find((t) => !t.closeable)?.id ?? null,
      })),

      // ── Search ────────────────────────────────────────────────────────────
      setSearchQuery: (q) => set({ searchQuery: q }),
    }),
    {
      name: 'pa-ui',
      partialize: (s) => ({
        theme:            s.theme,
        sidebarCollapsed: s.sidebarCollapsed,
        workspaceTabs:    s.workspaceTabs,
        activeTabId:      s.activeTabId,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) applyTheme(state.theme)
      },
    },
  ),
)

// ─── Pure helper ─────────────────────────────────────────────────────────────

function applyTheme(theme: UIState['theme']) {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const isDark = theme === 'dark' || (theme === 'system' && prefersDark)
  document.documentElement.classList.toggle('dark', isDark)
}
