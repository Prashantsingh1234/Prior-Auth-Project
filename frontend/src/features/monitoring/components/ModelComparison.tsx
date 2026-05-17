import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  BarChart, Bar, RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, Tooltip, Cell, Legend,
} from 'recharts'
import { TrendingDown, Zap, DollarSign, AlertTriangle, Activity } from 'lucide-react'
import type { ModelMetrics } from '../hooks/useMonitoringData'

// ─── Comparison table row ─────────────────────────────────────────────────────

interface RowProps {
  label:    string
  values:   Array<{ model: string; color: string; v: number; fmt: string; goodDir: 'up' | 'down' }>
}

function CompareRow({ label, values }: RowProps) {
  const sorted  = [...values].sort((a, b) => a.v - b.v)
  const bestVal = values[0].goodDir === 'up' ? sorted[sorted.length - 1]!.v : sorted[0]!.v

  return (
    <tr className="border-b border-[var(--border)] hover:bg-[var(--elevated)]/40 transition-colors">
      <td className="px-3 py-2 text-[10px] text-[var(--text-3)] w-36 whitespace-nowrap">{label}</td>
      {values.map((v) => {
        const isBest = v.v === bestVal
        return (
          <td key={v.model} className="px-3 py-2 text-center">
            <span
              className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded"
              style={{
                color:      isBest ? v.color : 'var(--text-2)',
                background: isBest ? `${v.color}18` : 'transparent',
                border:     `1px solid ${isBest ? v.color + '40' : 'transparent'}`,
              }}
            >
              {v.fmt}
            </span>
          </td>
        )
      })}
    </tr>
  )
}

// ─── Radar overlay ────────────────────────────────────────────────────────────

function NormalizedRadar({ models, selected }: { models: ModelMetrics[]; selected: Set<string> }) {
  const data = [
    { axis: 'Grounding',    ...Object.fromEntries(models.map((m) => [m.model, m.groundingScore])) },
    { axis: 'Speed',        ...Object.fromEntries(models.map((m) => [m.model, Math.max(0, 100 - m.avgLatencyMs / 50)])) },
    { axis: 'Accuracy',     ...Object.fromEntries(models.map((m) => [m.model, 100 - m.errorRate * 5])) },
    { axis: 'Cost Eff.',    ...Object.fromEntries(models.map((m) => [m.model, Math.max(0, 100 - m.costPerK * 4)])) },
    { axis: 'Anti-Halluc.', ...Object.fromEntries(models.map((m) => [m.model, 100 - m.hallucinationRate * 8])) },
    { axis: 'Throughput',   ...Object.fromEntries(models.map((m) => [m.model, Math.min(100, m.throughput / 14)])) },
  ]

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data}>
          <PolarGrid stroke="var(--border)" />
          <PolarAngleAxis dataKey="axis" tick={{ fontSize: 9, fill: 'var(--text-4)' }} />
          {models.filter((m) => selected.has(m.model)).map((m) => (
            <Radar
              key={m.model}
              name={m.model}
              dataKey={m.model}
              stroke={m.color}
              fill={m.color}
              fillOpacity={0.12}
              strokeWidth={2}
            />
          ))}
          <Legend
            formatter={(v: string) => <span style={{ fontSize: 9 }}>{v.replace('claude-', '')}</span>}
          />
          <Tooltip
            contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', fontSize: 9 }}
            formatter={(v: number) => [v.toFixed(1)]}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}

// ─── Throughput bar chart ─────────────────────────────────────────────────────

function ThroughputBars({ models, selected }: { models: ModelMetrics[]; selected: Set<string> }) {
  const data = models
    .filter((m) => selected.has(m.model))
    .map((m) => ({ name: m.model.replace('claude-', '').replace('text-', ''), v: m.throughput, color: m.color }))

  return (
    <div className="h-32">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 2, right: 8, left: 8, bottom: 2 }}>
          <Bar dataKey="v" radius={[3, 3, 0, 0]} isAnimationActive={false}>
            {data.map((d, i) => <Cell key={i} fill={d.color} fillOpacity={0.8} />)}
          </Bar>
          <Tooltip
            formatter={(v: number) => [`${v} req/min`, 'Throughput']}
            contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', fontSize: 10 }}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// ─── Model header card ────────────────────────────────────────────────────────

function ModelCard({
  model, checked, onToggle,
}: { model: ModelMetrics; checked: boolean; onToggle: () => void }) {
  return (
    <div
      className="rounded-xl p-3 cursor-pointer transition-all"
      style={{
        background: checked ? `${model.color}12` : 'var(--elevated)',
        border:     `1px solid ${checked ? model.color + '50' : 'var(--border)'}`,
        opacity:    checked ? 1 : 0.5,
      }}
      onClick={onToggle}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="w-2 h-2 rounded-full" style={{ background: model.color }} />
        <span className="text-[8px] font-semibold text-[var(--text-4)]">{model.provider}</span>
      </div>
      <p className="text-[10px] font-bold text-[var(--text-1)] leading-tight truncate">
        {model.model.replace('claude-', '').replace('text-', '')}
      </p>
      <div className="flex items-center gap-3 mt-2 flex-wrap">
        <span className="flex items-center gap-0.5 text-[8px] text-[var(--text-4)]">
          <Activity className="w-2 h-2" />
          {model.throughput}/min
        </span>
        <span className="flex items-center gap-0.5 text-[8px] text-[var(--text-4)]">
          <DollarSign className="w-2 h-2" />
          ${model.costPerK}/k
        </span>
        <span className="flex items-center gap-0.5 text-[8px] text-[var(--text-4)]">
          <Zap className="w-2 h-2" />
          {model.avgLatencyMs}ms
        </span>
      </div>
    </div>
  )
}

// ─── Main ─────────────────────────────────────────────────────────────────────

interface ModelComparisonProps {
  models: ModelMetrics[]
}

export function ModelComparison({ models }: ModelComparisonProps) {
  const [selected, setSelected] = useState<Set<string>>(
    new Set(models.map((m) => m.model)),
  )

  function toggle(model: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(model)) {
        if (next.size > 1) next.delete(model)
      } else {
        next.add(model)
      }
      return next
    })
  }

  const active = models.filter((m) => selected.has(m.model))

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {/* Model toggles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        {models.map((m) => (
          <ModelCard key={m.model} model={m} checked={selected.has(m.model)} onToggle={() => toggle(m.model)} />
        ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-xl p-4" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
          <p className="text-[10px] font-bold text-[var(--text-2)] uppercase tracking-wide mb-2">Performance Radar</p>
          <NormalizedRadar models={models} selected={selected} />
        </div>
        <div className="rounded-xl p-4" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
          <p className="text-[10px] font-bold text-[var(--text-2)] uppercase tracking-wide mb-2">Throughput (req/min)</p>
          <ThroughputBars models={models} selected={selected} />
          <div className="mt-3 space-y-1">
            {active.map((m) => (
              <div key={m.model} className="flex items-center justify-between text-[9px]">
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full inline-block" style={{ background: m.color }} />
                  <span className="text-[var(--text-3)]">{m.model.replace('claude-', '').replace('text-', '')}</span>
                </span>
                <span className="font-mono text-[var(--text-2)]">
                  {m.avgLatencyMs}ms avg · P95 {m.p95LatencyMs}ms
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Comparison table */}
      <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--border)' }}>
        <div className="px-4 py-2" style={{ background: 'var(--elevated)' }}>
          <p className="text-[10px] font-bold text-[var(--text-2)] uppercase tracking-wide">Head-to-Head Comparison</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr style={{ background: 'var(--surface)' }}>
                <th className="px-3 py-2 text-left text-[9px] font-semibold text-[var(--text-4)] uppercase tracking-wide w-36">Metric</th>
                {active.map((m) => (
                  <th key={m.model} className="px-3 py-2 text-center">
                    <span className="text-[9px] font-bold" style={{ color: m.color }}>
                      {m.model.replace('claude-', '').replace('text-', '')}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody style={{ background: 'var(--elevated)' }}>
              <CompareRow label="Avg Latency" values={active.map((m) => ({ model: m.model, color: m.color, v: m.avgLatencyMs, fmt: `${m.avgLatencyMs}ms`, goodDir: 'down' }))} />
              <CompareRow label="P95 Latency" values={active.map((m) => ({ model: m.model, color: m.color, v: m.p95LatencyMs, fmt: `${m.p95LatencyMs}ms`, goodDir: 'down' }))} />
              <CompareRow label="Grounding Score" values={active.map((m) => ({ model: m.model, color: m.color, v: m.groundingScore, fmt: `${m.groundingScore}%`, goodDir: 'up' }))} />
              <CompareRow label="Hallucination Rate" values={active.map((m) => ({ model: m.model, color: m.color, v: m.hallucinationRate, fmt: `${m.hallucinationRate}%`, goodDir: 'down' }))} />
              <CompareRow label="Error Rate" values={active.map((m) => ({ model: m.model, color: m.color, v: m.errorRate, fmt: `${m.errorRate}%`, goodDir: 'down' }))} />
              <CompareRow label="Fallback Rate" values={active.map((m) => ({ model: m.model, color: m.color, v: m.fallbackRate, fmt: `${m.fallbackRate}%`, goodDir: 'down' }))} />
              <CompareRow label="Cost / 1k tokens" values={active.map((m) => ({ model: m.model, color: m.color, v: m.costPerK, fmt: `$${m.costPerK.toFixed(2)}`, goodDir: 'down' }))} />
              <CompareRow label="Throughput" values={active.map((m) => ({ model: m.model, color: m.color, v: m.throughput, fmt: `${m.throughput}/min`, goodDir: 'up' }))} />
            </tbody>
          </table>
        </div>
      </div>

      {/* Alerts */}
      {active.some((m) => m.hallucinationRate > 3) && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-[10px]"
          style={{ background: '#ef444412', border: '1px solid #ef444440', color: '#ef4444' }}
        >
          <AlertTriangle className="w-3 h-3 shrink-0" />
          {active.filter((m) => m.hallucinationRate > 3).map((m) => m.model.replace('claude-', '')).join(', ')} exceeded hallucination threshold of 3%.
          Consider routing complex cases to Opus.
        </motion.div>
      )}
      {active.some((m) => m.avgLatencyMs > 2000) && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-[10px]"
          style={{ background: '#f59e0b12', border: '1px solid #f59e0b40', color: '#f59e0b' }}
        >
          <TrendingDown className="w-3 h-3 shrink-0" />
          {active.filter((m) => m.avgLatencyMs > 2000).map((m) => m.model.replace('claude-', '')).join(', ')} showing elevated latency (&gt;2s). Monitor for SLA impact.
        </motion.div>
      )}
    </div>
  )
}
