import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Radio, Brain, FileText, Inbox, ShieldAlert, Zap,
  Play, Square, RefreshCw, ChevronRight,
} from 'lucide-react'
import { useRealtimeStore, type AIStreamState } from '@/store/realtimeStore'
import type { OCRProgressPayload } from '@/services/realtime.service'
import { useSSEStream } from '@/hooks/useSSEStream'
import {
  AIThinkingAnimation,
  OCRProgressPanel,
  ConnectionStatusChip,
  ReconnectBanner,
  LiveQueueIndicator,
  SystemAlertBanner,
} from '@/components/realtime'

// ─── Mock event simulator ─────────────────────────────────────────────────────

const MOCK_DOCS  = [
  { documentId: 'doc-001', filename: 'clinical_notes_2024.pdf',   totalPages: 12 },
  { documentId: 'doc-002', filename: 'radiology_report_knee.pdf', totalPages: 4  },
  { documentId: 'doc-003', filename: 'insurance_form_AH22.pdf',   totalPages: 2  },
]

// ─── Tab config ───────────────────────────────────────────────────────────────

type DemoTab = 'overview' | 'ai_stream' | 'ocr' | 'queue' | 'alerts'

const TABS: Array<{ id: DemoTab; label: string; icon: React.ElementType }> = [
  { id: 'overview',  label: 'Live Overview',     icon: Radio       },
  { id: 'ai_stream', label: 'AI Reasoning',       icon: Brain       },
  { id: 'ocr',       label: 'OCR Processing',     icon: FileText    },
  { id: 'queue',     label: 'Queue Monitor',      icon: Inbox       },
  { id: 'alerts',    label: 'System Alerts',      icon: ShieldAlert },
]

// ─── AI Reasoning demo ────────────────────────────────────────────────────────

function AIReasoningDemo() {
  const { startAIStream, appendAIToken, advanceAIStep, completeAIStream, resetAIStream, aiStreams } = useRealtimeStore()
  const sseStream = useSSEStream()
  const [activeCaseId] = useState('PA-2024-001')

  const streamState: AIStreamState = aiStreams.get(activeCaseId) ?? {
    traceId: '', caseId: activeCaseId, stage: 'idle', stepLabel: '',
    tokens: '', tokensUsed: 0, steps: [], startedAt: null, completedAt: null,
  }

  function handleStart() {
    resetAIStream(activeCaseId)
    startAIStream({ caseId: activeCaseId, traceId: crypto.randomUUID(), stage: 'retrieval', stepLabel: 'Loading policy criteria' })
    sseStream.start('/ai/reason')
  }

  function handleReset() {
    sseStream.reset()
    resetAIStream(activeCaseId)
  }

  // Sync SSE steps → store
  useEffect(() => {
    if (!sseStream.currentStep) return
    advanceAIStep({
      caseId:    activeCaseId,
      traceId:   '',
      stage:     sseStream.currentStep.stage as 'retrieval' | 'reasoning' | 'decision' | 'complete',
      stepLabel: sseStream.currentStep.label,
    })
  }, [sseStream.currentStep]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (sseStream.tokens) {
      const last = streamState.tokens
      const delta = sseStream.tokens.slice(last.length)
      if (delta) appendAIToken(activeCaseId, delta)
    }
  }, [sseStream.tokens]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (sseStream.status === 'complete') completeAIStream(activeCaseId)
  }, [sseStream.status]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-1)]">AI Reasoning Stream</h3>
          <p className="text-[10px] text-[var(--text-4)]">Live token-by-token output with step tracing</p>
        </div>
        <div className="flex items-center gap-2">
          {sseStream.status === 'streaming' ? (
            <button
              onClick={handleReset}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium"
              style={{ background: '#ef444415', color: '#ef4444', border: '1px solid #ef444430' }}
            >
              <Square className="w-3 h-3" />
              Stop
            </button>
          ) : (
            <button
              onClick={handleStart}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium"
              style={{ background: '#8b5cf615', color: '#8b5cf6', border: '1px solid #8b5cf630' }}
            >
              <Play className="w-3 h-3" />
              {sseStream.status === 'complete' ? 'Run Again' : 'Run AI Reasoning'}
            </button>
          )}
        </div>
      </div>

      <AIThinkingAnimation stream={streamState} />

      {sseStream.status === 'complete' && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                    className="rounded-xl p-3 space-y-1"
                    style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
          <p className="text-[9px] text-[var(--text-4)] uppercase tracking-wide">Stream stats</p>
          <div className="flex items-center gap-4">
            <span className="text-[10px] text-[var(--text-3)]">
              Tokens: <span className="font-mono text-violet-400">{sseStream.totalTokens}</span>
            </span>
            <span className="text-[10px] text-[var(--text-3)]">
              Latency: <span className="font-mono text-emerald-400">{sseStream.latencyMs}ms</span>
            </span>
            <span className="text-[10px] text-[var(--text-3)]">
              Steps: <span className="font-mono text-sky-400">{sseStream.steps.length}</span>
            </span>
          </div>
        </motion.div>
      )}
    </div>
  )
}

// ─── OCR demo ────────────────────────────────────────────────────────────────

function OCRDemo() {
  const { upsertOCRProgress, ocrProgress } = useRealtimeStore()
  const [running, setRunning] = useState(false)
  const timerRef = { current: null as ReturnType<typeof setInterval> | null }

  const docs: OCRProgressPayload[] = MOCK_DOCS.map((d) => {
    const saved = ocrProgress.get(d.documentId)
    return saved ?? { ...d, caseId: 'PA-2024-001', progress: 0, stage: 'queued', pagesDone: 0 }
  })

  const runSimulation = useCallback(() => {
    setRunning(true)
    // Initialize all to queued
    MOCK_DOCS.forEach((d) => upsertOCRProgress({ ...d, caseId: 'PA-2024-001', progress: 0, stage: 'uploading', pagesDone: 0 }))

    let tick = 0
    const stages: OCRProgressPayload['stage'][] = ['uploading', 'queued', 'extracting', 'validating', 'complete']

    timerRef.current = setInterval(() => {
      tick++
      MOCK_DOCS.forEach((d, i) => {
        const offset  = i * 8
        const myTick  = tick - offset
        if (myTick < 0) return

        const stageIdx = Math.min(Math.floor(myTick / 5), stages.length - 1)
        const stage    = stages[stageIdx]
        const progress = Math.min(100, (myTick / (stages.length * 5)) * 100)
        const pagesDone = stage === 'complete' ? d.totalPages : Math.floor((progress / 100) * d.totalPages)

        upsertOCRProgress({
          ...d, caseId: 'PA-2024-001', progress: Math.round(progress),
          stage, pagesDone,
          confidence: stage === 'complete' ? 0.92 + Math.random() * 0.07 : undefined,
        })
      })

      const allDone = MOCK_DOCS.every((d) => ocrProgress.get(d.documentId)?.stage === 'complete')
      if (tick > 60 || allDone) {
        if (timerRef.current) clearInterval(timerRef.current)
        setRunning(false)
      }
    }, 300)
  }, [upsertOCRProgress, ocrProgress])

  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current) }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-1)]">OCR Processing</h3>
          <p className="text-[10px] text-[var(--text-4)]">Real-time document extraction progress</p>
        </div>
        <button
          onClick={runSimulation}
          disabled={running}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-50"
          style={{ background: '#0ea5e915', color: '#0ea5e9', border: '1px solid #0ea5e930' }}
        >
          {running ? <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}><RefreshCw className="w-3 h-3" /></motion.div> : <Play className="w-3 h-3" />}
          {running ? 'Processing…' : 'Simulate OCR'}
        </button>
      </div>

      <OCRProgressPanel documents={docs} />
    </div>
  )
}

// ─── Alerts demo ──────────────────────────────────────────────────────────────

function AlertsDemo() {
  const { addSystemAlert, systemAlerts, dismissAlert, clearAlerts } = useRealtimeStore()

  function inject(level: 'info' | 'warning' | 'critical') {
    const msgs = {
      info:     { service: 'OCR Service',    message: 'Document queue processed successfully.', code: 'OCR_OK'      },
      warning:  { service: 'AI Gateway',     message: 'Token rate limit approaching threshold.', code: 'RATE_WARN'  },
      critical: { service: 'LangGraph',      message: 'Reasoning pipeline latency exceeded 10s SLA.', code: 'SLA_BREACH' },
    }
    addSystemAlert({ ...msgs[level], level })
  }

  const visible = systemAlerts.filter((a) => !a.dismissed)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-1)]">System Alerts</h3>
          <p className="text-[10px] text-[var(--text-4)]">Real-time service health notifications</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => inject('info')}
                  className="px-2.5 py-1.5 rounded-lg text-[10px] font-medium"
                  style={{ background: '#0ea5e915', color: '#0ea5e9', border: '1px solid #0ea5e930' }}>
            + Info
          </button>
          <button onClick={() => inject('warning')}
                  className="px-2.5 py-1.5 rounded-lg text-[10px] font-medium"
                  style={{ background: '#f59e0b15', color: '#f59e0b', border: '1px solid #f59e0b30' }}>
            + Warning
          </button>
          <button onClick={() => inject('critical')}
                  className="px-2.5 py-1.5 rounded-lg text-[10px] font-medium"
                  style={{ background: '#ef444415', color: '#ef4444', border: '1px solid #ef444430' }}>
            + Critical
          </button>
          {visible.length > 0 && (
            <button onClick={clearAlerts}
                    className="px-2.5 py-1.5 rounded-lg text-[10px] font-medium text-[var(--text-4)] hover:text-[var(--text-2)]">
              Clear
            </button>
          )}
        </div>
      </div>

      {visible.length === 0 && (
        <div className="flex flex-col items-center justify-center py-10 text-center">
          <Zap className="w-8 h-8 text-[var(--text-4)] mb-2" />
          <p className="text-xs text-[var(--text-4)]">No active alerts. Use the buttons above to inject mock alerts.</p>
        </div>
      )}

      <div className="space-y-2">
        <AnimatePresence>
          {visible.map((alert) => (
            <motion.div
              key={alert.id}
              initial={{ x: -12, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 12, opacity: 0 }}
              className="flex items-start gap-3 px-4 py-3 rounded-xl"
              style={{
                background: alert.level === 'critical' ? '#ef444415' : alert.level === 'warning' ? '#f59e0b15' : '#0ea5e915',
                border: `1px solid ${alert.level === 'critical' ? '#ef444430' : alert.level === 'warning' ? '#f59e0b30' : '#0ea5e930'}`,
              }}
            >
              <ShieldAlert className="w-4 h-4 mt-0.5 flex-shrink-0"
                           style={{ color: alert.level === 'critical' ? '#ef4444' : alert.level === 'warning' ? '#f59e0b' : '#0ea5e9' }} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[10px] font-bold uppercase tracking-wide"
                        style={{ color: alert.level === 'critical' ? '#ef4444' : alert.level === 'warning' ? '#f59e0b' : '#0ea5e9' }}>
                    {alert.level}
                  </span>
                  <span className="text-[10px] text-[var(--text-3)] font-medium">{alert.service}</span>
                  {alert.code && (
                    <span className="text-[8px] px-1.5 py-0.5 rounded font-mono bg-white/10 text-[var(--text-4)]">
                      {alert.code}
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-[var(--text-2)]">{alert.message}</p>
              </div>
              <button onClick={() => dismissAlert(alert.id)}
                      className="text-[var(--text-4)] hover:text-[var(--text-2)] p-1 rounded transition-colors">
                <ChevronRight className="w-3 h-3" />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}

// ─── Live overview ────────────────────────────────────────────────────────────

function LiveOverview() {
  const { ocrProgress, aiStreams, queueSnapshot } = useRealtimeStore()

  const activeOCR   = Array.from(ocrProgress.values()).filter((d) => d.stage !== 'complete')
  const activeAI    = Array.from(aiStreams.values()).filter((s) => s.stage !== 'idle' && s.stage !== 'complete')
  const q           = queueSnapshot ?? { pending: 14, processing: 3, completed: 87, avgWaitMin: 4.2, slaAtRisk: 2 }

  return (
    <div className="grid grid-cols-2 gap-4">
      {/* Connection */}
      <div className="col-span-2 flex items-center gap-3 px-4 py-3 rounded-xl"
           style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
        <Radio className="w-4 h-4 text-[var(--text-3)]" />
        <div>
          <p className="text-[10px] font-semibold text-[var(--text-2)]">WebSocket Connection</p>
          <p className="text-[9px] text-[var(--text-4)]">Real-time event pipeline</p>
        </div>
        <div className="ml-auto">
          <ConnectionStatusChip />
        </div>
      </div>

      {/* Queue */}
      <LiveQueueIndicator />

      {/* Active AI streams */}
      <div className="rounded-xl p-4" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
        <p className="text-[10px] font-semibold text-[var(--text-2)] mb-3 flex items-center gap-2">
          <Brain className="w-3.5 h-3.5 text-violet-400" />
          Active AI Streams
        </p>
        {activeAI.length === 0 ? (
          <p className="text-[10px] text-[var(--text-4)] text-center py-4">No active reasoning sessions</p>
        ) : (
          activeAI.map((s) => (
            <AIThinkingAnimation key={s.caseId} stream={s} compact />
          ))
        )}
      </div>

      {/* OCR active */}
      <div className="col-span-2">
        {activeOCR.length > 0 ? (
          <OCRProgressPanel documents={activeOCR} title="Active OCR Jobs" />
        ) : (
          <div className="rounded-xl p-4 flex items-center gap-3"
               style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
            <FileText className="w-4 h-4 text-[var(--text-4)]" />
            <p className="text-[10px] text-[var(--text-4)]">No documents currently processing</p>
          </div>
        )}
      </div>

      {/* Summary */}
      <div className="col-span-2 grid grid-cols-4 gap-3">
        {[
          { label: 'Pending Cases',     value: q.pending,    color: '#0ea5e9' },
          { label: 'AI Processing',     value: q.processing, color: '#8b5cf6' },
          { label: 'SLA At Risk',       value: q.slaAtRisk,  color: '#ef4444' },
          { label: 'Completed Today',   value: q.completed,  color: '#10b981' },
        ].map((stat) => (
          <div key={stat.label} className="rounded-xl p-3 text-center"
               style={{ background: `${stat.color}08`, border: `1px solid ${stat.color}25` }}>
            <p className="text-2xl font-bold tabular-nums" style={{ color: stat.color }}>{stat.value}</p>
            <p className="text-[9px] text-[var(--text-4)] mt-0.5">{stat.label}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function RealtimePage() {
  const [tab, setTab] = useState<DemoTab>('overview')

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ background: 'var(--bg)' }}>
      <ReconnectBanner />
      <SystemAlertBanner />

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b flex-shrink-0"
           style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
        <div>
          <h1 className="text-base font-bold text-[var(--text-1)] flex items-center gap-2">
            <Radio className="w-4 h-4 text-emerald-400" />
            Real-Time Architecture
          </h1>
          <p className="text-[10px] text-[var(--text-4)] mt-0.5">
            WebSocket events · SSE streaming · Optimistic updates · Live queue
          </p>
        </div>
        <ConnectionStatusChip />
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 px-6 pt-3 pb-0 flex-shrink-0"
           style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
        {TABS.map((t) => {
          const Icon = t.icon
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className="flex items-center gap-1.5 px-3 py-2 text-[11px] font-medium rounded-t-lg transition-all relative"
              style={{
                color:      tab === t.id ? 'var(--text-1)' : 'var(--text-3)',
                background: tab === t.id ? 'var(--bg)' : 'transparent',
                borderBottom: tab === t.id ? '2px solid #10b981' : '2px solid transparent',
              }}
            >
              <Icon className="w-3 h-3" />
              {t.label}
            </button>
          )
        })}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <AnimatePresence mode="wait">
          <motion.div
            key={tab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="max-w-3xl mx-auto"
          >
            {tab === 'overview'  && <LiveOverview />}
            {tab === 'ai_stream' && <AIReasoningDemo />}
            {tab === 'ocr'       && <OCRDemo />}
            {tab === 'queue'     && <LiveQueueIndicator />}
            {tab === 'alerts'    && <AlertsDemo />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}
