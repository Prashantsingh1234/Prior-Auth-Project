import { APP_CONFIG } from '@/config/app.config'

// ─── Event type registry ──────────────────────────────────────────────────────

export type RTEventType =
  | 'case:created'
  | 'case:updated'
  | 'case:status_changed'
  | 'case:assigned'
  | 'case:decision'
  | 'ocr:progress'
  | 'ocr:complete'
  | 'ocr:failed'
  | 'ai:thinking_start'
  | 'ai:thinking_token'
  | 'ai:thinking_complete'
  | 'ai:decision_ready'
  | 'ai:override_required'
  | 'clarification:requested'
  | 'clarification:answered'
  | 'queue:updated'
  | 'sla:warning'
  | 'sla:breached'
  | 'system:alert'
  | 'system:health'
  | 'reviewer:action'
  | 'connection:ping'

export interface RTEvent<T = unknown> {
  type:      RTEventType
  payload:   T
  timestamp: string
  id:        string
}

// ─── Typed payloads ───────────────────────────────────────────────────────────

export interface CaseStatusPayload {
  caseId:    string
  caseRef:   string
  status:    string
  changedBy: string
}

export interface OCRProgressPayload {
  caseId:      string
  documentId:  string
  filename:    string
  progress:    number   // 0–100
  stage:       'uploading' | 'queued' | 'extracting' | 'validating' | 'complete' | 'failed'
  pagesDone:   number
  totalPages:  number
  confidence?: number
  error?:      string
}

export interface AIThinkingPayload {
  caseId:     string
  traceId:    string
  token?:     string
  stepLabel?: string
  stage?:     'retrieval' | 'reasoning' | 'decision' | 'complete'
  tokensUsed?: number
}

export interface QueuePayload {
  pending:    number
  processing: number
  completed:  number
  avgWaitMin: number
  slaAtRisk:  number
}

export interface SystemAlertPayload {
  level:   'info' | 'warning' | 'critical'
  service: string
  message: string
  code?:   string
}

// ─── Connection state ─────────────────────────────────────────────────────────

export type WSConnectionState = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'closed' | 'error'

type Listener<T = unknown> = (event: RTEvent<T>) => void

// ─── WebSocket singleton ──────────────────────────────────────────────────────

const WS_BASE = (() => {
  const apiBase = APP_CONFIG.api.baseUrl.replace(/^http/, 'ws')
  return apiBase.replace('/api/v1', '')
})()

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000]
const PING_INTERVAL_MS = 25_000

class RealtimeService {
  private ws:           WebSocket | null = null
  private state:        WSConnectionState = 'idle'
  private listeners:    Map<RTEventType, Set<Listener<any>>> = new Map()
  private globalListeners: Set<Listener<any>> = new Set()
  private reconnectIdx  = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private pingTimer:      ReturnType<typeof setInterval> | null = null
  private stateListeners: Set<(s: WSConnectionState) => void> = new Set()
  private manualClose   = false

  connect() {
    if (this.state === 'connected' || this.state === 'connecting') return
    this.manualClose = false
    this._doConnect()
  }

  disconnect() {
    this.manualClose = true
    this._cleanup()
    this._setState('closed')
  }

  getState() { return this.state }

  onStateChange(cb: (s: WSConnectionState) => void) {
    this.stateListeners.add(cb)
    return () => this.stateListeners.delete(cb)
  }

  on<T = unknown>(type: RTEventType, cb: Listener<T>) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set())
    this.listeners.get(type)!.add(cb as Listener)
    return () => this.listeners.get(type)?.delete(cb as Listener)
  }

  onAny(cb: Listener<unknown>) {
    this.globalListeners.add(cb)
    return () => this.globalListeners.delete(cb)
  }

  // ── Private ─────────────────────────────────────────────────────────────────

  private _doConnect() {
    this._setState('connecting')

    const token = this._readToken()
    const url   = `${WS_BASE}/ws/realtime${token ? `?token=${encodeURIComponent(token)}` : ''}`

    try {
      this.ws = new WebSocket(url)
    } catch {
      this._scheduleReconnect()
      return
    }

    this.ws.onopen = () => {
      this._setState('connected')
      this.reconnectIdx = 0
      this._startPing()
    }

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string) as RTEvent
        if (msg.type === 'connection:ping') return
        this._dispatch(msg)
      } catch {
        // malformed frame — ignore
      }
    }

    this.ws.onerror = () => {
      // onerror always precedes onclose — let onclose handle reconnect
    }

    this.ws.onclose = () => {
      this._cleanup()
      if (!this.manualClose) {
        this._setState('reconnecting')
        this._scheduleReconnect()
      }
    }
  }

  private _dispatch(event: RTEvent) {
    this.globalListeners.forEach((cb) => cb(event))
    this.listeners.get(event.type)?.forEach((cb) => cb(event))
  }

  private _scheduleReconnect() {
    const delay = RECONNECT_DELAYS[Math.min(this.reconnectIdx, RECONNECT_DELAYS.length - 1)]
    this.reconnectIdx++
    this.reconnectTimer = setTimeout(() => this._doConnect(), delay)
  }

  private _startPing() {
    this._stopPing()
    this.pingTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'connection:ping' }))
      }
    }, PING_INTERVAL_MS)
  }

  private _stopPing() {
    if (this.pingTimer) { clearInterval(this.pingTimer); this.pingTimer = null }
  }

  private _cleanup() {
    this._stopPing()
    if (this.reconnectTimer) { clearTimeout(this.reconnectTimer); this.reconnectTimer = null }
    if (this.ws) {
      this.ws.onopen = this.ws.onmessage = this.ws.onerror = this.ws.onclose = null
      if (this.ws.readyState < WebSocket.CLOSING) this.ws.close()
      this.ws = null
    }
  }

  private _setState(s: WSConnectionState) {
    this.state = s
    this.stateListeners.forEach((cb) => cb(s))
  }

  private _readToken(): string | null {
    try {
      const raw = localStorage.getItem('pa-auth')
      if (!raw) return null
      return JSON.parse(raw)?.state?.tokens?.accessToken ?? null
    } catch { return null }
  }
}

export const realtimeService = new RealtimeService()
