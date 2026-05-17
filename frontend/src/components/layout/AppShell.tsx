import { useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar }             from './Sidebar'
import { TopBar }              from './TopBar'
import { WorkspaceTabs }       from './WorkspaceTabs'
import { BreadcrumbNav }       from './BreadcrumbNav'
import { CommandPalette }      from './CommandPalette'
import { NotificationsPanel }  from './NotificationsPanel'
import { AIAssistantPanel }    from './AIAssistantPanel'
import { ReconnectBanner, SystemAlertBanner } from '@/components/realtime'
import { SkipLink }            from '@/components/a11y'
import { useUIStore }          from '@/store/uiStore'
import { useWebSocketBridge }  from '@/hooks/useWebSocket'
import { useBreakpoint }       from '@/hooks/useBreakpoint'

export function AppShell() {
  const sidebarCollapsed     = useUIStore((s) => s.sidebarCollapsed)
  const mobileSidebarOpen    = useUIStore((s) => s.mobileSidebarOpen)
  const setMobileSidebarOpen = useUIStore((s) => s.setMobileSidebarOpen)
  const isDesktop            = useBreakpoint('md')
  useWebSocketBridge()

  // Close mobile sidebar when resizing to desktop
  useEffect(() => {
    if (isDesktop) setMobileSidebarOpen(false)
  }, [isDesktop, setMobileSidebarOpen])

  // Prevent body scroll when mobile drawer is open
  useEffect(() => {
    document.body.classList.toggle('drawer-open', !isDesktop && mobileSidebarOpen)
    return () => document.body.classList.remove('drawer-open')
  }, [isDesktop, mobileSidebarOpen])

  const marginLeft = isDesktop
    ? sidebarCollapsed ? 64 : 256
    : 0

  return (
    <div className="flex h-screen bg-[var(--bg)] overflow-hidden">

      <SkipLink />

      {/* Mobile overlay backdrop */}
      {!isDesktop && mobileSidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/60 backdrop-blur-sm"
          onClick={() => setMobileSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar — fixed left */}
      <Sidebar />

      {/* Main content area */}
      <div
        className="flex flex-col flex-1 min-w-0 min-h-0 transition-[margin-left] duration-[220ms] ease-[cubic-bezier(0.4,0,0.2,1)]"
        style={{ marginLeft }}
      >
        {/* Top navigation bar */}
        <TopBar />

        {/* Workspace tabs — hidden on mobile */}
        <div className="hidden sm:block">
          <WorkspaceTabs />
        </div>

        {/* Breadcrumb — hidden on mobile */}
        <div className="hidden sm:block">
          <BreadcrumbNav />
        </div>

        {/* Page content */}
        <main id="main-content" role="main" className="flex-1 overflow-y-auto overflow-x-hidden">
          <Outlet />
        </main>
      </div>

      {/* Global overlay panels */}
      <CommandPalette />
      <NotificationsPanel />
      <AIAssistantPanel />
      <ReconnectBanner />
      <SystemAlertBanner />
    </div>
  )
}
