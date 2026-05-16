import { useSessionTimeout } from '@/features/auth/hooks/useSessionTimeout'
import { SessionTimeoutModal } from '@/features/auth/components/SessionTimeoutModal'
import { useAuthStore } from '@/store'

interface Props { children: React.ReactNode }

function SessionGuard() {
  const { millisRemaining, showWarning, isContinuing, continueSession, signOut } = useSessionTimeout()

  return (
    <SessionTimeoutModal
      open={showWarning}
      millisRemaining={millisRemaining}
      onContinue={continueSession}
      onSignOut={signOut}
      isContinuing={isContinuing}
    />
  )
}

/**
 * AuthProvider wires up session timeout warning + auto-logout.
 * Only renders the guard when there's an active session.
 */
export function AuthProvider({ children }: Props) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)

  return (
    <>
      {children}
      {isAuthenticated && <SessionGuard />}
    </>
  )
}
