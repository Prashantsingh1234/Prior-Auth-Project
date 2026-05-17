import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Activity, Bot, BarChart3, Shield, Radio,
  AlertTriangle, CheckCircle2, Layers,
} from 'lucide-react'
import { useMonitoringData } from './hooks/useMonitoringData'
import { LiveMetricsBar }   from './components/LiveMetricsBar'
import { MetricCharts }     from './components/MetricCharts'
import { AITraceExplorer }  from './components/AITraceExplorer'
import { ModelComparison }  from './components/ModelComparison'
import { EvaluatorAnalytics } from './components/EvaluatorAnalytics'
import { useHealthCheck }   from './hooks/useHealthCheck'

// ─── Tabs ─────────────────────────────────────────────────────────────────────

type Tab = 'overview' | 'traces' | 'models' | 'evaluators'

const TABS: Array<{ id: Tab; label: string; icon: React.ElementType }> = [
  { id: 'overview',   label: 'Live Overview',   icon: Activity },
  { id: 'traces',     label: 'AI Trace Explorer', icon: Bot },
  { id: 'models',     label: 'Model Comparison', icon: Layers },
  { id: 'evaluators', label: 'Evaluator Analytics', icon: BarChart3 },
]

// ─── Health dot ───────────────────────────────────────────────────────────────

function HealthDot() {
  const { data, isLoading } = useHealthCheck()
  const status = isLoading ? 'checking' : (data?.status ?? 'healthy')

  const cfg = {
    healthy:  { color: '#10b981', label: 'All systems operational' },
    degraded: { color: '#f59e0b', label: 'Partial degradation' },
    down:     { color: '#ef4444', label: 'System outage' },
    checking: { color: '#6b7280', label: 'Checking…' },
  }[status] ?? { color: '#10b981', label: 'All systems operational' }

  return (
    <div className="flex items-center gap-1.5">
      <motion.div
        className="w-2 h-2 rounded-full"
        animate={{ opacity: [1, 0.4, 1], scale: [1, 1.15, 1] }}
        transition={{ duration: 2, repeat: Infinity }}
        style={{ background: cfg.color }}
      />
      <span className="text-[10px] font-semibold" style={{ color: cfg.color }}>{cfg.label}</span>
    </div>
  )
}

// ─── Alert banner ─────────────────────────────────────────────────────────────

function AlertBanner({ snapshot }: { snapshot: ReturnType<typeof useMonitoringData>['snapshot'] }) {
  const alerts: string[] = []
  if (snapshot.hallucinationRate > 5) alerts.push(`Hallucination rate elevated: ${snapshot.hallucinationRate.toFixed(1)}%`)
  if (snapshot.groundingScore < 82)   alerts.push(`Grounding score degraded: ${snapshot.groundingScore.toFixed(1)}%`)
  if (snapshot.modelLatency > 2200)   alerts.push(`Model latency critical: ${Math.round(snapshot.modelLatency)}ms`)
  if (snapshot.queueBacklog > 30)     alerts.push(`Queue backlog high: ${Math.round(snapshot.queueBacklog)} cases`)

  if (alerts.length === 0) return null

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      className="px-4 py-2 flex items-center gap-3 shrink-0"
      style={{ background: '#ef444412', borderBottom: '1px solid #ef444430' }}
    >
      <motion.div
        animate={{ opacity: [1, 0.4, 1] }}
        transition={{ duration: 1, repeat: Infinity }}
      >
        <AlertTriangle className="w-3.5 h-3.5 text-red-400 shrink-0" />
      </motion.div>
      <div className="flex items-center gap-3 flex-wrap">
        {alerts.map((a, i) => (
          <span key={i} className="text-[10px] font-semibold text-red-400">{a}</span>
        ))}
      </div>
    </motion.div>
  )
}

// ─── Header stat chip ─────────────────────────────────────────────────────────

function HeaderStat({
  icon: Icon, label, value, color,
}: { icon: React.ElementType; label: string; value: string; color: string }) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl"
         style={{ background: `${color}10`, border: `1px solid ${color}25` }}>
      <Icon style={{ color, width: 12, height: 12 }} />
      <div>
        <p className="text-[7px] uppercase tracking-widest font-bold text-[var(--text-4)] leading-none">{label}</p>
        <p className="text-xs font-bold tabular-nums font-mono" style={{ color }}>{value}</p>
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function MonitoringPage() {
  const { metrics, snapshot, traces, models, evaluators, selectedTrace, setTrace, streamTick } = useMonitoringData()
  const [activeTab, setActiveTab] = useState<Tab>('overview')

  const errorCount   = traces.filter((t) => t.status === 'error').length
  const warningCount = traces.filter((t) => t.status === 'warning').length
  const successCount = traces.filter((t) => t.status === 'success').length

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden">

      {/* ── Page header ──────────────────────────────────────────────────────── */}
      <div className="shrink-0 border-b border-[var(--border)]" style={{ background: 'var(--elevated)' }}>
        <div className="flex items-center justify-between px-5 py-3 gap-4">
          {/* Title */}
          <div className="flex items-center gap-3 min-w-0">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: '#10b98115', border: '1px solid #10b98130' }}
            >
              <Radio className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <p className="text-sm font-bold text-[var(--text-1)]">AI Monitoring — Mission Control</p>
              <p className="text-[10px] text-[var(--text-4)]">Real-time LLM observability · Hallucination detection · Trace analytics</p>
            </div>
          </div>

          {/* Stats + health */}
          <div className="flex items-center gap-2 shrink-0 flex-wrap">
            <HeaderStat icon={CheckCircle2}  label="Success"    value={successCount.toString()} color="#10b981" />
            <HeaderStat icon={AlertTriangle} label="Warnings"   value={warningCount.toString()} color="#f59e0b" />
            <HeaderStat icon={AlertTriangle} label="Errors"     value={errorCount.toString()}   color="#ef4444" />
            <HeaderStat icon={Activity}      label="Halluc."    value={`${snapshot.hallucinationRate.toFixed(1)}%`} color={snapshot.hallucinationRate > 5 ? '#ef4444' : '#6366f1'} />
            <HeaderStat icon={Shield}        label="Grounding"  value={`${snapshot.groundingScore.toFixed(1)}%`}  color="#8b5cf6" />
            <div className="ml-2">
              <HealthDot />
            </div>
          </div>
        </div>

        {/* Tab bar */}
        <div
          className="flex items-center gap-1 px-4 py-1.5 border-t border-[var(--border)]"
          style={{ background: 'rgba(0,0,0,0.08)' }}
        >
          {TABS.map((tab) => {
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-semibold transition-all"
                style={{
                  background: isActive ? 'var(--surface)' : 'transparent',
                  color:      isActive ? 'var(--text-1)' : 'var(--text-4)',
                  border:     `1px solid ${isActive ? 'var(--border)' : 'transparent'}`,
                }}
              >
                <tab.icon className="w-3 h-3" />
                {tab.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* ── Alert banner ─────────────────────────────────────────────────────── */}
      <AlertBanner snapshot={snapshot} />

      {/* ── Live metrics bar ──────────────────────────────────────────────────── */}
      <LiveMetricsBar snapshot={snapshot} streamTick={streamTick} />

      {/* ── Tab content ───────────────────────────────────────────────────────── */}
      <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
            className="flex-1 min-h-0 overflow-hidden flex flex-col"
          >
            {activeTab === 'overview' && (
              <MetricCharts metrics={metrics} />
            )}
            {activeTab === 'traces' && (
              <AITraceExplorer
                traces={traces}
                selectedTrace={selectedTrace}
                onSelect={setTrace}
              />
            )}
            {activeTab === 'models' && (
              <ModelComparison models={models} />
            )}
            {activeTab === 'evaluators' && (
              <EvaluatorAnalytics evaluators={evaluators} />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}
