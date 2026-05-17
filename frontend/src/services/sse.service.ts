import { APP_CONFIG } from '@/config/app.config'

// ─── SSE event types ──────────────────────────────────────────────────────────

export type SSEEventType = 'token' | 'step' | 'complete' | 'error' | 'progress'

export interface SSETokenEvent {
  type:    'token'
  token:   string
  index:   number
}

export interface SSEStepEvent {
  type:    'step'
  label:   string
  stage:   string
  index:   number
}

export interface SSECompleteEvent {
  type:        'complete'
  totalTokens: number
  latencyMs:   number
  traceId:     string
}

export interface SSEProgressEvent {
  type:     'progress'
  progress: number
  message:  string
}

export interface SSEErrorEvent {
  type:    'error'
  code:    string
  message: string
}

export type SSEPayload = SSETokenEvent | SSEStepEvent | SSECompleteEvent | SSEProgressEvent | SSEErrorEvent

type SSEListener = (event: SSEPayload) => void

// ─── SSE stream handle ────────────────────────────────────────────────────────

export interface SSEStreamHandle {
  close:    () => void
  streamId: string
}

// ─── Service ──────────────────────────────────────────────────────────────────

function readToken(): string | null {
  try {
    const raw = localStorage.getItem('pa-auth')
    if (!raw) return null
    return JSON.parse(raw)?.state?.tokens?.accessToken ?? null
  } catch { return null }
}

export function openSSEStream(
  endpoint: string,
  onEvent: SSEListener,
  onError?: (err: Event) => void,
): SSEStreamHandle {
  const streamId = crypto.randomUUID()
  const token    = readToken()
  const base     = APP_CONFIG.api.baseUrl

  const url = new URL(`${base}${endpoint}`, window.location.origin)
  if (token) url.searchParams.set('token', token)
  url.searchParams.set('stream_id', streamId)

  const es = new EventSource(url.toString())

  es.onmessage = (e) => {
    try {
      const payload = JSON.parse(e.data) as SSEPayload
      onEvent(payload)
    } catch {
      // malformed — ignore
    }
  }

  es.addEventListener('token',    (e) => { try { onEvent(JSON.parse((e as MessageEvent).data)) } catch {} })
  es.addEventListener('step',     (e) => { try { onEvent(JSON.parse((e as MessageEvent).data)) } catch {} })
  es.addEventListener('complete', (e) => { try { onEvent(JSON.parse((e as MessageEvent).data)); es.close() } catch {} })
  es.addEventListener('error',    (e) => { try { onEvent(JSON.parse((e as MessageEvent).data)) } catch {} })
  es.addEventListener('progress', (e) => { try { onEvent(JSON.parse((e as MessageEvent).data)) } catch {} })

  es.onerror = (e) => {
    onError?.(e)
    es.close()
  }

  return {
    streamId,
    close: () => es.close(),
  }
}

// ─── Mock SSE for development ─────────────────────────────────────────────────

const MOCK_REASONING_STEPS = [
  { label: 'Loading policy criteria',   stage: 'retrieval' },
  { label: 'Retrieving clinical docs',  stage: 'retrieval' },
  { label: 'Analyzing ICD codes',       stage: 'reasoning' },
  { label: 'Evaluating CPT codes',      stage: 'reasoning' },
  { label: 'Applying policy rules',     stage: 'reasoning' },
  { label: 'Checking prior auth rules', stage: 'reasoning' },
  { label: 'Computing confidence',      stage: 'decision'  },
  { label: 'Generating rationale',      stage: 'decision'  },
  { label: 'Final decision assembly',   stage: 'decision'  },
]

const MOCK_TOKENS = [
  'Based', ' on', ' the', ' clinical', ' documentation', ' provided,', ' this', ' request',
  ' for', ' Total', ' Knee', ' Arthroplasty', ' meets', ' the', ' established', ' medical',
  ' necessity', ' criteria.', ' The', ' patient', ' demonstrates', ' significant', ' functional',
  ' impairment,', ' radiographic', ' evidence', ' of', ' severe', ' osteoarthritis,', ' and',
  ' failure', ' of', ' conservative', ' treatments', ' over', ' 6+', ' months.', ' Confidence:',
  ' 0.94.',
]

export function openMockSSEStream(
  _endpoint: string,
  onEvent: SSEListener,
  delayMs = 60,
): SSEStreamHandle {
  const streamId = crypto.randomUUID()
  let cancelled  = false
  let timer: ReturnType<typeof setTimeout>

  async function run() {
    for (let i = 0; i < MOCK_REASONING_STEPS.length && !cancelled; i++) {
      await new Promise<void>((res) => { timer = setTimeout(res, delayMs * 4) })
      if (cancelled) break
      onEvent({ type: 'step', label: MOCK_REASONING_STEPS[i].label, stage: MOCK_REASONING_STEPS[i].stage, index: i })
    }

    for (let i = 0; i < MOCK_TOKENS.length && !cancelled; i++) {
      await new Promise<void>((res) => { timer = setTimeout(res, delayMs) })
      if (cancelled) break
      onEvent({ type: 'token', token: MOCK_TOKENS[i], index: i })
    }

    if (!cancelled) {
      onEvent({ type: 'complete', totalTokens: MOCK_TOKENS.length, latencyMs: 1840, traceId: streamId })
    }
  }

  run()

  return {
    streamId,
    close: () => { cancelled = true; clearTimeout(timer) },
  }
}
