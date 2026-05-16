import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { ROUTES } from '@/config/routes.config'
import { useAuthStore } from '@/store'
import { usePermissions } from '@/hooks'
import { SuspenseBoundary } from '@/components/layout/SuspenseBoundary'
import { ErrorBoundary }    from '@/components/layout/ErrorBoundary'
import { AppShell }         from '@/components/layout/AppShell'

// ─── Lazy page imports ────────────────────────────────────────────────────────
const LoginPage          = lazy(() => import('@/features/auth/pages/LoginPage').then((m) => ({ default: m.LoginPage })))
const ReviewerDashboard  = lazy(() => import('@/features/cases/pages/CaseListPage').then((m) => ({ default: m.CaseListPage })))
const ReviewPage         = lazy(() => import('@/features/review/pages/ReviewPage').then((m) => ({ default: m.ReviewPage })))
const AnalyticsDashboard = lazy(() => import('@/features/analytics/pages/AnalyticsDashboard').then((m) => ({ default: m.AnalyticsDashboard })))

// ─── Guards ───────────────────────────────────────────────────────────────────

function RequireAuth() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const isHydrated      = useAuthStore((s) => s.isHydrated)
  if (!isHydrated) return null
  return isAuthenticated ? <Outlet /> : <Navigate to={ROUTES.LOGIN} replace />
}

function RequirePermission({ permission }: { permission: import('@/types').Permission }) {
  const { can } = usePermissions()
  return can(permission) ? <Outlet /> : <Navigate to={ROUTES.DASHBOARD} replace />
}

// ─── Router ───────────────────────────────────────────────────────────────────

export function AppRouter() {
  return (
    <ErrorBoundary>
      <Routes>
        {/* Public */}
        <Route
          path={ROUTES.LOGIN}
          element={
            <SuspenseBoundary>
              <LoginPage />
            </SuspenseBoundary>
          }
        />

        {/* Protected shell */}
        <Route element={<RequireAuth />}>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to={ROUTES.DASHBOARD} replace />} />

            <Route
              path={ROUTES.DASHBOARD}
              element={
                <SuspenseBoundary>
                  <ReviewerDashboard />
                </SuspenseBoundary>
              }
            />

            <Route
              path="/review/:caseId"
              element={
                <ErrorBoundary>
                  <SuspenseBoundary>
                    <ReviewPage />
                  </SuspenseBoundary>
                </ErrorBoundary>
              }
            />

            {/* Analytics — reviewer+ only */}
            <Route element={<RequirePermission permission="analytics:read" />}>
              <Route
                path={ROUTES.ANALYTICS}
                element={
                  <SuspenseBoundary>
                    <AnalyticsDashboard />
                  </SuspenseBoundary>
                }
              />
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  )
}