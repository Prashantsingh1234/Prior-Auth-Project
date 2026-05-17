export const ROUTES = {
  // Public auth
  LOGIN:            '/login',
  FORGOT_PASSWORD:  '/auth/forgot-password',
  RESET_PASSWORD:   '/auth/reset-password',
  MFA:              '/auth/mfa',
  OTP:              '/auth/otp',

  // Protected app
  DASHBOARD:  '/dashboard',
  CASES:      '/cases',
  CASE:       '/cases/:caseId',
  REVIEW:     '/review/:caseId',
  ANALYTICS:  '/analytics',
  INGESTION:  '/ingestion',
  REASONING:  '/reasoning',
  POLICIES:   '/policies',
  AUDIT:      '/audit',
  MONITORING: '/monitoring',
  SETTINGS:   '/settings',
  USERS:      '/admin/users',
} as const

export type RouteKey = keyof typeof ROUTES
export type RoutePath = (typeof ROUTES)[RouteKey]

export function buildRoute(route: string, params: Record<string, string>): string {
  return Object.entries(params).reduce(
    (acc, [key, val]) => acc.replace(`:${key}`, val),
    route
  )
}

/** Role-based default landing page after login */
export const ROLE_HOME = {
  admin:    ROUTES.DASHBOARD,
  reviewer: ROUTES.DASHBOARD,
  provider: ROUTES.CASES,
} as const
