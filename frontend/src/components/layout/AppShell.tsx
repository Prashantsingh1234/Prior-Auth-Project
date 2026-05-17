import { Outlet } from 'react-router-dom'
import { Sidebar }             from './Sidebar'
import { TopBar }              from './TopBar'
import { WorkspaceTabs }       from './WorkspaceTabs'
import { BreadcrumbNav }       from './BreadcrumbNav'
import { CommandPalette }      from './CommandPalette'
import { NotificationsPanel }  from './NotificationsPanel'
import { AIAssistantPanel }    from './AIAssistantPanel'
import { ReconnectBanner, SystemAlertBanner } from '@/components/realtime'
import { useUIStore }          from '@/store/uiStore'
import { useWebSocketBridge }  from '@/hooks/useWebSocket'
import { cn }                  from '@/lib/utils'

export function AppShell() {
  const sidebarCollapsed = useUIStore((s) => s.sidebarCollapsed)
  useWebSocketBridge()

  return (
    <div className="flex h-screen bg-[var(--bg)] overflow-hidden">

      {/* Sidebar — fixed left */}
      <Sidebar />

      {/* Main content area — CSS transition on margin matches Sidebar motion */}
      <div
        className={cn(
          'flex flex-col flex-1 min-w-0 min-h-0 transition-[margin-left] duration-[220ms] ease-[cubic-bezier(0.4,0,0.2,1)]',
          sidebarCollapsed ? 'ml-16' : 'ml-64',
        )}
      >
        {/* Top navigation bar */}
        <TopBar />

        {/* Workspace tabs */}
        <WorkspaceTabs />

        {/* Breadcrumb */}
        <BreadcrumbNav />

        {/* Page content */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden">
          <Outlet />
        </main>
      </div>

      {/* Global overlay panels (rendered above everything) */}
      <CommandPalette />
      <NotificationsPanel />
      <AIAssistantPanel />
      <ReconnectBanner />
      <SystemAlertBanner />
    </div>
  )
}
