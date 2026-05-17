import { motion, AnimatePresence } from 'framer-motion'
import { Activity, Zap, AlertTriangle } from 'lucide-react'
import type { MonitoringSnapshot } from '../hooks/useMonitoringData'

interface MetricChipProps {
  label:   string
  value:   string
  status:  'good' | 'warn' | 'crit'
  unit?:   string
  pulse?:  boolean
}

const STATUS_COLOR: Record<MetricChipProps['status'], string> = {
  good: '#10b981',
  warn: '#f59e0b',
  crit: '#ef4444',
}

function MetricChip({ label, value, status, unit, pulse }: MetricChipProps) {
  const color = STATUS_COLOR[status]
  return (
    <div
      className="flex flex-col px-3 py-1.5 rounded-lg relative overflow-hidden"
      style={{ background: `${color}10`, border: `1px solid ${color}25`, minWidth: 88 }}
    >
      {pulse && (
        <motion.div
          className="absolute inset-0 rounded-lg"
          animate={{ opacity: [0, 0.12, 0] }}
          transition={{ duration: 1.4, repeat: Infinity }}
          style={{ background: color }}
        />
      )}
      <span className="text-[8px] uppercase tracking-widest font-bold text-[var(--text-4)] leading-none relative z-10">
        {label}
      </span>
      <span className="text-xs font-bold tabular-nums font-mono mt-0.5 relative z-10" style={{ color }}>
        {value}<span className="text-[9px] font-normal ml-0.5 opacity-70">{unit}</span>
      </span>
    </div>
  )
}

interface LiveMetricsBarProps {
  snapshot:  MonitoringSnapshot
  streamTick: number
}

export function LiveMetricsBar({ snapshot, streamTick }: LiveMetricsBarProps) {
  const halStatus = snapshot.hallucinationRate > 6 ? 'crit' : snapshot.hallucinationRate > 3 ? 'warn' : 'good'
  const gndStatus = snapshot.groundingScore < 80 ? 'crit' : snapshot.groundingScore < 87 ? 'warn' : 'good'
  const retStatus = snapshot.retrievalQuality < 85 ? 'crit' : snapshot.retrievalQuality < 90 ? 'warn' : 'good'
  const ocrStatus = snapshot.ocrAccuracy < 90 ? 'crit' : snapshot.ocrAccuracy < 95 ? 'warn' : 'good'
  const latStatus = snapshot.modelLatency > 2000 ? 'crit' : snapshot.modelLatency > 1600 ? 'warn' : 'good'
  const fbkStatus = snapshot.fallbackFrequency > 8 ? 'crit' : snapshot.fallbackFrequency > 4 ? 'warn' : 'good'
  const bklStatus = snapshot.queueBacklog > 30 ? 'crit' : snapshot.queueBacklog > 20 ? 'warn' : 'good'
  const agrStatus = snapshot.reviewerAgreement < 80 ? 'crit' : snapshot.reviewerAgreement < 86 ? 'warn' : 'good'

  const hasCrit = [halStatus, gndStatus, retStatus, ocrStatus, latStatus, fbkStatus, bklStatus, agrStatus].includes('crit')
  const hasWarn = [halStatus, gndStatus, retStatus, ocrStatus, latStatus, fbkStatus, bklStatus, agrStatus].includes('warn')

  return (
    <div
      className="shrink-0 border-b border-[var(--border)] px-4 py-2 flex items-center gap-3 overflow-x-auto"
      style={{ background: 'var(--elevated)' }}
    >
      {/* Live indicator */}
      <div className="flex items-center gap-1.5 shrink-0">
        <motion.div
          className="w-1.5 h-1.5 rounded-full"
          animate={{ opacity: [1, 0.3, 1] }}
          transition={{ duration: 0.8, repeat: Infinity }}
          style={{ background: hasCrit ? '#ef4444' : hasWarn ? '#f59e0b' : '#10b981' }}
        />
        <span className="text-[9px] font-bold uppercase tracking-wider"
              style={{ color: hasCrit ? '#ef4444' : hasWarn ? '#f59e0b' : '#10b981' }}>
          LIVE
        </span>
        <span className="text-[9px] text-[var(--text-4)] tabular-nums">#{streamTick}</span>
      </div>

      <div className="w-px h-6 bg-[var(--border)] shrink-0" />

      {/* System icon */}
      <div className="flex items-center gap-1 shrink-0">
        {hasCrit ? (
          <AlertTriangle className="w-3 h-3 text-red-400" />
        ) : hasWarn ? (
          <AlertTriangle className="w-3 h-3 text-amber-400" />
        ) : (
          <Activity className="w-3 h-3 text-emerald-400" />
        )}
        <span className="text-[9px] text-[var(--text-4)] font-semibold">
          {hasCrit ? 'ALERT' : hasWarn ? 'DEGRADED' : 'NOMINAL'}
        </span>
      </div>

      <div className="w-px h-6 bg-[var(--border)] shrink-0" />

      {/* Metrics */}
      <AnimatePresence mode="wait">
        <motion.div
          key={Math.floor(streamTick / 5)}
          className="flex items-center gap-2 min-w-0"
          initial={{ opacity: 0.7 }}
          animate={{ opacity: 1 }}
        >
          <MetricChip label="Hallucination" value={snapshot.hallucinationRate.toFixed(1)} unit="%" status={halStatus} pulse={halStatus === 'crit'} />
          <MetricChip label="Grounding"     value={snapshot.groundingScore.toFixed(1)}    unit="%" status={gndStatus} />
          <MetricChip label="Retrieval"     value={snapshot.retrievalQuality.toFixed(1)}   unit="%" status={retStatus} />
          <MetricChip label="OCR Accuracy"  value={snapshot.ocrAccuracy.toFixed(1)}        unit="%" status={ocrStatus} />
          <MetricChip label="Latency"       value={Math.round(snapshot.modelLatency).toLocaleString()} unit="ms" status={latStatus} pulse={latStatus === 'crit'} />
          <MetricChip label="Tokens/req"    value={Math.round(snapshot.tokenUsage).toLocaleString()} status="good" />
          <MetricChip label="Fallback"      value={snapshot.fallbackFrequency.toFixed(1)}  unit="%" status={fbkStatus} pulse={fbkStatus === 'crit'} />
          <MetricChip label="Queue Backlog" value={Math.round(snapshot.queueBacklog).toString()} unit=" cases" status={bklStatus} pulse={bklStatus === 'crit'} />
          <MetricChip label="Reviewer Agr." value={snapshot.reviewerAgreement.toFixed(1)}  unit="%" status={agrStatus} />
          <MetricChip label="Clarif. Freq." value={snapshot.clarificationFreq.toFixed(1)}  unit="%" status="good" />
        </motion.div>
      </AnimatePresence>

      <div className="ml-auto shrink-0 flex items-center gap-1">
        <Zap className="w-3 h-3 text-[var(--text-4)]" />
        <span className="text-[9px] text-[var(--text-4)]">2s refresh</span>
      </div>
    </div>
  )
}
