import { useCallback, useRef, useState } from 'react'

/**
 * Sliding-window rate limiter.
 * `attempt()` returns true if the action is allowed, false if the window is full.
 * Useful for login forms, OTP submission, and other brute-force-sensitive actions.
 */
export function useRateLimit(maxAttempts: number, windowMs: number) {
  const timestamps = useRef<number[]>([])
  const [isLimited, setIsLimited] = useState(false)

  const attempt = useCallback((): boolean => {
    const now = Date.now()
    // Drop timestamps outside the window
    timestamps.current = timestamps.current.filter((t) => now - t < windowMs)

    if (timestamps.current.length >= maxAttempts) {
      setIsLimited(true)
      return false
    }

    timestamps.current.push(now)
    setIsLimited(false)
    return true
  }, [maxAttempts, windowMs])

  const reset = useCallback(() => {
    timestamps.current = []
    setIsLimited(false)
  }, [])

  // Returns milliseconds until the oldest attempt falls out of the window
  const cooldownMs = useCallback((): number => {
    if (timestamps.current.length < maxAttempts) return 0
    return Math.max(0, windowMs - (Date.now() - timestamps.current[0]))
  }, [maxAttempts, windowMs])

  return { isLimited, attempt, reset, cooldownMs }
}
