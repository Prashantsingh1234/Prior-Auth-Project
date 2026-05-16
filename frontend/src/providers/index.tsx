import { QueryProvider }  from './QueryProvider'
import { ThemeProvider }  from './ThemeProvider'
import { AuthProvider }   from './AuthProvider'

interface Props { children: React.ReactNode }

/**
 * Root provider composition. Order matters:
 *  QueryProvider — must wrap everything that uses React Query
 *  ThemeProvider — reads from store (no deps on auth)
 *  AuthProvider  — handles token expiry after Query is available
 */
export function AppProviders({ children }: Props) {
  return (
    <QueryProvider>
      <ThemeProvider>
        <AuthProvider>
          {children}
        </AuthProvider>
      </ThemeProvider>
    </QueryProvider>
  )
}