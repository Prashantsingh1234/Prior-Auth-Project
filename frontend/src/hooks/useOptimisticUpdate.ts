import { useState, useCallback, useRef } from 'react'

// ─── Types ────────────────────────────────────────────────────────────────────

type MutationFn<TData, TVariables> = (variables: TVariables) => Promise<TData>

export type OptimisticStatus = 'idle' | 'loading' | 'success' | 'error'

export interface UseOptimisticUpdateOptions<TState, TVariables> {
  getOptimisticState: (current: TState, variables: TVariables) => TState
  onSuccess?:         (data: unknown, variables: TVariables) => void
  onError?:           (err: unknown, variables: TVariables) => void
  onSettled?:         () => void
}

export interface UseOptimisticUpdateResult<TState, TVariables> {
  state:    TState
  status:   OptimisticStatus
  error:    unknown | null
  mutate:   (variables: TVariables) => Promise<void>
  rollback: () => void
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useOptimisticUpdate<TState, TData, TVariables>(
  initialState: TState,
  mutationFn:   MutationFn<TData, TVariables>,
  options:      UseOptimisticUpdateOptions<TState, TVariables>,
): UseOptimisticUpdateResult<TState, TVariables> {
  const [state,  setState]  = useState<TState>(initialState)
  const [status, setStatus] = useState<OptimisticStatus>('idle')
  const [error,  setError]  = useState<unknown>(null)

  const previousStateRef = useRef<TState>(initialState)

  const rollback = useCallback(() => {
    setState(previousStateRef.current)
    setStatus('idle')
    setError(null)
  }, [])

  const mutate = useCallback(async (variables: TVariables) => {
    previousStateRef.current = state
    const optimistic = options.getOptimisticState(state, variables)

    setState(optimistic)
    setStatus('loading')
    setError(null)

    try {
      const data = await mutationFn(variables)
      setStatus('success')
      options.onSuccess?.(data, variables)
    } catch (err) {
      setState(previousStateRef.current)
      setStatus('error')
      setError(err)
      options.onError?.(err, variables)
    } finally {
      options.onSettled?.()
    }
  }, [state, mutationFn, options])

  return { state, status, error, mutate, rollback }
}
