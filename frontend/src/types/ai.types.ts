export interface AIWorkflowResult {
  caseId: string
  runId: string
  recommendation: 'APPROVE' | 'DENY' | 'REQUEST_INFO' | 'ESCALATE'
  confidence: number
  rationale: AIRationale
  processingTimeMs: number
  modelTier: 'SMALL' | 'MEDIUM' | 'LARGE'
  modelId: string
  completedAt: string
}

export interface AIRationale {
  summary: string
  reasoningSteps: ReasoningStep[]
  caveats: string[]
  policyReferences: string[]
  groundingScore: number
  promptInjectionFlagged: boolean
}

export interface ReasoningStep {
  stepName: string
  content: string
  durationMs?: number
}

export interface GuardrailResult {
  passed: boolean
  checks: GuardrailCheck[]
}

export interface GuardrailCheck {
  name: string
  passed: boolean
  severity?: 'LOW' | 'MEDIUM' | 'HIGH'
  detail?: string
}

export interface Clarification {
  id: string
  caseId: string
  question: string
  askedBy: 'AI' | 'REVIEWER'
  askedAt: string
  response?: string
  respondedAt?: string
  status: 'PENDING' | 'ANSWERED' | 'DISMISSED'
}