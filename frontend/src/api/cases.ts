import http from '@/services/http.service'
import type { ApiResponse, CaseFilters, CaseListItem, CaseListResponse, PACase } from './types'

// ─── Document URL helper (does not need auth wrapper) ─────────────────────────

export function caseDocumentUrl(caseId: string, documentId: string): string {
  const base = (window as any).__API_BASE__ ?? '/api/v1'
  return `${base}/cases/${caseId}/documents/${documentId}`
}

// ─── API ──────────────────────────────────────────────────────────────────────

export const casesApi = {
  list: async (filters: CaseFilters = {}): Promise<CaseListResponse> => {
    const params: Record<string, unknown> = {
      page:      filters.page      ?? 1,
      page_size: filters.page_size ?? 20,
      sort_by:   filters.sort_by   ?? 'submitted_at',
      sort_dir:  filters.sort_dir  ?? 'desc',
    }
    if (filters.status?.length)       params.status       = filters.status.join(',')
    if (filters.priority?.length)     params.priority     = filters.priority.join(',')
    if (filters.service_type?.length) params.service_type = filters.service_type.join(',')
    if (filters.assigned_to_me)       params.assigned_to_me = true

    const res = await http.get<ApiResponse<CaseListItem[]>>('/cases', { params })
    return { cases: res.data, meta: res.meta! }
  },

  get: async (caseId: string): Promise<PACase> => {
    const res = await http.get<ApiResponse<PACase>>(`/cases/${caseId}`)
    return res.data
  },

  getDocument: async (caseId: string, documentId: string): Promise<Blob> => {
    // Use raw axios for blob response — http helper defaults to json
    const { getHttpClient } = await import('@/services/http.service')
    const res = await getHttpClient().get(
      `/cases/${caseId}/documents/${documentId}`,
      { responseType: 'blob' },
    )
    return res.data as Blob
  },

  queue: (filters: Omit<CaseFilters, 'status'> = {}): Promise<CaseListResponse> =>
    casesApi.list({
      ...filters,
      status:   ['UNDER_REVIEW', 'SUBMITTED', 'PENDING_CLARIFICATION'],
      sort_by:  'priority',
      sort_dir: 'desc',
    }),
}
