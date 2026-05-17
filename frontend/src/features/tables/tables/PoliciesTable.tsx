import { useState } from 'react'
import { createColumnHelper } from '@tanstack/react-table'
import { BookOpen, CheckCircle2, Clock, Archive, Edit2, Trash2, Download, Copy } from 'lucide-react'
import { DataTable } from '@/components/data-table'
import type { FilterDef, RowAction } from '@/components/data-table'
import { formatDate, formatRelative } from '@/lib/utils'
import { generatePolicies, type PolicyRow } from '../data/mockData'

const col = createColumnHelper<PolicyRow>()

const STATUS_CFG: Record<string, { color: string; bg: string; icon: React.ElementType }> = {
  active:       { color: '#10b981', bg: '#10b98115', icon: CheckCircle2 },
  draft:        { color: '#6b7280', bg: '#6b728015', icon: Edit2        },
  under_review: { color: '#f59e0b', bg: '#f59e0b15', icon: Clock        },
  archived:     { color: '#6366f1', bg: '#6366f115', icon: Archive      },
}

function StatusBadge({ status }: { status: string }) {
  const cfg  = STATUS_CFG[status] ?? STATUS_CFG['draft']
  const Icon = cfg.icon
  return (
    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold"
          style={{ background: cfg.bg, color: cfg.color }}>
      <Icon className="w-2.5 h-2.5" />
      {status.replace('_',' ')}
    </span>
  )
}

function ScoreBar({ value }: { value: number }) {
  const color = value >= 0.85 ? '#10b981' : value >= 0.75 ? '#f59e0b' : '#ef4444'
  return (
    <div className="flex items-center gap-1.5 w-full">
      <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--surface)' }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${value * 100}%`, background: color }} />
      </div>
      <span className="text-[10px] font-mono w-8 text-right" style={{ color }}>{Math.round(value * 100)}%</span>
    </div>
  )
}

function PolicyExpandedRow({ row }: { row: PolicyRow }) {
  return (
    <div className="px-6 py-4 grid grid-cols-3 gap-6">
      <div>
        <p className="text-[9px] uppercase tracking-wide text-[var(--text-4)] mb-2">Description</p>
        <p className="text-[11px] text-[var(--text-2)] leading-relaxed">{row.description}</p>
      </div>
      <div>
        <p className="text-[9px] uppercase tracking-wide text-[var(--text-4)] mb-2">Code Mappings</p>
        <div className="space-y-1">
          {[['CPT Codes', row.procedureCodes],['ICD Codes', row.icdCodes],['Chunks', `${row.chunksCount} chunks`]].map(([k,v]) => (
            <div key={k} className="flex items-start gap-2">
              <span className="text-[10px] text-[var(--text-4)] w-20 flex-shrink-0">{k}</span>
              <span className="text-[10px] text-[var(--text-2)] font-mono">{v}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <p className="text-[9px] uppercase tracking-wide text-[var(--text-4)] mb-2">Lifecycle</p>
        <div className="space-y-1">
          {[['Effective', formatDate(row.effectiveDate)],['Expiry', row.expiryDate ? formatDate(row.expiryDate) : 'No expiry'],['Review', row.reviewCycle],['Size', `${row.documentSizeKb} KB`]].map(([k,v]) => (
            <div key={k} className="flex items-center gap-2">
              <span className="text-[10px] text-[var(--text-4)] w-20">{k}</span>
              <span className="text-[10px] text-[var(--text-2)] font-medium">{v}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

const COLUMNS = [
  col.accessor('name', {
    header: 'Policy Name', size: 240,
    cell: (i) => (
      <span className="flex items-center gap-2 font-medium text-[11px]">
        <BookOpen className="w-3 h-3 text-indigo-400 flex-shrink-0" />
        <span className="truncate">{i.getValue()}</span>
      </span>
    ),
  }),
  col.accessor('status', {
    header: 'Status', size: 130,
    cell: (i) => <StatusBadge status={i.getValue()} />,
    filterFn: 'multiselect',
  }),
  col.accessor('version', {
    header: 'Version', size: 80,
    cell: (i) => <span className="font-mono text-[11px] text-sky-400">v{i.getValue()}</span>,
  }),
  col.accessor('category', { header: 'Category', size: 160, filterFn: 'multiselect' }),
  col.accessor('chunksCount', {
    header: 'Chunks', size: 80,
    cell: (i) => <span className="font-mono text-[11px]">{i.getValue()}</span>,
    filterFn: 'numberrange',
  }),
  col.accessor('retrievalScore', {
    header: 'Retrieval Score', size: 150,
    cell: (i) => <ScoreBar value={i.getValue()} />,
    filterFn: 'numberrange',
  }),
  col.accessor('createdBy', { header: 'Author', size: 160 }),
  col.accessor('approvedBy', {
    header: 'Approved By', size: 160,
    cell: (i) => i.getValue()
      ? <span className="text-[11px]">{i.getValue()}</span>
      : <span className="text-[10px] text-[var(--text-4)]">Pending</span>,
  }),
  col.accessor('lastUpdated', {
    header: 'Last Updated', size: 130,
    cell: (i) => <span className="text-[11px] text-[var(--text-3)]">{formatRelative(i.getValue())}</span>,
    filterFn: 'daterange',
  }),
  col.accessor('documentSizeKb', {
    header: 'Size (KB)', size: 90,
    cell: (i) => <span className="font-mono text-[11px]">{i.getValue()}</span>,
  }),
  col.accessor('reviewCycle', { header: 'Review Cycle', size: 120, filterFn: 'multiselect' }),
]

const FILTER_DEFS: FilterDef[] = [
  { id: 'status',   label: 'Status',   type: 'multiselect', options: Object.keys(STATUS_CFG).map((v) => ({ value: v, label: v.replace('_',' '), color: STATUS_CFG[v].color })) },
  { id: 'category', label: 'Category', type: 'multiselect', options: ['Medical/Surgical','Behavioral Health','Radiology','Physical Therapy','Cardiology','Oncology','Preventive'].map((v) => ({ value: v, label: v })) },
  { id: 'retrievalScore', label: 'Retrieval Score', type: 'numberrange', min: 0, max: 1 },
  { id: 'chunksCount',    label: 'Chunks',          type: 'numberrange', min: 0, max: 30 },
  { id: 'lastUpdated',    label: 'Last Updated',    type: 'daterange' },
  { id: 'reviewCycle',    label: 'Review Cycle',    type: 'multiselect', options: ['Annual','Bi-Annual','Quarterly','On-Demand'].map((v) => ({ value: v, label: v })) },
]

const ROW_ACTIONS: RowAction<PolicyRow>[] = [
  { action: 'edit',    label: 'Edit Policy',   icon: Edit2,   color: '#6366f1' },
  { action: 'copy',    label: 'Duplicate',     icon: Copy,    color: '#0ea5e9' },
  { action: 'export',  label: 'Export',        icon: Download, color: '#6b7280' },
  { action: 'archive', label: 'Archive',       icon: Archive, color: '#f59e0b', condition: (r) => r.status !== 'archived' },
  { action: 'delete',  label: 'Delete',        icon: Trash2,  destructive: true, condition: (r) => r.status === 'draft' },
]

export function PoliciesTable() {
  const [data] = useState(() => generatePolicies(40))

  return (
    <DataTable
      tableId="policies"
      data={data}
      columns={COLUMNS}
      filterDefs={FILTER_DEFS}
      defaultSorting={[{ id: 'lastUpdated', desc: true }]}
      expandedRowRenderer={(row) => <PolicyExpandedRow row={row} />}
      rowActions={ROW_ACTIONS}
      height={580}
      systemViews={[
        { name: 'Active Only',   isSystem: true, columnVisibility: {}, columnOrder: [], sorting: [{ id: 'name', desc: false }], columnFilters: [{ id: 'status', value: ['active'] }], globalFilter: '', pageSize: 20 },
        { name: 'Needs Review',  isSystem: true, columnVisibility: {}, columnOrder: [], sorting: [{ id: 'lastUpdated', desc: false }], columnFilters: [{ id: 'status', value: ['under_review'] }], globalFilter: '', pageSize: 20 },
        { name: 'Low Retrieval', isSystem: true, columnVisibility: {}, columnOrder: [], sorting: [{ id: 'retrievalScore', desc: false }], columnFilters: [{ id: 'retrievalScore', value: ['', 0.8] }], globalFilter: '', pageSize: 20 },
      ]}
    />
  )
}
