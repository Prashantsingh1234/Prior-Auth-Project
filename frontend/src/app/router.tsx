import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store'
import AppLayout from '@/components/layout/AppLayout'

// ─── Lazy pages ───────────────────────────────────────────────────────────────

const LoginPage = lazy(() => import('@/features/auth/LoginPage'))

// Provider
const ProviderDashboard      = lazy(() => import('@/features/provider/ProviderDashboard'))
const SubmitRequestPage      = lazy(() => import('@/features/provider/SubmitRequestPage'))
const MyCasesPage            = lazy(() => import('@/features/provider/MyCasesPage'))
const ProviderClarifications = lazy(() => import('@/features/provider/ClarificationsPage'))

// Reviewer
const ReviewerDashboard      = lazy(() => import('@/features/reviewer/ReviewerDashboard'))
const CaseQueuePage          = lazy(() => import('@/features/reviewer/CaseQueuePage'))
const CaseReviewPage         = lazy(() => import('@/features/reviewer/CaseReviewPage'))
const ReviewerClarifications = lazy(() => import('@/features/reviewer/ClarificationsPage'))

// Admin
const AdminDashboard         = lazy(() => import('@/features/admin/AdminDashboard'))
const UserManagementPage     = lazy(() => import('@/features/admin/UserManagementPage'))
const PolicyManagementPage   = lazy(() => import('@/features/admin/PolicyManagementPage'))

// ─── Loading fallback ─────────────────────────────────────────────────────────

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64 text-sm text-gray-400">
      Loading…
    </div>
  )
}

// ─── Guards ───────────────────────────────────────────────────────────────────

function RequireAuth() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const location = useLocation()
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return <Outlet />
}

function RequireGuest() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const role = useAuthStore((s) => s.user?.role)
  if (isAuthenticated) {
    return <Navigate to={roleHome(role)} replace />
  }
  return <Outlet />
}

function roleHome(role?: string) {
  if (role === 'reviewer') return '/reviewer/dashboard'
  if (role === 'admin')    return '/admin/dashboard'
  return '/provider/dashboard'
}

function RoleRedirect() {
  const role = useAuthStore((s) => s.user?.role)
  return <Navigate to={roleHome(role)} replace />
}

// ─── Router ───────────────────────────────────────────────────────────────────

export function AppRouter() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>

        {/* Guest routes */}
        <Route element={<RequireGuest />}>
          <Route path="/login" element={<LoginPage />} />
        </Route>

        {/* Protected routes */}
        <Route element={<RequireAuth />}>
          <Route element={<AppLayout />}>

            <Route index element={<RoleRedirect />} />

            {/* Provider */}
            <Route path="/provider/dashboard"      element={<ProviderDashboard />} />
            <Route path="/provider/submit"         element={<SubmitRequestPage />} />
            <Route path="/provider/cases"          element={<MyCasesPage />} />
            <Route path="/provider/clarifications" element={<ProviderClarifications />} />

            {/* Reviewer */}
            <Route path="/reviewer/dashboard"      element={<ReviewerDashboard />} />
            <Route path="/reviewer/queue"          element={<CaseQueuePage />} />
            <Route path="/reviewer/case/:caseId"   element={<CaseReviewPage />} />
            <Route path="/reviewer/clarifications" element={<ReviewerClarifications />} />

            {/* Admin */}
            <Route path="/admin/dashboard"  element={<AdminDashboard />} />
            <Route path="/admin/users"      element={<UserManagementPage />} />
            <Route path="/admin/policies"   element={<PolicyManagementPage />} />

          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}
