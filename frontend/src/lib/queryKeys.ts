// Type-safe query key factory — centralises cache key strings so refetches,
// invalidations, and prefetches all reference the same shape.

export const queryKeys = {
  cases: {
    all:    ()                                  => ['cases']                    as const,
    list:   (filters?: Record<string, unknown>) => ['cases', 'list', filters]  as const,
    detail: (id: string)                        => ['cases', 'detail', id]     as const,
  },
  dashboard: {
    all:       () => ['dashboard']                      as const,
    kpi:       () => ['dashboard', 'kpi']               as const,
    system:    () => ['dashboard', 'system']            as const,
    trend:     () => ['dashboard', 'confidence-trend']  as const,
    reviewers: () => ['dashboard', 'reviewer-load']     as const,
    outcomes:  () => ['dashboard', 'outcomes']          as const,
  },
  policies: {
    all:    ()               => ['policies']              as const,
    list:   ()               => ['policies', 'list']      as const,
    detail: (id: string)     => ['policies', 'detail', id] as const,
  },
  audit: {
    all:  ()                                  => ['audit']              as const,
    list: (filters?: Record<string, unknown>) => ['audit', 'list', filters] as const,
  },
  users: {
    all:  () => ['users']       as const,
    list: () => ['users', 'list'] as const,
  },
} as const
