import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { MutationFunction } from '@tanstack/react-query'

interface OptimisticMutationOptions<TData, TVariables, TSnapshot> {
  mutationFn: MutationFunction<TData, TVariables>
  queryKey:   readonly unknown[]
  updater:    (snapshot: TSnapshot | undefined, variables: TVariables) => TSnapshot
  onSuccess?: (data: TData, variables: TVariables) => void
  onError?:   (error: unknown, variables: TVariables) => void
}

export function useOptimisticMutation<TData, TVariables, TSnapshot = unknown>({
  mutationFn,
  queryKey,
  updater,
  onSuccess,
  onError,
}: OptimisticMutationOptions<TData, TVariables, TSnapshot>) {
  const qc = useQueryClient()

  return useMutation({
    mutationFn,

    onMutate: async (variables) => {
      await qc.cancelQueries({ queryKey })
      const snapshot = qc.getQueryData<TSnapshot>(queryKey)
      qc.setQueryData(queryKey, (old: TSnapshot | undefined) => updater(old, variables))
      return { snapshot }
    },

    onError: (error, variables, context: any) => {
      if (context?.snapshot !== undefined) {
        qc.setQueryData(queryKey, context.snapshot)
      }
      onError?.(error, variables)
    },

    onSuccess: (data, variables) => {
      onSuccess?.(data, variables)
    },

    onSettled: () => {
      qc.invalidateQueries({ queryKey })
    },
  })
}
