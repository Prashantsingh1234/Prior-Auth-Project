import { apiClient } from './client'
import type {
  ApiResponse,
  ApproveRequest,
  DenyRequest,
  EscalateRequest,
  PACase,
  PendRequest,
  AddNoteRequest,
} from './types'

export const reviewApi = {
  approve: async (caseId: string, body: ApproveRequest): Promise<PACase> => {
    const { data } = await apiClient.post<ApiResponse<PACase>>(
      `/review/${caseId}/approve`,
      body,
    )
    return data.data
  },

  deny: async (caseId: string, body: DenyRequest): Promise<PACase> => {
    const { data } = await apiClient.post<ApiResponse<PACase>>(
      `/review/${caseId}/deny`,
      body,
    )
    return data.data
  },

  pend: async (caseId: string, body: PendRequest): Promise<PACase> => {
    const { data } = await apiClient.post<ApiResponse<PACase>>(
      `/review/${caseId}/pend`,
      body,
    )
    return data.data
  },

  escalate: async (caseId: string, body: EscalateRequest): Promise<PACase> => {
    const { data } = await apiClient.post<ApiResponse<PACase>>(
      `/review/${caseId}/escalate`,
      body,
    )
    return data.data
  },

  addNote: async (caseId: string, body: AddNoteRequest): Promise<void> => {
    await apiClient.post(`/review/${caseId}/notes`, body)
  },

  assign: async (caseId: string, reviewerId: string): Promise<PACase> => {
    const { data } = await apiClient.post<ApiResponse<PACase>>(
      `/review/${caseId}/assign`,
      { reviewer_id: reviewerId },
    )
    return data.data
  },

  respondToClarification: async (
    caseId: string,
    clarificationId: string,
    response: string,
  ): Promise<void> => {
    await apiClient.post(`/review/${caseId}/clarifications/${clarificationId}/respond`, {
      response,
    })
  },
}
