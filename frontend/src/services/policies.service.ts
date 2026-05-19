import http from './http.service'

type Api<T> = { success: boolean; data: T; meta: Record<string, unknown> }

export type PolicyProcessingStatus = 'UPLOADED' | 'EXTRACTED' | 'CHUNKED' | 'EMBEDDED' | 'STORED' | 'FAILED'
export type PolicyEmbeddingStatus = 'NONE' | 'STORED' | 'DELETED'

export interface PolicyListItem {
  id: string
  policy_key: string
  policy_name: string
  policy_version: string
  policy_type?: string | null
  effective_date?: string | null
  upload_date: string
  total_chunks: number
  processing_status: PolicyProcessingStatus
  embedding_status: PolicyEmbeddingStatus
  pinecone_namespace: string
  original_filename: string
  last_processed_at?: string | null
  last_error?: string | null
}

export interface PolicyListResponse {
  items: PolicyListItem[]
  total: number
}

export interface PolicyChunkItem {
  id: string
  chunk_index: number
  chunk_length: number
  chunk_overlap: number
  preview: string
  cpt_codes: string[]
  icd_codes: string[]
  metadata: Record<string, unknown>
}

export interface PolicyChunkListResponse {
  items: PolicyChunkItem[]
  total: number
}

export const policiesService = {
  async listPolicies(params?: { page?: number; page_size?: number; search?: string; status?: PolicyProcessingStatus; namespace?: string }) {
    return http.get<Api<PolicyListResponse>>('/policies', { params })
  },

  async uploadPolicy(formData: FormData) {
    return http.upload<Api<{ policy_id: string; policy_key: string }>>('/policies', formData)
  },

  async processPolicy(policyId: string) {
    return http.post<Api<{ policy_id: string; status: PolicyProcessingStatus; total_chunks: number; warnings: string[] }>>(
      `/policies/${policyId}/process`,
    )
  },

  async listChunks(policyId: string, params?: { page?: number; page_size?: number }) {
    return http.get<Api<PolicyChunkListResponse>>(`/policies/${policyId}/chunks`, { params })
  },

  async deleteEmbeddings(policyId: string) {
    return http.delete<Api<{ deleted_vectors: number }>>(`/policies/${policyId}/embeddings`)
  },

  async deleteChunks(policyId: string) {
    return http.delete<Api<{ deleted_chunks: number }>>(`/policies/${policyId}/chunks`)
  },

  async deletePolicy(policyId: string) {
    return http.delete<Api<{ deleted_vectors: number; deleted_policy_id: string }>>(`/policies/${policyId}`)
  },
}
