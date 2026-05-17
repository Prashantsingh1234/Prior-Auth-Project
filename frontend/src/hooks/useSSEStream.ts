import { useState, useCallback, useRef, useEffect } from 'react'
import { openMockSSEStream, type SSEPayload, type SSEStreamHandle } from '@/services/sse.service'

// ─── State ────────────────────────────────────────────────────────────────────

export type SSEStreamStatus = 'idle' | 'streaming' | 'complete' | 'error'

export interface StreamStep {
  label:  string
  stage:  string
  index:  number
}

export interface UseSSEStreamResult {
  status:      SSEStreamStatus
  tokens:      string
  steps:       StreamStep[]
  currentStep: StreamStep | null
  error:       string | null
  streamId:    string | null
  totalTokens: number
  latencyMs:   number
  start:       (endpoint: string) => void
  reset:       () => void
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useSSEStream(): UseSSEStreamResult {
  const [status,      setStatus]      = useState<SSEStreamStatus>('idle')
  const [tokens,      setTokens]      = useState('')
  const [steps,       setSteps]       = useState<StreamStep[]>([])
  const [currentStep, setCurrentStep] = useState<StreamStep | null>(null)
  const [error,       setError]       = useState<string | null>(null)
  const [streamId,    setStreamId]    = useState<string | null>(null)
  const [totalTokens, setTotalTokens] = useState(0)
  const [latencyMs,   setLatencyMs]   = useState(0)

  const handleRef = useRef<SSEStreamHandle | null>(null)

  const handleEvent = useCallback((event: SSEPayload) => {
    switch (event.type) {
      case 'token':
        setTokens((t) => t + event.token)
        break
      case 'step': {
        const step: StreamStep = { label: event.label, stage: event.stage, index: event.index }
        setSteps((prev) => {
          const exists = prev.some((s) => s.index === step.index)
          return exists ? prev : [...prev, step]
        })
        setCurrentStep(step)
        break
      }
      case 'complete':
        setTotalTokens(event.totalTokens)
        setLatencyMs(event.latencyMs)
        setStreamId(event.traceId)
        setCurrentStep(null)
        setStatus('complete')
        break
      case 'error':
        setError(event.message)
        setStatus('error')
        break
    }
  }, [])

  const start = useCallback((endpoint: string) => {
    handleRef.current?.close()
    setStatus('streaming')
    setTokens('')
    setSteps([])
    setCurrentStep(null)
    setError(null)
    setTotalTokens(0)
    setLatencyMs(0)

    const handle = openMockSSEStream(endpoint, handleEvent)
    handleRef.current = handle
    setStreamId(handle.streamId)
  }, [handleEvent])

  const reset = useCallback(() => {
    handleRef.current?.close()
    handleRef.current = null
    setStatus('idle')
    setTokens('')
    setSteps([])
    setCurrentStep(null)
    setError(null)
    setStreamId(null)
    setTotalTokens(0)
    setLatencyMs(0)
  }, [])

  useEffect(() => () => { handleRef.current?.close() }, [])

  return { status, tokens, steps, currentStep, error, streamId, totalTokens, latencyMs, start, reset }
}
