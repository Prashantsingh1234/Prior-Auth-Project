import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { Sidebar } from '@/components/layout/Sidebar'
import { TopBar } from '@/components/layout/TopBar'
import { LoginPage } from '@/features/auth/LoginPage'
import { ReviewerDashboard } from '@/features/dashboard/ReviewerDashboard'
import { ReviewWorkspace } from '@/features/review/ReviewWorkspace'

function ProtectedLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-auto min-h-0">
          <Routes>
            <Route path="dashboard"    element={<ReviewerDashboard />} />
            <Route path="review/:caseId" element={<ReviewWorkspace />} />
            <Route path="*"            element={<Navigate to="dashboard" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)

  return (
    <Routes>
      <Route path="/login" element={
        isAuthenticated ? <Navigate to="/dashboard" replace /> : <LoginPage />
      } />
      <Route path="/*" element={
        isAuthenticated ? <ProtectedLayout /> : <Navigate to="/login" replace />
      } />
    </Routes>
  )
}
