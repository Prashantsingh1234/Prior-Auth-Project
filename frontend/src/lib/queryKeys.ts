// Type-safe query key factory — all cache keys live here so invalidations,
// prefetches, and refetches always reference the exact same shape.

import type { CaseFilters } from '@/api/types'

export const queryKeys = {
  cases: {
    all:    ()                    => ['cases']                       as const,
    lists:  ()                    => ['cases', 'list']              as const,
    list:   (f?: CaseFilters)     => ['cases', 'list', f]           as const,
    detail: (id: string)          => ['cases', 'detail', id]        as const,
    queue:  ()                    => ['cases', 'queue']             as const,
    document: (caseId: string, docId: string) =>
                                     ['cases', 'document', caseId, docId] as const,
  },

  dashboard: {
    all:       () => ['dashboard']                     as const,
    kpi:       () => ['dashboard', 'kpi']              as const,
    system:    () => ['dashboard', 'system']           as const,
    trend:     () => ['dashboard', 'confidence-trend'] as const,
    reviewers: () => ['dashboard', 'reviewer-load']    as const,
    outcomes:  () => ['dashboard', 'outcomes']         as const,
    clarifications: () => ['dashboard', 'clarifications'] as const,
  },

  metrics: {
    all:  () => ['metrics']        as const,
    data: () => ['metrics', 'data'] as const,
  },

  health: {
    status: () => ['health', 'status'] as const,
  },

  clarifications: {
    all:    ()           => ['clarifications']          as const,
    byCase: (id: string) => ['clarifications', 'case', id] as const,
  },

  policies: {
    all:    ()           => ['policies']              as const,
    list:   ()           => ['policies', 'list']      as const,
    detail: (id: string) => ['policies', 'detail', id] as const,
  },

  audit: {
    all:    ()                                  => ['audit']              as const,
    list:   (f?: Record<string, unknown>)       => ['audit', 'list', f]   as const,
    byCase: (id: string)                        => ['audit', 'case', id]  as const,
  },

  users: {
    all:  () => ['users']        as const,
    list: () => ['users', 'list'] as const,
  },
} as const
