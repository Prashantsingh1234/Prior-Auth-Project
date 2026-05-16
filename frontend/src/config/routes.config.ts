export const ROUTES = {
  LOGIN:      '/login',
  DASHBOARD:  '/dashboard',
  CASES:      '/cases',
  CASE:       '/cases/:caseId',
  REVIEW:     '/review/:caseId',
  ANALYTICS:  '/analytics',
  POLICIES:   '/policies',
  AUDIT:      '/audit',
  MONITORING: '/monitoring',
  SETTINGS:   '/settings',
} as const

export type RouteKey = keyof typeof ROUTES
export type RoutePath = (typeof ROUTES)[RouteKey]

export function buildRoute(route: string, params: Record<string, string>): string {
  return Object.entries(params).reduce(
    (acc, [key, val]) => acc.replace(`:${key}`, val),
    route
  )
}