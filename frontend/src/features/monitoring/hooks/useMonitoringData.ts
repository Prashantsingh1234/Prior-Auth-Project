import { useState, useEffect, useCallback } from 'react'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface MetricPoint { t: number; v: number }

export interface LiveMetrics {
  hallucinationRate:    MetricPoint[]
  groundingScore:       MetricPoint[]
  retrievalQuality:     MetricPoint[]
  ocrAccuracy:          MetricPoint[]
  clarificationFreq:    MetricPoint[]
  modelLatency:         MetricPoint[]
  tokenUsage:           MetricPoint[]
  fallbackFrequency:    MetricPoint[]
  queueBacklog:         MetricPoint[]
  reviewerAgreement:    MetricPoint[]
}

export interface TraceSpan {
  id:        string
  name:      string
  type:      'llm' | 'retrieval' | 'ocr' | 'tool' | 'chain' | 'eval'
  startMs:   number
  durationMs: number
  tokens?:   { input: number; output: number }
  model?:    string
  status:    'success' | 'error' | 'warning'
  metadata?: Record<string, string | number>
}

export interface AITrace {
  id:          string
  caseId:      string
  caseRef:     string
  triggeredAt: string
  totalMs:     number
  status:      'success' | 'error' | 'warning'
  spans:       TraceSpan[]
  inputTokens: number
  outputTokens: number
  decision:    string
  confidence:  number
  groundingScore: number
  hallucinationFlag: boolean
  model:       string
  fallbackUsed: boolean
}

export interface ModelMetrics {
  model:          string
  provider:       string
  color:          string
  avgLatencyMs:   number
  p95LatencyMs:   number
  inputTokens:    number
  outputTokens:   number
  costPerK:       number
  errorRate:      number
  hallucinationRate: number
  groundingScore: number
  throughput:     number
  fallbackRate:   number
}

export interface EvaluatorScore {
  criterion:    string
  score:        number
  trend:        number
  passRate:     number
  sampleCount:  number
  breakdown:    { label: string; count: number; color: string }[]
}

export interface MonitoringSnapshot {
  hallucinationRate:  number
  groundingScore:     number
  retrievalQuality:   number
  ocrAccuracy:        number
  clarificationFreq:  number
  modelLatency:       number
  tokenUsage:         number
  fallbackFrequency:  number
  queueBacklog:       number
  reviewerAgreement:  number
}

// ─── Seeded PRNG ──────────────────────────────────────────────────────────────

function seeded(n: number) {
  return Math.abs(Math.sin(n * 9301 + 49297) % 1)
}

// ─── Initial history (60 points = 2 minutes at 2s interval) ──────────────────

function makeHistory(
  base: number,
  amp: number,
  seed: number,
  count = 60,
): MetricPoint[] {
  const now = Date.now()
  return Array.from({ length: count }, (_, i) => ({
    t: now - (count - i) * 2000,
    v: Math.max(0, Math.min(100, base + (seeded(seed + i) - 0.5) * amp * 2)),
  }))
}

function buildInitialMetrics(): LiveMetrics {
  return {
    hallucinationRate:  makeHistory(3.2,  2.5,  1),
    groundingScore:     makeHistory(87.4, 4.0,  2),
    retrievalQuality:   makeHistory(91.2, 3.0,  3),
    ocrAccuracy:        makeHistory(96.8, 2.0,  4),
    clarificationFreq:  makeHistory(12.1, 4.0,  5),
    modelLatency:       makeHistory(1420, 200,  6),
    tokenUsage:         makeHistory(2340, 300,  7),
    fallbackFrequency:  makeHistory(4.1,  2.0,  8),
    queueBacklog:       makeHistory(18,   8.0,  9),
    reviewerAgreement:  makeHistory(88.6, 3.5, 10),
  }
}

// ─── Mock traces ──────────────────────────────────────────────────────────────

const CASE_REFS = ['PA-2024-001', 'PA-2024-002', 'PA-2024-003', 'PA-2024-004', 'PA-2024-005',
                   'PA-2024-006', 'PA-2024-007', 'PA-2024-008']
const DECISIONS = ['APPROVE', 'DENY', 'PEND', 'APPROVE', 'APPROVE', 'DENY', 'PEND', 'APPROVE']
const MODELS    = ['claude-sonnet-4-6', 'claude-haiku-4-5', 'claude-sonnet-4-6', 'claude-opus-4-7',
                   'claude-sonnet-4-6', 'claude-haiku-4-5', 'claude-sonnet-4-6', 'claude-sonnet-4-6']

function makeSpans(totalMs: number, seed: number): TraceSpan[] {
  const spans: TraceSpan[] = []
  let cursor = 0

  const defs: Array<Omit<TraceSpan, 'id' | 'startMs' | 'durationMs'> & { dur: number }> = [
    { name: 'ocr.extract',       type: 'ocr',      dur: Math.round(totalMs * 0.08 + seeded(seed + 0) * 50), status: 'success', model: undefined,               tokens: undefined,           metadata: { pages: 4, chars: 2847 } },
    { name: 'retrieve.chunks',   type: 'retrieval', dur: Math.round(totalMs * 0.12 + seeded(seed + 1) * 80), status: 'success', model: 'text-embedding-3-large', tokens: { input: 512, output: 0 }, metadata: { chunks: 24, filtered: 11 } },
    { name: 'llm.classify',      type: 'llm',       dur: Math.round(totalMs * 0.15 + seeded(seed + 2) * 120), status: 'success', model: 'claude-haiku-4-5',     tokens: { input: 890, output: 220 }, metadata: { temperature: 0.1 } },
    { name: 'llm.evaluate',      type: 'llm',       dur: Math.round(totalMs * 0.35 + seeded(seed + 3) * 200), status: seeded(seed + 10) > 0.85 ? 'warning' : 'success', model: 'claude-sonnet-4-6', tokens: { input: 2840, output: 680 }, metadata: { criteria: 6 } },
    { name: 'eval.groundedness', type: 'eval',      dur: Math.round(totalMs * 0.08 + seeded(seed + 4) * 40), status: 'success', model: undefined,               tokens: undefined,           metadata: { score: (0.82 + seeded(seed + 5) * 0.15).toFixed(2) } },
    { name: 'llm.rationale',     type: 'llm',       dur: Math.round(totalMs * 0.18 + seeded(seed + 6) * 150), status: 'success', model: 'claude-sonnet-4-6',    tokens: { input: 1240, output: 420 }, metadata: {} },
    { name: 'chain.aggregate',   type: 'chain',     dur: Math.round(totalMs * 0.04 + seeded(seed + 7) * 20), status: 'success', model: undefined,               tokens: undefined,           metadata: {} },
  ]

  for (const d of defs) {
    spans.push({ id: `span-${seed}-${spans.length}`, startMs: cursor, durationMs: d.dur, name: d.name, type: d.type, status: d.status, model: d.model, tokens: d.tokens, metadata: d.metadata })
    cursor += d.dur
  }
  return spans
}

function buildTraces(): AITrace[] {
  return Array.from({ length: 20 }, (_, i) => {
    const totalMs = Math.round(1100 + seeded(i * 3) * 1800)
    const spans = makeSpans(totalMs, i * 7)
    const inputT  = spans.reduce((s, sp) => s + (sp.tokens?.input  ?? 0), 0)
    const outputT = spans.reduce((s, sp) => s + (sp.tokens?.output ?? 0), 0)
    const minsAgo = Math.round(seeded(i * 5) * 120)
    const d = new Date(Date.now() - minsAgo * 60000)
    return {
      id:               `trace-${i.toString().padStart(3, '0')}`,
      caseId:           `case-${i + 1}`,
      caseRef:          CASE_REFS[i % CASE_REFS.length],
      triggeredAt:      d.toISOString(),
      totalMs,
      status:           seeded(i * 11) > 0.9 ? 'error' : seeded(i * 11) > 0.75 ? 'warning' : 'success',
      spans,
      inputTokens:      inputT,
      outputTokens:     outputT,
      decision:         DECISIONS[i % DECISIONS.length],
      confidence:       Math.round((0.60 + seeded(i * 13) * 0.38) * 100),
      groundingScore:   Math.round((0.78 + seeded(i * 17) * 0.20) * 100),
      hallucinationFlag: seeded(i * 19) > 0.88,
      model:            MODELS[i % MODELS.length],
      fallbackUsed:     seeded(i * 23) > 0.88,
    }
  })
}

// ─── Model comparison data ────────────────────────────────────────────────────

const INITIAL_MODELS: ModelMetrics[] = [
  {
    model: 'claude-sonnet-4-6', provider: 'Anthropic', color: '#6366f1',
    avgLatencyMs: 1420, p95LatencyMs: 2180, inputTokens: 2840000, outputTokens: 680000,
    costPerK: 3.0, errorRate: 0.8, hallucinationRate: 2.1, groundingScore: 91.4,
    throughput: 142, fallbackRate: 1.2,
  },
  {
    model: 'claude-haiku-4-5', provider: 'Anthropic', color: '#0ea5e9',
    avgLatencyMs: 380, p95LatencyMs: 620, inputTokens: 890000, outputTokens: 220000,
    costPerK: 0.25, errorRate: 1.2, hallucinationRate: 4.8, groundingScore: 84.2,
    throughput: 387, fallbackRate: 0.4,
  },
  {
    model: 'claude-opus-4-7', provider: 'Anthropic', color: '#8b5cf6',
    avgLatencyMs: 3240, p95LatencyMs: 4890, inputTokens: 1240000, outputTokens: 420000,
    costPerK: 15.0, errorRate: 0.3, hallucinationRate: 0.9, groundingScore: 95.8,
    throughput: 48, fallbackRate: 0.1,
  },
  {
    model: 'text-embedding-3-large', provider: 'OpenAI', color: '#10b981',
    avgLatencyMs: 95, p95LatencyMs: 180, inputTokens: 5120000, outputTokens: 0,
    costPerK: 0.13, errorRate: 0.2, hallucinationRate: 0, groundingScore: 0,
    throughput: 1240, fallbackRate: 0.0,
  },
]

// ─── Evaluator analytics ──────────────────────────────────────────────────────

const INITIAL_EVALUATORS: EvaluatorScore[] = [
  {
    criterion: 'Medical Necessity',
    score: 87.4, trend: 2.1, passRate: 91.2, sampleCount: 284,
    breakdown: [
      { label: 'Pass',    count: 259, color: '#10b981' },
      { label: 'Fail',    count: 18,  color: '#ef4444' },
      { label: 'Partial', count: 7,   color: '#f59e0b' },
    ],
  },
  {
    criterion: 'Clinical Guidelines',
    score: 82.1, trend: -1.3, passRate: 88.4, sampleCount: 284,
    breakdown: [
      { label: 'Pass',    count: 251, color: '#10b981' },
      { label: 'Fail',    count: 24,  color: '#ef4444' },
      { label: 'Partial', count: 9,   color: '#f59e0b' },
    ],
  },
  {
    criterion: 'Policy Compliance',
    score: 91.8, trend: 0.7, passRate: 94.7, sampleCount: 284,
    breakdown: [
      { label: 'Pass',    count: 269, color: '#10b981' },
      { label: 'Fail',    count: 10,  color: '#ef4444' },
      { label: 'Partial', count: 5,   color: '#f59e0b' },
    ],
  },
  {
    criterion: 'Evidence Grounding',
    score: 88.9, trend: 3.4, passRate: 92.6, sampleCount: 284,
    breakdown: [
      { label: 'Pass',    count: 263, color: '#10b981' },
      { label: 'Fail',    count: 14,  color: '#ef4444' },
      { label: 'Partial', count: 7,   color: '#f59e0b' },
    ],
  },
  {
    criterion: 'Rationale Clarity',
    score: 79.3, trend: -0.4, passRate: 85.6, sampleCount: 284,
    breakdown: [
      { label: 'Pass',    count: 243, color: '#10b981' },
      { label: 'Fail',    count: 28,  color: '#ef4444' },
      { label: 'Partial', count: 13,  color: '#f59e0b' },
    ],
  },
  {
    criterion: 'Hallucination-Free',
    score: 96.8, trend: 0.2, passRate: 97.5, sampleCount: 284,
    breakdown: [
      { label: 'Pass',    count: 277, color: '#10b981' },
      { label: 'Fail',    count: 5,   color: '#ef4444' },
      { label: 'Partial', count: 2,   color: '#f59e0b' },
    ],
  },
]

// ─── Hook ─────────────────────────────────────────────────────────────────────

const WINDOW = 60
const TICK_MS = 2000

export function useMonitoringData() {
  const [metrics, setMetrics]       = useState<LiveMetrics>(buildInitialMetrics)
  const [snapshot, setSnapshot]     = useState<MonitoringSnapshot>(() => ({
    hallucinationRate: 3.2, groundingScore: 87.4, retrievalQuality: 91.2,
    ocrAccuracy: 96.8, clarificationFreq: 12.1, modelLatency: 1420,
    tokenUsage: 2340, fallbackFrequency: 4.1, queueBacklog: 18, reviewerAgreement: 88.6,
  }))
  const [traces]                    = useState<AITrace[]>(buildTraces)
  const [models]                    = useState<ModelMetrics[]>(INITIAL_MODELS)
  const [evaluators]                = useState<EvaluatorScore[]>(INITIAL_EVALUATORS)
  const [selectedTrace, setTrace]   = useState<AITrace | null>(null)
  const [streamTick, setStreamTick] = useState(0)

  const tick = useCallback(() => {
    setMetrics((prev) => {
      const now = Date.now()
      function next(
        arr: MetricPoint[],
        base: number,
        amp: number,
        seed: number,
      ): MetricPoint[] {
        const last = arr[arr.length - 1]?.v ?? base
        const noise = (seeded(now + seed) - 0.5) * amp
        const mean  = base
        const v     = Math.max(0, Math.min(base * 1.5, last + (mean - last) * 0.05 + noise))
        return [...arr.slice(-WINDOW + 1), { t: now, v }]
      }
      const updated: LiveMetrics = {
        hallucinationRate:  next(prev.hallucinationRate,  3.2,  1.2, 1),
        groundingScore:     next(prev.groundingScore,     87.4, 2.0, 2),
        retrievalQuality:   next(prev.retrievalQuality,   91.2, 1.5, 3),
        ocrAccuracy:        next(prev.ocrAccuracy,        96.8, 1.0, 4),
        clarificationFreq:  next(prev.clarificationFreq,  12.1, 2.0, 5),
        modelLatency:       next(prev.modelLatency,       1420, 100, 6),
        tokenUsage:         next(prev.tokenUsage,         2340, 150, 7),
        fallbackFrequency:  next(prev.fallbackFrequency,  4.1,  1.0, 8),
        queueBacklog:       next(prev.queueBacklog,       18,   4.0, 9),
        reviewerAgreement:  next(prev.reviewerAgreement,  88.6, 1.8, 10),
      }
      function last(arr: MetricPoint[]) { return arr[arr.length - 1]!.v }
      setSnapshot({
        hallucinationRate:  last(updated.hallucinationRate),
        groundingScore:     last(updated.groundingScore),
        retrievalQuality:   last(updated.retrievalQuality),
        ocrAccuracy:        last(updated.ocrAccuracy),
        clarificationFreq:  last(updated.clarificationFreq),
        modelLatency:       last(updated.modelLatency),
        tokenUsage:         last(updated.tokenUsage),
        fallbackFrequency:  last(updated.fallbackFrequency),
        queueBacklog:       last(updated.queueBacklog),
        reviewerAgreement:  last(updated.reviewerAgreement),
      })
      return updated
    })
    setStreamTick((n) => n + 1)
  }, [])

  useEffect(() => {
    const id = setInterval(tick, TICK_MS)
    return () => clearInterval(id)
  }, [tick])

  return { metrics, snapshot, traces, models, evaluators, selectedTrace, setTrace, streamTick }
}
