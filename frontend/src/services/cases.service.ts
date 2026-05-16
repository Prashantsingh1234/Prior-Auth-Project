import http from './http.service'
import type { PACase, CaseListItem, PaginatedCases, CaseFilters } from '@/types'
import type { PaginationParams } from '@/types'

const BASE = '/cases'

export const casesService = {
  list(filters?: CaseFilters, pagination?: PaginationParams): Promise<PaginatedCases> {
    return http.get(BASE, { params: { ...filters, ...pagination } })
  },

  get(caseId: string): Promise<PACase> {
    return http.get(`${BASE}/${caseId}`)
  },

  create(payload: FormData): Promise<PACase> {
    return http.upload(`/pa-requests`, payload)
  },

  uploadDocument(
    caseId: string,
    file: File,
    documentType: string,
    onProgress?: (pct: number) => void,
  ): Promise<{ id: string; filename: string }> {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('document_type', documentType)
    return http.upload(`${BASE}/${caseId}/documents`, fd, onProgress)
  },

  triggerAIProcessing(caseId: string): Promise<{ runId: string }> {
    return http.post(`${BASE}/${caseId}/process`)
  },

  getAIResult(caseId: string): Promise<import('@/types').AIWorkflowResult> {
    return http.get(`${BASE}/${caseId}/ai-result`)
  },
}