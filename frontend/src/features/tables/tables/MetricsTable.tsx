import { useState } from 'react'
import { createColumnHelper } from '@tanstack/react-table'
import { TrendingUp, TrendingDown, Minus, AlertTriangle, Activity, Download } from 'lucide-react'
import { motion } from 'framer-motion'
import { DataTable } from '@/components/data-table'
import type { FilterDef, RowAction } from '@/components/data-table'
import { formatDate } from '@/lib/utils'
import { generateMetrics, type MetricRow } from '../data/mockData'

const col = createColumnHelper<MetricRow>()

const ENV_CFG: Record<string, { color: string; bg: string }> = {
  production:  { color: '#10b981', bg: '#10b98115' },
  staging:     { color: '#f59e0b', bg: '#f59e0b15' },
  development: { color: '#6b7280', bg: '#6b728015' },
}

function TrendBadge({ trend, delta }: { trend: string; delta: number }) {
  if (trend === 'up')   return <span className="flex items-center gap-0.5 text-[10px] text-emerald-400 font-semibold"><TrendingUp   className="w-3 h-3" />+{Math.abs(delta).toFixed(2)}</span>
  if (trend === 'down') return <span className="flex items-center gap-0.5 text-[10px] text-red-400    font-semibold"><TrendingDown className="w-3 h-3" />-{Math.abs(delta).toFixed(2)}</span>
  return <span className="flex items-center gap-0.5 text-[10px] text-[var(--text-4)]"><Minus className="w-3 h-3" />—</span>
}

function GaugeBar({ value, baseline, threshold }: { value: number; baseline: number; threshold: number }) {
  const isHigherBetter = threshold > baseline
  const good  = isHigherBetter ? value >= baseline : value <= baseline
  const color = good ? '#10b981' : value === threshold || (!isHigherBetter ? value > threshold : value < threshold) ? '#ef4444' : '#f59e0b'
  const pct   = Math.min(100, Math.max(0, (value / (threshold * 1.3)) * 100))
  return (
    <div className="flex items-center gap-1.5 w-full">
      <div className="flex-1 h-1.5 rounded-full overflow-hidden relative" style={{ background: 'var(--surface)' }}>
        <motion.div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }}
                    initial={{ width: 0 }} animate={{ width: `${pct}%` }} />
        <div className="absolute top-0 h-full w-0.5 bg-[var(--border)]"
             style={{ left: `${Math.min(99, (baseline / (threshold * 1.3)) * 100)}%` }} />
      </div>
      <span className="text-[10px] font-mono w-12 text-right font-semibold" style={{ color }}>
        {value.toFixed(value < 10 ? 2 : 0)}
      </span>
    </div>
  )
}

function MetricExpandedRow({ row }: { row: MetricRow }) {
  return (
    <div className="px-6 py-4 grid grid-cols-4 gap-4">
      {[
        { label: 'Value',      value: `${row.value.toFixed(2)} ${row.unit}`, color: row.breached ? '#ef4444' : '#10b981' },
        { label: 'Baseline',   value: `${row.baseline.toFixed(2)} ${row.unit}`, color: '#6b7280' },
        { label: 'P95',        value: `${row.p95.toFixed(2)} ${row.unit}`, color: '#f59e0b' },
        { label: 'Samples',    value: row.sampleCount.toLocaleString(), color: '#0ea5e9' },
        { label: 'Threshold',  value: `${row.alertThreshold.toFixed(2)} ${row.unit}`, color: row.breached ? '#ef4444' : '#6b7280' },
        { label: 'Delta',      value: `${row.delta >= 0 ? '+' : ''}${row.delta.toFixed(2)}`, color: row.delta > 0 ? '#10b981' : '#ef4444' },
        { label: 'Environment', value: row.environment, color: ENV_CFG[row.environment]?.color ?? '#6b7280' },
        { label: 'Date',       value: formatDate(row.date), color: 'var(--text-3)' },
      ].map((s) => (
        <div key={s.label} className="rounded-lg p-2.5 text-center"
             style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
          <p className="text-sm font-bold" style={{ color: s.color }}>{s.value}</p>
          <p className="text-[9px] text-[var(--text-4)] mt-0.5">{s.label}</p>
        </div>
      ))}
    </div>
  )
}

const COLUMNS = [
  col.accessor('date', {
    header: 'Date', size: 110,
    cell: (i) => <span className="text-[11px] text-[var(--text-3)]">{formatDate(i.getValue())}</span>,
    filterFn: 'daterange',
  }),
  col.accessor('model', {
    header: 'Model', size: 180,
    cell: (i) => <span className="font-mono text-[10px] text-violet-400">{i.getValue()}</span>,
    filterFn: 'multiselect',
  }),
  col.accessor('metric', {
    header: 'Metric', size: 180,
    cell: (i) => <span className="font-medium text-[11px]">{i.getValue()}</span>,
    filterFn: 'multiselect',
  }),
  col.accessor('value', {
    header: 'Value', size: 180,
    cell: (i) => {
      const row = i.row.original
      return <GaugeBar value={i.getValue()} baseline={row.baseline} threshold={row.alertThreshold} />
    },
    filterFn: 'numberrange',
  }),
  col.accessor('unit', {
    header: 'Unit', size: 60,
    cell: (i) => <span className="font-mono text-[10px] text-[var(--text-4)]">{i.getValue()}</span>,
  }),
  col.accessor('trend', {
    header: 'Trend', size: 90,
    cell: (i) => <TrendBadge trend={i.getValue()} delta={i.row.original.delta} />,
    filterFn: 'multiselect',
  }),
  col.accessor('category', { header: 'Category', size: 110, filterFn: 'multiselect' }),
  col.accessor('environment', {
    header: 'Environment', size: 120,
    cell: (i) => {
      const cfg = ENV_CFG[i.getValue()] ?? ENV_CFG['development']
      return (
        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold"
              style={{ background: cfg.bg, color: cfg.color }}>
          {i.getValue()}
        </span>
      )
    },
    filterFn: 'multiselect',
  }),
  col.accessor('sampleCount', {
    header: 'Samples', size: 90,
    cell: (i) => <span className="font-mono text-[11px]">{i.getValue().toLocaleString()}</span>,
  }),
  col.accessor('breached', {
    header: 'Alert', size: 80,
    cell: (i) => i.getValue()
      ? <span className="flex items-center gap-1 text-[10px] font-semibold text-red-400"><AlertTriangle className="w-3 h-3" />BREACH</span>
      : <span className="text-[10px] text-[var(--text-4)]">OK</span>,
    filterFn: 'boolean',
  }),
]

const MODELS = ['claude-sonnet-4-6','claude-haiku-4-5','gpt-4o','gpt-4o-mini','llama-3-70b']
const METRICS = ['Hallucination Rate','Grounding Score','Retrieval Precision','OCR Accuracy','Avg Latency','P95 Latency','Token Usage Avg','Clarification Freq','Override Rate','Agreement Rate','Fallback Rate','Cost per Case']
const CATS   = ['Accuracy','Performance','Cost','Quality','Safety']

const FILTER_DEFS: FilterDef[] = [
  { id: 'model',       label: 'Model',       type: 'multiselect', options: MODELS.map((v) => ({ value: v, label: v })) },
  { id: 'metric',      label: 'Metric',      type: 'multiselect', options: METRICS.map((v) => ({ value: v, label: v })) },
  { id: 'category',    label: 'Category',    type: 'multiselect', options: CATS.map((v) => ({ value: v, label: v })) },
  { id: 'environment', label: 'Environment', type: 'multiselect', options: Object.keys(ENV_CFG).map((v) => ({ value: v, label: v, color: ENV_CFG[v].color })) },
  { id: 'trend',       label: 'Trend',       type: 'multiselect', options: [{ value:'up',label:'Up',color:'#10b981' },{ value:'down',label:'Down',color:'#ef4444' },{ value:'stable',label:'Stable',color:'#6b7280' }] },
  { id: 'breached',    label: 'Alert',       type: 'boolean' },
  { id: 'date',        label: 'Date Range',  type: 'daterange' },
]

const ROW_ACTIONS: RowAction<MetricRow>[] = [
  { action: 'export', label: 'Export Row', icon: Download, color: '#6b7280' },
  { action: 'chart',  label: 'View Chart', icon: Activity, color: '#0ea5e9' },
]

export function MetricsTable() {
  const [data] = useState(() => generateMetrics(200))

  return (
    <DataTable
      tableId="metrics"
      data={data}
      columns={COLUMNS}
      filterDefs={FILTER_DEFS}
      defaultSorting={[{ id: 'date', desc: true }]}
      expandedRowRenderer={(row) => <MetricExpandedRow row={row} />}
      rowActions={ROW_ACTIONS}
      height={580}
      systemViews={[
        { name: 'Alerts Only',   isSystem: true, columnVisibility: {}, columnOrder: [], sorting: [{ id: 'value', desc: true }], columnFilters: [{ id: 'breached', value: true }], globalFilter: '', pageSize: 20 },
        { name: 'Production',    isSystem: true, columnVisibility: {}, columnOrder: [], sorting: [{ id: 'date', desc: true }], columnFilters: [{ id: 'environment', value: ['production'] }], globalFilter: '', pageSize: 20 },
        { name: 'Claude Models', isSystem: true, columnVisibility: {}, columnOrder: [], sorting: [{ id: 'metric', desc: false }], columnFilters: [{ id: 'model', value: ['claude-sonnet-4-6','claude-haiku-4-5'] }], globalFilter: '', pageSize: 50 },
      ]}
    />
  )
}
