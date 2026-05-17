import { useEffect, useState } from 'react'
import { useQuery }            from '@tanstack/react-query'
import { metricsApi, type MetricsResponse } from '@/api/metrics'
import { APP_CONFIG }          from '@/config/app.config'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface KPIMetrics {
  totalCases:    number
  approvedCases: number
  deniedCases:   number
  pendingCases:  number
  inReviewCases: number
  approvalRate:  number
  denialRate:    number
  avgReviewMs:   number
  aiAccuracy:    number
  weekDelta:     { total: number; approved: number; denied: number; pending: number }
}

export interface TrendPoint {
  date:    string
  high:    number
  good:    number
  medium:  number
  low:     number
  critical:number
}

export interface ReviewerLoad {
  name:      string
  approved:  number
  denied:    number
  inReview:  number
  pending:   number
}

export interface SystemStats {
  ocrSuccessRate:       number
  llmLatencyP50:        number
  llmLatencyP95:        number
  llmLatencyP99:        number
  policyRetrievalMs:    number
  tokenUsageToday:      number
  tokenBudgetDaily:     number
  guardrailTriggers:    number
  avgConfidence:        number
}

export interface ActivityEvent {
  id:         string
  type:       'ai_complete' | 'ocr_complete' | 'policy_match' | 'low_confidence' | 'guardrail' | 'recommendation' | 'escalated'
  caseId:     string
  patient?:   string
  message:    string
  confidence?: number
  severity:   'info' | 'success' | 'warning' | 'error'
  timestamp:  Date
}

export interface ClarificationPoint {
  date:      string
  patient:   number
  records:   number
  policy:    number
}

export interface OutcomePoint {
  name:  string
  value: number
  color: string
}

// ─── Deterministic mock generator (stable across renders) ────────────────────

function seeded(n: number, range: number, offset = 0) {
  return Math.round(offset + ((Math.sin(n * 9301 + 49297) * 233 + 23) % 1) * range)
}

function buildKPI(tick: number): KPIMetrics {
  const base = 1247 + seeded(tick, 12)
  const appr  = Math.round(base * 0.508) + seeded(tick, 5)
  const deny  = Math.round(base * 0.232) + seeded(tick, 3)
  const pend  = base - appr - deny - 34
  return {
    totalCases:    base,
    approvedCases: appr,
    deniedCases:   deny,
    pendingCases:  pend,
    inReviewCases: 34 + seeded(tick, 4),
    approvalRate:  appr / base,
    denialRate:    deny / base,
    avgReviewMs:   3500 + seeded(tick, 500) - 250,
    aiAccuracy:    0.942 + (seeded(tick, 20) - 10) / 1000,
    weekDelta: {
      total:    12 + seeded(tick, 4) - 2,
      approved:  8 + seeded(tick, 3) - 1,
      denied:    2 + seeded(tick, 2) - 1,
      pending:  -3 + seeded(tick, 2) - 1,
    },
  }
}

function buildTrend(): TrendPoint[] {
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  return days.map((d, i) => ({
    date:     d,
    high:     75 + seeded(i, 15),
    good:     55 + seeded(i + 10, 20),
    medium:   35 + seeded(i + 20, 15),
    low:      15 + seeded(i + 30, 10),
    critical: 5  + seeded(i + 40, 5),
  }))
}

function buildReviewerLoad(): ReviewerLoad[] {
  return [
    { name: 'Dr. S. Chen',    approved: 42, denied: 18, inReview: 7, pending: 23 },
    { name: 'Dr. M. Torres',  approved: 38, denied: 22, inReview: 5, pending: 31 },
    { name: 'Dr. J. Park',    approved: 55, denied: 14, inReview: 9, pending: 18 },
    { name: 'Dr. A. Williams',approved: 29, denied: 11, inReview: 4, pending: 42 },
    { name: 'Dr. R. Patel',   approved: 47, denied: 19, inReview: 6, pending: 27 },
  ]
}

function buildSystemStats(tick: number): SystemStats {
  return {
    ocrSuccessRate:    0.974 + (seeded(tick, 10) - 5) / 1000,
    llmLatencyP50:     1200 + seeded(tick, 200) - 100,
    llmLatencyP95:     2800 + seeded(tick, 400) - 200,
    llmLatencyP99:     4100 + seeded(tick, 600) - 300,
    policyRetrievalMs: 45   + seeded(tick, 20) - 10,
    tokenUsageToday:   47832 + seeded(tick, 2000),
    tokenBudgetDaily:  100_000,
    guardrailTriggers: 3 + seeded(tick, 2),
    avgConfidence:     0.847 + (seeded(tick, 20) - 10) / 1000,
  }
}

function buildClarifications(): ClarificationPoint[] {
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  return days.map((d, i) => ({
    date:    d,
    patient: 8  + seeded(i, 6),
    records: 12 + seeded(i + 5, 8),
    policy:  5  + seeded(i + 10, 4),
  }))
}

const OUTCOME_DATA: OutcomePoint[] = [
  { name: 'Approved',  value: 634, color: '#10b981' },
  { name: 'Denied',    value: 289, color: '#ef4444' },
  { name: 'Pended',    value: 201, color: '#f59e0b' },
  { name: 'Escalated', value: 123, color: '#8b5cf6' },
]

// ─── Activity feed generator ──────────────────────────────────────────────────

const FEED_POOL: Omit<ActivityEvent, 'id' | 'timestamp'>[] = [
  { type: 'ai_complete',   caseId: 'PA-2024-1247', patient: 'James M.',  message: 'Analysis complete — APPROVE recommended', confidence: 0.942, severity: 'success' },
  { type: 'ocr_complete',  caseId: 'PA-2024-1246', patient: 'Sarah K.',  message: '14 pages extracted, 98.2% confidence', severity: 'info' },
  { type: 'policy_match',  caseId: 'PA-2024-1245', patient: 'Robert T.', message: '4 of 5 criteria met — Prior Auth criteria', confidence: 0.879, severity: 'success' },
  { type: 'low_confidence',caseId: 'PA-2024-1244', patient: 'Lisa P.',   message: 'Low confidence 58.3% — escalated for review', confidence: 0.583, severity: 'warning' },
  { type: 'recommendation',caseId: 'PA-2024-1243', patient: 'David W.',  message: 'DENY recommended — criteria not met', confidence: 0.891, severity: 'error' },
  { type: 'guardrail',     caseId: 'PA-2024-1242', patient: 'Anna R.',   message: 'Reasoning discarded — factual inconsistency', severity: 'warning' },
  { type: 'ai_complete',   caseId: 'PA-2024-1241', patient: 'Mark S.',   message: 'Analysis complete — PEND recommended', confidence: 0.723, severity: 'info' },
  { type: 'escalated',     caseId: 'PA-2024-1240', patient: 'Carol H.',  message: 'Escalated to senior reviewer', severity: 'warning' },
]

function randomEvent(): ActivityEvent {
  const base = FEED_POOL[Math.floor(Math.random() * FEED_POOL.length)]
  return { ...base, id: crypto.randomUUID(), timestamp: new Date() }
}

// ─── Metrics → KPI transform ──────────────────────────────────────────────────

function toKPIMetrics(m: MetricsResponse): KPIMetrics {
  return {
    totalCases:    m.total_cases,
    approvedCases: m.approved_cases,
    deniedCases:   m.denied_cases,
    pendingCases:  m.pending_cases,
    inReviewCases: m.in_review_cases,
    approvalRate:  m.approval_rate,
    denialRate:    m.denial_rate,
    avgReviewMs:   m.avg_review_ms,
    aiAccuracy:    m.ai_accuracy,
    weekDelta:     m.week_delta,
  }
}

// ─── Hooks ────────────────────────────────────────────────────────────────────

export function useKPIMetrics() {
  return useQuery({
    queryKey:        ['dashboard', 'kpi'],
    queryFn:         async () => {
      const m = await metricsApi.get()
      return toKPIMetrics(m)
    },
    staleTime:       APP_CONFIG.cache.metricsStaleMs,
    refetchInterval: APP_CONFIG.cache.metricsStaleMs,
    // Show mock data immediately while first fetch runs
    placeholderData: (prev) => prev ?? buildKPI(0),
    // Don't let a failing metrics endpoint break the whole dashboard
    retry: (count, err: any) => err?.statusCode >= 500 && count < 2,
  })
}

export function useConfidenceTrend() {
  return useQuery({
    queryKey:  ['dashboard', 'confidence-trend'],
    queryFn:   () => Promise.resolve(buildTrend()),
    staleTime: 60_000,
    placeholderData: buildTrend(),
  })
}

export function useReviewerLoad() {
  return useQuery({
    queryKey:  ['dashboard', 'reviewer-load'],
    queryFn:   () => Promise.resolve(buildReviewerLoad()),
    staleTime: 30_000,
    placeholderData: buildReviewerLoad(),
  })
}

export function useSystemStats() {
  return useQuery({
    queryKey:        ['dashboard', 'system'],
    queryFn:         () => Promise.resolve(buildSystemStats(Math.floor(Date.now() / 15_000))),
    staleTime:       12_000,
    refetchInterval: 15_000,
    placeholderData: (prev) => prev ?? buildSystemStats(0),
  })
}

export function useClarifications() {
  return useQuery({
    queryKey:  ['dashboard', 'clarifications'],
    queryFn:   () => Promise.resolve(buildClarifications()),
    staleTime: 60_000,
    placeholderData: buildClarifications(),
  })
}

export function useOutcomes() {
  return useQuery({
    queryKey:  ['dashboard', 'outcomes'],
    queryFn:   () => Promise.resolve(OUTCOME_DATA),
    staleTime: 60_000,
    placeholderData: OUTCOME_DATA,
  })
}

export function useActivityFeed() {
  const [events, setEvents] = useState<ActivityEvent[]>(() =>
    Array.from({ length: 6 }, (_, i) => ({
      ...FEED_POOL[i % FEED_POOL.length],
      id: `init-${i}`,
      timestamp: new Date(Date.now() - i * 45_000),
    }))
  )

  useEffect(() => {
    const t = setInterval(() => {
      setEvents((prev) => [randomEvent(), ...prev].slice(0, 20))
    }, 4_000 + Math.random() * 3_000)
    return () => clearInterval(t)
  }, [])

  return events
}
