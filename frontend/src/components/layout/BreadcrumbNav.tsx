import { useLocation, Link } from 'react-router-dom'
import { ChevronRight, Home } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Crumb {
  label: string
  path:  string
  current: boolean
}

const ROUTE_LABELS: Record<string, string> = {
  dashboard:  'Dashboard',
  cases:      'Cases',
  review:     'Review',
  analytics:  'Analytics',
  policies:   'Policies',
  audit:      'Audit Log',
  monitoring: 'Monitoring',
  settings:   'Settings',
  admin:      'Admin',
  users:      'User Management',
  auth:       'Auth',
}

function buildCrumbs(pathname: string): Crumb[] {
  const parts = pathname.split('/').filter(Boolean)

  return parts.map((part, i) => {
    const path = '/' + parts.slice(0, i + 1).join('/')
    const isCaseId = part.startsWith('case-') || (part.length > 8 && /^[a-z0-9-]+$/i.test(part))
    const isUUID   = /^[0-9a-f-]{36}$/i.test(part)
    const label    = isUUID || isCaseId
      ? `Case #${part.slice(0, 8).toUpperCase()}`
      : ROUTE_LABELS[part] ?? part.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

    return { label, path, current: i === parts.length - 1 }
  })
}

export function BreadcrumbNav() {
  const { pathname } = useLocation()
  const crumbs = buildCrumbs(pathname)

  if (crumbs.length <= 1) return null

  return (
    <nav
      className="flex items-center gap-1 px-4 sm:px-6 h-8 border-b border-[var(--border)] flex-shrink-0 overflow-x-auto"
      style={{ scrollbarWidth: 'none' }}
      aria-label="Breadcrumb"
    >
      <Link to="/" className="text-[var(--text-4)] hover:text-[var(--text-2)] transition-colors flex-shrink-0">
        <Home className="w-3 h-3" />
      </Link>
      {crumbs.map((crumb) => (
        <div key={crumb.path} className="flex items-center gap-1">
          <ChevronRight className="w-3 h-3 text-[var(--text-4)] flex-shrink-0" />
          {crumb.current ? (
            <span className={cn('text-xs font-medium text-[var(--text-2)] truncate max-w-[200px]')}>
              {crumb.label}
            </span>
          ) : (
            <Link
              to={crumb.path}
              className="text-xs text-[var(--text-4)] hover:text-[var(--text-2)] transition-colors truncate max-w-[160px]"
            >
              {crumb.label}
            </Link>
          )}
        </div>
      ))}
    </nav>
  )
}
