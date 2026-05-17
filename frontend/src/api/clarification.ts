import http from '@/services/http.service'
import type { ClarificationRequest } from './types'

export interface ClarificationResponsePayload {
  response: string
}

export const clarificationApi = {
  respond(clarificationId: string, response: string): Promise<ClarificationRequest> {
    return http.post<ClarificationRequest, ClarificationResponsePayload>(
      `/clarification/${clarificationId}`,
      { response },
    )
  },
}
