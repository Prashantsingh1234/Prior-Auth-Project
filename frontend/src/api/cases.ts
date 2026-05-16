import { apiClient } from './client'
import type { ApiResponse, CaseFilters, CaseListItem, CaseListResponse, PACase } from './types'

export const casesApi = {
  list: async (filters: CaseFilters = {}): Promise<CaseListResponse> => {
    const params: Record<string, unknown> = {
      page: filters.page ?? 1,
      page_size: filters.page_size ?? 20,
      sort_by: filters.sort_by ?? 'submitted_at',
      sort_dir: filters.sort_dir ?? 'desc',
    }
    if (filters.status?.length)        params.status       = filters.status.join(',')
    if (filters.priority?.length)      params.priority     = filters.priority.join(',')
    if (filters.service_type?.length)  params.service_type = filters.service_type.join(',')
    if (filters.assigned_to_me)        params.assigned_to_me = true

    const { data } = await apiClient.get<ApiResponse<CaseListItem[]>>('/cases', { params })
    return {
      cases: data.data,
      meta:  data.meta!,
    }
  },

  get: async (caseId: string): Promise<PACase> => {
    const { data } = await apiClient.get<ApiResponse<PACase>>(`/cases/${caseId}`)
    return data.data
  },

  getDocument: async (caseId: string, documentId: string): Promise<Blob> => {
    const { data } = await apiClient.get(`/cases/${caseId}/documents/${documentId}`, {
      responseType: 'blob',
    })
    return data
  },

  getDocumentUrl: (caseId: string, documentId: string): string => {
    const token = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'
    return `${token}/cases/${caseId}/documents/${documentId}`
  },

  queue: async (filters: Omit<CaseFilters, 'status'> = {}): Promise<CaseListResponse> => {
    return casesApi.list({
      ...filters,
      status: ['UNDER_REVIEW', 'SUBMITTED', 'PENDING_CLARIFICATION'],
      sort_by: 'priority',
      sort_dir: 'desc',
    })
  },
}
