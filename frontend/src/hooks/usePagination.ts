import { useState, useCallback } from 'react'

interface UsePaginationOptions {
  initialPage?:     number
  initialPageSize?: number
}

export function usePagination({ initialPage = 1, initialPageSize = 20 }: UsePaginationOptions = {}) {
  const [page, setPage]         = useState(initialPage)
  const [pageSize, setPageSize] = useState(initialPageSize)

  const goToPage    = useCallback((p: number) => setPage(Math.max(1, p)), [])
  const nextPage    = useCallback(() => setPage((p) => p + 1), [])
  const prevPage    = useCallback(() => setPage((p) => Math.max(1, p - 1)), [])
  const resetPage   = useCallback(() => setPage(1), [])
  const changeSize  = useCallback((s: number) => { setPageSize(s); setPage(1) }, [])

  return { page, pageSize, goToPage, nextPage, prevPage, resetPage, changeSize }
}