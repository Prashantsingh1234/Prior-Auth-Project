import { Bell, RefreshCw, Wifi, WifiOff } from 'lucide-react'
import { useIsFetching } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'

const ROUTE_TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/cases':     'Cases',
  '/review':    'Review Queue',
  '/reports':   'Reports',
}

export function TopBar() {
  const location  = useLocation()
  const isFetching = useIsFetching()

  const title = ROUTE_TITLES[location.pathname]
    ?? Object.entries(ROUTE_TITLES).find(([k]) => location.pathname.startsWith(k))?.[1]
    ?? 'PA Review Platform'

  return (
    <header className="h-16 bg-white border-b border-slate-200 flex items-center px-6 gap-4 flex-shrink-0 shadow-sm">
      <div className="flex-1 min-w-0">
        <h1 className="text-lg font-semibold text-slate-900 truncate">{title}</h1>
      </div>

      <div className="flex items-center gap-3">
        {/* Live data indicator */}
        <div className="flex items-center gap-1.5 text-xs">
          {isFetching > 0 ? (
            <>
              <RefreshCw className="w-3 h-3 text-brand-500 animate-spin" />
              <span className="text-slate-400 hidden sm:block">Updating…</span>
            </>
          ) : (
            <>
              <Wifi className="w-3 h-3 text-green-500" />
              <span className="text-slate-400 hidden sm:block">Live</span>
            </>
          )}
        </div>

        {/* HIPAA compliance badge */}
        <span className="hidden md:inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 ring-1 ring-blue-200">
          HIPAA Compliant
        </span>

        {/* Notifications placeholder */}
        <button className="relative p-1.5 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-100 transition-colors">
          <Bell className="w-5 h-5" />
          <span className="absolute top-0.5 right-0.5 w-2 h-2 bg-red-500 rounded-full" />
        </button>
      </div>
    </header>
  )
}
