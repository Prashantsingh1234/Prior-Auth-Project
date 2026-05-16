import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import type { PACase, CaseListItem, CaseFilters } from '@/types'

interface CasesStore {
  // List state
  cases:      CaseListItem[]
  total:      number
  page:       number
  pageSize:   number
  filters:    CaseFilters
  isLoading:  boolean

  // Detail state
  activeCase:     PACase | null
  activeCaseId:   string | null
  isCaseLoading:  boolean

  // Actions
  setFilters:    (f: Partial<CaseFilters>) => void
  resetFilters:  () => void
  setPage:       (p: number) => void
  setActiveCase: (c: PACase | null) => void
  setActiveCaseId: (id: string | null) => void
}

const DEFAULT_FILTERS: CaseFilters = {}

export const useCasesStore = create<CasesStore>()(
  devtools(
    (set) => ({
      cases:     [],
      total:     0,
      page:      1,
      pageSize:  20,
      filters:   DEFAULT_FILTERS,
      isLoading: false,

      activeCase:    null,
      activeCaseId:  null,
      isCaseLoading: false,

      setFilters: (f) => set((s) => ({ filters: { ...s.filters, ...f }, page: 1 }), false, 'cases/setFilters'),
      resetFilters: () => set({ filters: DEFAULT_FILTERS, page: 1 }, false, 'cases/resetFilters'),
      setPage: (p) => set({ page: p }, false, 'cases/setPage'),
      setActiveCase: (c) => set({ activeCase: c }, false, 'cases/setActiveCase'),
      setActiveCaseId: (id) => set({ activeCaseId: id }, false, 'cases/setActiveCaseId'),
    }),
    { name: 'CasesStore' }
  )
)