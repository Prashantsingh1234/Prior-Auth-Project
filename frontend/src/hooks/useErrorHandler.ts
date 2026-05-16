import { useCallback } from 'react'
import { useUIStore } from '@/store'
import type { ApiError } from '@/types'

export function useErrorHandler() {
  const addNotification = useUIStore((s) => s.addNotification)

  const handleError = useCallback((error: unknown, fallbackMessage?: string) => {
    const apiError = error as ApiError

    const message =
      apiError?.message
      ?? (error instanceof Error ? error.message : null)
      ?? fallbackMessage
      ?? 'An unexpected error occurred'

    addNotification({ type: 'error', title: 'Error', message })
  }, [addNotification])

  const handleSuccess = useCallback((title: string, message?: string) => {
    addNotification({ type: 'success', title, message })
  }, [addNotification])

  return { handleError, handleSuccess }
}