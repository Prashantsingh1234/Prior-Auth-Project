import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom'
import { ROUTES, ROLE_HOME } from '@/config/routes.config'
import { useAuthStore } from '@/store'
import { usePermissions } from '@/hooks'
import { SuspenseBoundary } from '@/components/layout/SuspenseBoundary'
import { ErrorBoundary }    from '@/components/layout/ErrorBoundary'
import { AppShell }         from '@/components/layout/AppShell'
import type { UserRole, Permission } from '@/types'

// ─── Lazy page imports ────────────────────────────────────────────────────────

const LoginPage           = lazy(() => import('@/features/auth/LoginPage').then((m) => ({ default: m.LoginPage })))
const ForgotPasswordPage  = lazy(() => import('@/features/auth/pages/ForgotPasswordPage').then((m) => ({ default: m.ForgotPasswordPage })))
const OTPVerificationPage = lazy(() => import('@/features/auth/pages/OTPVerificationPage').then((m) => ({ default: m.OTPVerificationPage })))
const MFAPage             = lazy(() => import('@/features/auth/pages/MFAPage').then((m) => ({ default: m.MFAPage })))

const CaseListPage        = lazy(() => import('@/features/cases/pages/CaseListPage').then((m) => ({ default: m.CaseListPage })))
const ReviewPage          = lazy(() => import('@/features/review/pages/ReviewPage').then((m) => ({ default: m.ReviewPage })))
const AnalyticsDashboard  = lazy(() => import('@/features/analytics/pages/AnalyticsDashboard').then((m) => ({ default: m.AnalyticsDashboard })))

// ─── Guards ───────────────────────────────────────────────────────────────────

function RequireAuth() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const isHydrated      = useAuthStore((s) => s.isHydrated)
  const location        = useLocation()

  if (!isHydrated) return null

  return isAuthenticated
    ? <Outlet />
    : <Navigate to={ROUTES.LOGIN} state={{ from: location }} replace />
}

function RequireGuest() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const isHydrated      = useAuthStore((s) => s.isHydrated)
  const role            = useAuthStore((s) => s.user?.role)

  if (!isHydrated) return null

  return isAuthenticated
    ? <Navigate to={ROLE_HOME[role as UserRole] ?? ROUTES.DASHBOARD} replace />
    : <Outlet />
}

function RequirePermission({ permission }: { permission: Permission }) {
  const { can } = usePermissions()
  return can(permission) ? <Outlet /> : <Navigate to={ROUTES.DASHBOARD} replace />
}

function RequireRole({ roles }: { roles: UserRole[] }) {
  const hasAnyRole = useAuthStore((s) => s.hasAnyRole)
  return hasAnyRole(roles) ? <Outlet /> : <Navigate to={ROUTES.DASHBOARD} replace />
}

function RequireMFAChallenge() {
  const mfaChallenge = useAuthStore((s) => s.mfaChallenge)
  return mfaChallenge ? <Outlet /> : <Navigate to={ROUTES.LOGIN} replace />
}

// ─── Role-based landing redirect ──────────────────────────────────────────────

function RoleRedirect() {
  const role = useAuthStore((s) => s.user?.role)
  return <Navigate to={ROLE_HOME[role as UserRole] ?? ROUTES.DASHBOARD} replace />
}

// ─── Lazy wrapper ─────────────────────────────────────────────────────────────

function Page({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary>
      <SuspenseBoundary>{children}</SuspenseBoundary>
    </ErrorBoundary>
  )
}

// ─── Router ───────────────────────────────────────────────────────────────────

export function AppRouter() {
  return (
    <ErrorBoundary>
      <Routes>

        {/* ── Public / guest-only routes ──────────────────────────────────── */}
        <Route element={<RequireGuest />}>
          <Route path={ROUTES.LOGIN}           element={<Page><LoginPage /></Page>} />
          <Route path={ROUTES.FORGOT_PASSWORD} element={<Page><ForgotPasswordPage /></Page>} />
          <Route path={ROUTES.RESET_PASSWORD}  element={<Page><ForgotPasswordPage /></Page>} />
          <Route path={ROUTES.OTP}             element={<Page><OTPVerificationPage /></Page>} />
        </Route>

        {/* ── MFA flow (requires challenge token, not full auth) ────────── */}
        <Route element={<RequireMFAChallenge />}>
          <Route path={ROUTES.MFA} element={<Page><MFAPage /></Page>} />
        </Route>

        {/* ── Protected shell ───────────────────────────────────────────── */}
        <Route element={<RequireAuth />}>
          <Route element={<AppShell />}>

            {/* Root redirect based on role */}
            <Route index element={<RoleRedirect />} />

            {/* Dashboard — all authenticated roles */}
            <Route
              path={ROUTES.DASHBOARD}
              element={<Page><CaseListPage /></Page>}
            />

            {/* Cases list */}
            <Route
              path={ROUTES.CASES}
              element={<Page><CaseListPage /></Page>}
            />

            {/* Review workspace */}
            <Route
              path="/review/:caseId"
              element={<Page><ReviewPage /></Page>}
            />

            {/* Analytics — reviewer + admin */}
            <Route element={<RequirePermission permission="analytics:read" />}>
              <Route
                path={ROUTES.ANALYTICS}
                element={<Page><AnalyticsDashboard /></Page>}
              />
            </Route>

            {/* Admin-only routes */}
            <Route element={<RequireRole roles={['admin']} />}>
              <Route
                path={ROUTES.USERS}
                element={<Page><div className="p-8 text-[var(--text-1)]">User Management</div></Page>}
              />
              <Route
                path={ROUTES.SETTINGS}
                element={<Page><div className="p-8 text-[var(--text-1)]">Settings</div></Page>}
              />
            </Route>

            {/* Audit — reviewer + admin */}
            <Route element={<RequirePermission permission="audit:read" />}>
              <Route
                path={ROUTES.AUDIT}
                element={<Page><div className="p-8 text-[var(--text-1)]">Audit Log</div></Page>}
              />
            </Route>

          </Route>
        </Route>

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  )
}
