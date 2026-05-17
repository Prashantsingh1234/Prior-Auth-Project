import { useEffect, useRef } from 'react'
import { realtimeService, type RTEventType } from '@/services/realtime.service'
import type {
  CaseStatusPayload,
  OCRProgressPayload,
  AIThinkingPayload,
  QueuePayload,
  SystemAlertPayload,
} from '@/services/realtime.service'
import { useRealtimeStore } from '@/store/realtimeStore'
import { useUIStore } from '@/store/uiStore'

// ─── Main connection hook ─────────────────────────────────────────────────────
// Mount once at the app root (AppShell). Wires all WS events to stores.

export function useWebSocketBridge() {
  const {
    setConnectionState,
    setLastPing,
    upsertOCRProgress,
    startAIStream,
    appendAIToken,
    advanceAIStep,
    completeAIStream,
    setQueueSnapshot,
    addSystemAlert,
    setLiveCaseStatus,
  } = useRealtimeStore()
  const { addNotification } = useUIStore()

  useEffect(() => {
    realtimeService.connect()

    const unsubs: Array<() => void> = []

    unsubs.push(realtimeService.onStateChange((s) => {
      setConnectionState(s)
      if (s === 'connected') setLastPing()
    }))

    unsubs.push(realtimeService.on<CaseStatusPayload>('case:status_changed', (e) => {
      setLiveCaseStatus(e.payload.caseId, e.payload.status)
      addNotification({
        type:    'info',
        title:   `Case ${e.payload.caseRef} updated`,
        message: `Status changed to ${e.payload.status}`,
        caseId:  e.payload.caseId,
        link:    `/review/${e.payload.caseId}`,
      })
    }))

    unsubs.push(realtimeService.on<CaseStatusPayload>('case:decision', (e) => {
      const status = e.payload.status
      addNotification({
        type:    status === 'APPROVED' ? 'success' : status === 'DENIED' ? 'error' : 'warning',
        title:   `Decision: ${e.payload.caseRef}`,
        message: `Case ${status.toLowerCase()} by ${e.payload.changedBy}`,
        caseId:  e.payload.caseId,
        link:    `/review/${e.payload.caseId}`,
      })
    }))

    unsubs.push(realtimeService.on<OCRProgressPayload>('ocr:progress', (e) => {
      upsertOCRProgress(e.payload)
    }))

    unsubs.push(realtimeService.on<OCRProgressPayload>('ocr:complete', (e) => {
      upsertOCRProgress({ ...e.payload, progress: 100, stage: 'complete' })
      addNotification({
        type:    'success',
        title:   'OCR complete',
        message: `${e.payload.filename} processed (${(e.payload.confidence ?? 0.95 * 100).toFixed(0)}% confidence)`,
        caseId:  e.payload.caseId,
      })
    }))

    unsubs.push(realtimeService.on<OCRProgressPayload>('ocr:failed', (e) => {
      upsertOCRProgress({ ...e.payload, stage: 'failed' })
      addNotification({
        type:    'error',
        title:   'OCR failed',
        message: e.payload.error ?? `Failed to process ${e.payload.filename}`,
        caseId:  e.payload.caseId,
      })
    }))

    unsubs.push(realtimeService.on<AIThinkingPayload>('ai:thinking_start', (e) => {
      startAIStream(e.payload)
    }))

    unsubs.push(realtimeService.on<AIThinkingPayload>('ai:thinking_token', (e) => {
      if (e.payload.token) appendAIToken(e.payload.caseId, e.payload.token)
    }))

    unsubs.push(realtimeService.on<AIThinkingPayload>('ai:thinking_complete', (e) => {
      completeAIStream(e.payload.caseId)
    }))

    unsubs.push(realtimeService.on<AIThinkingPayload>('ai:decision_ready', (e) => {
      advanceAIStep({ ...e.payload, stage: 'complete' })
      addNotification({
        type:    'info',
        title:   'AI decision ready',
        message: `Analysis complete for case ${e.payload.caseId}`,
        caseId:  e.payload.caseId,
        link:    `/review/${e.payload.caseId}`,
      })
    }))

    unsubs.push(realtimeService.on<QueuePayload>('queue:updated', (e) => {
      setQueueSnapshot(e.payload)
    }))

    unsubs.push(realtimeService.on<{ caseRef: string; caseId: string }>('sla:warning', (e) => {
      addNotification({
        type:    'warning',
        title:   `SLA warning: ${e.payload.caseRef}`,
        message: 'Case is approaching SLA deadline',
        caseId:  e.payload.caseId,
        link:    `/review/${e.payload.caseId}`,
      })
    }))

    unsubs.push(realtimeService.on<{ caseRef: string; caseId: string }>('sla:breached', (e) => {
      addNotification({
        type:    'error',
        title:   `SLA breached: ${e.payload.caseRef}`,
        message: 'Case has exceeded the SLA deadline',
        caseId:  e.payload.caseId,
        link:    `/review/${e.payload.caseId}`,
      })
    }))

    unsubs.push(realtimeService.on<SystemAlertPayload>('system:alert', (e) => {
      addSystemAlert(e.payload)
      if (e.payload.level === 'critical') {
        addNotification({
          type:    'error',
          title:   `System alert: ${e.payload.service}`,
          message: e.payload.message,
        })
      }
    }))

    return () => {
      unsubs.forEach((u) => u())
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
}

// ─── Per-event hook ───────────────────────────────────────────────────────────

export function useRTEvent<T>(type: RTEventType, handler: (payload: T) => void) {
  const handlerRef = useRef(handler)
  handlerRef.current = handler

  useEffect(() => {
    const unsub = realtimeService.on<T>(type, (e) => handlerRef.current(e.payload))
    return () => { unsub() }
  }, [type])
}
