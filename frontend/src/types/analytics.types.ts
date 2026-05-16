export interface PlatformMetrics {
  totalCases: number
  pendingReview: number
  approvedToday: number
  deniedToday: number
  avgAiConfidence: number
  avgReviewTimeMs: number
  aiAccuracyRate: number
  humanOverrideRate: number
  escalationRate: number
  complianceScore: number
}

export interface TrendPoint {
  date: string
  value: number
}

export interface AnalyticsSeries {
  label: string
  color: string
  data: TrendPoint[]
}

export interface WorkflowLatency {
  stageName: string
  p50: number
  p95: number
  p99: number
}

export interface OutcomeDistribution {
  outcome: string
  count: number
  percentage: number
  color: string
}