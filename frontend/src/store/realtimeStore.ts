import { create } from 'zustand'
import type { WSConnectionState, OCRProgressPayload, QueuePayload, SystemAlertPayload, AIThinkingPayload } from '@/services/realtime.service'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface AIStreamState {
  traceId:    string
  caseId:     string
  stage:      'retrieval' | 'reasoning' | 'decision' | 'complete' | 'idle'
  stepLabel:  string
  tokens:     string
  tokensUsed: number
  steps:      Array<{ label: string; stage: string; completedAt: string }>
  startedAt:  string | null
  completedAt: string | null
}

export interface SystemAlert {
  id:        string
  level:     'info' | 'warning' | 'critical'
  service:   string
  message:   string
  code?:     string
  timestamp: string
  dismissed: boolean
}

// ─── State ────────────────────────────────────────────────────────────────────

interface RealtimeState {
  connectionState: WSConnectionState
  lastPingAt:      string | null

  // OCR progress per documentId
  ocrProgress:  Map<string, OCRProgressPayload>

  // AI streaming per caseId
  aiStreams:    Map<string, AIStreamState>

  // Queue snapshot
  queueSnapshot: QueuePayload | null

  // System alerts
  systemAlerts: SystemAlert[]

  // Live case status overrides (caseId → status)
  liveCaseStatuses: Map<string, string>

  // ── Actions ────────────────────────────────────────────────────────────────

  setConnectionState:   (s: WSConnectionState) => void
  setLastPing:          () => void

  upsertOCRProgress:    (p: OCRProgressPayload) => void
  clearOCRProgress:     (documentId: string) => void

  startAIStream:        (payload: AIThinkingPayload) => void
  appendAIToken:        (caseId: string, token: string) => void
  advanceAIStep:        (payload: AIThinkingPayload) => void
  completeAIStream:     (caseId: string) => void
  resetAIStream:        (caseId: string) => void

  setQueueSnapshot:     (q: QueuePayload) => void

  addSystemAlert:       (a: SystemAlertPayload) => void
  dismissAlert:         (id: string) => void
  clearAlerts:          () => void

  setLiveCaseStatus:    (caseId: string, status: string) => void
}

// ─── Store ────────────────────────────────────────────────────────────────────

export const useRealtimeStore = create<RealtimeState>()((set) => ({
  connectionState:  'idle',
  lastPingAt:       null,
  ocrProgress:      new Map(),
  aiStreams:         new Map(),
  queueSnapshot:    null,
  systemAlerts:     [],
  liveCaseStatuses: new Map(),

  setConnectionState: (s) => set({ connectionState: s }),
  setLastPing:        () => set({ lastPingAt: new Date().toISOString() }),

  upsertOCRProgress: (p) =>
    set((s) => {
      const next = new Map(s.ocrProgress)
      next.set(p.documentId, p)
      return { ocrProgress: next }
    }),

  clearOCRProgress: (documentId) =>
    set((s) => {
      const next = new Map(s.ocrProgress)
      next.delete(documentId)
      return { ocrProgress: next }
    }),

  startAIStream: (payload) =>
    set((s) => {
      const next = new Map(s.aiStreams)
      next.set(payload.caseId, {
        traceId:     payload.traceId,
        caseId:      payload.caseId,
        stage:       payload.stage ?? 'retrieval',
        stepLabel:   payload.stepLabel ?? 'Initializing…',
        tokens:      '',
        tokensUsed:  0,
        steps:       [],
        startedAt:   new Date().toISOString(),
        completedAt: null,
      })
      return { aiStreams: next }
    }),

  appendAIToken: (caseId, token) =>
    set((s) => {
      const stream = s.aiStreams.get(caseId)
      if (!stream) return s
      const next = new Map(s.aiStreams)
      next.set(caseId, { ...stream, tokens: stream.tokens + token })
      return { aiStreams: next }
    }),

  advanceAIStep: (payload) =>
    set((s) => {
      const stream = s.aiStreams.get(payload.caseId)
      if (!stream) return s
      const next = new Map(s.aiStreams)
      const updatedSteps = stream.steps.some((st) => st.label === payload.stepLabel)
        ? stream.steps
        : [...stream.steps, {
            label:       payload.stepLabel ?? '',
            stage:       payload.stage ?? stream.stage,
            completedAt: new Date().toISOString(),
          }]
      next.set(payload.caseId, {
        ...stream,
        stage:      payload.stage ?? stream.stage,
        stepLabel:  payload.stepLabel ?? stream.stepLabel,
        tokensUsed: payload.tokensUsed ?? stream.tokensUsed,
        steps:      updatedSteps,
      })
      return { aiStreams: next }
    }),

  completeAIStream: (caseId) =>
    set((s) => {
      const stream = s.aiStreams.get(caseId)
      if (!stream) return s
      const next = new Map(s.aiStreams)
      next.set(caseId, { ...stream, stage: 'complete', completedAt: new Date().toISOString() })
      return { aiStreams: next }
    }),

  resetAIStream: (caseId) =>
    set((s) => {
      const next = new Map(s.aiStreams)
      next.delete(caseId)
      return { aiStreams: next }
    }),

  setQueueSnapshot: (q) => set({ queueSnapshot: q }),

  addSystemAlert: (a) =>
    set((s) => ({
      systemAlerts: [
        {
          ...a,
          id:        crypto.randomUUID(),
          timestamp: new Date().toISOString(),
          dismissed: false,
        },
        ...s.systemAlerts.slice(0, 19),
      ],
    })),

  dismissAlert: (id) =>
    set((s) => ({
      systemAlerts: s.systemAlerts.map((a) => a.id === id ? { ...a, dismissed: true } : a),
    })),

  clearAlerts: () =>
    set((s) => ({ systemAlerts: s.systemAlerts.filter((a) => !a.dismissed) })),

  setLiveCaseStatus: (caseId, status) =>
    set((s) => {
      const next = new Map(s.liveCaseStatuses)
      next.set(caseId, status)
      return { liveCaseStatuses: next }
    }),
}))
