/**
 * Secure token storage — two-tier model:
 *   Access token  → in-memory only (cleared on page refresh, never touches storage)
 *   Refresh token → sessionStorage (per-tab, cleared when tab closes)
 *
 * This eliminates the primary localStorage XSS vector: a malicious script reading
 * `localStorage.getItem('pa-auth')` gets nothing useful.
 */

const REFRESH_KEY = 'pa_rt'
const EXPIRES_KEY  = 'pa_exp'

let _accessToken: string | null = null

export const tokenVault = {
  setTokens(access: string, expiresAt: number, refresh?: string): void {
    _accessToken = access
    sessionStorage.setItem(EXPIRES_KEY, String(expiresAt))
    if (refresh) sessionStorage.setItem(REFRESH_KEY, refresh)
  },

  getAccessToken(): string | null {
    return _accessToken
  },

  getRefreshToken(): string | null {
    return sessionStorage.getItem(REFRESH_KEY)
  },

  getExpiresAt(): number | null {
    const raw = sessionStorage.getItem(EXPIRES_KEY)
    return raw ? Number(raw) : null
  },

  isExpiringSoon(bufferMs = 60_000): boolean {
    if (!_accessToken) return true
    const exp = Number(sessionStorage.getItem(EXPIRES_KEY) ?? '0')
    return !exp || Date.now() >= exp - bufferMs
  },

  updateAccessToken(access: string, expiresAt: number): void {
    _accessToken = access
    sessionStorage.setItem(EXPIRES_KEY, String(expiresAt))
  },

  clearTokens(): void {
    _accessToken = null
    sessionStorage.removeItem(REFRESH_KEY)
    sessionStorage.removeItem(EXPIRES_KEY)
  },

  hasSession(): boolean {
    return !!_accessToken || !!sessionStorage.getItem(REFRESH_KEY)
  },
}
