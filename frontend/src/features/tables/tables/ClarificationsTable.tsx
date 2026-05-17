import { useState } from 'react'
import { createColumnHelper } from '@tanstack/react-table'
import { Clock, CheckCircle2, XCircle, ArrowUpRight, Brain, Paperclip, Send, Eye } from 'lucide-react'
import { DataTable } from '@/components/data-table'
import type { FilterDef, RowAction } from '@/components/data-table'
import { formatDate, formatRelative } from '@/lib/utils'
import { generateClarifications, type ClarificationRow } from '../data/mockData'

const col = createColumnHelper<ClarificationRow>()

const STATUS_CFG: Record<string, { color: string; bg: string; icon: React.ElementType }> = {
  pending:   { color: '#f59e0b', bg: '#f59e0b15', icon: Clock        },
  answered:  { color: '#10b981', bg: '#10b98115', icon: CheckCircle2 },
  expired:   { color: '#ef4444', bg: '#ef444415', icon: XCircle      },
  escalated: { color: '#a855f7', bg: '#a855f715', icon: ArrowUpRight },
  withdrawn: { color: '#6b7280', bg: '#6b728015', icon: XCircle      },
}
const PRIORITY_CFG: Record<string, string> = { ROUTINE: '#6b7280', URGENT: '#f97316', EMERGENT: '#ef4444' }

function ClarificationExpandedRow({ row }: { row: ClarificationRow }) {
  return (
    <div className="px-6 py-4 space-y-4">
      <div className="flex gap-4">
        <div className="flex-1 rounded-lg p-3" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
          <p className="text-[9px] uppercase tracking-wide text-[var(--text-4)] mb-1.5">Question</p>
          <p className="text-[11px] text-[var(--text-2)] leading-relaxed">{row.questionText}</p>
          <p className="text-[9px] text-[var(--text-4)] mt-2">
            Requested by {row.requestedBy} · {formatRelative(row.requestedAt)}
            {row.aiSuggested && (
              <span className="ml-2 px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-400 text-[8px] font-semibold">AI SUGGESTED</span>
            )}
          </p>
        </div>
        {row.answerText && (
          <div className="flex-1 rounded-lg p-3" style={{ background: '#10b98108', border: '1px solid #10b98125' }}>
            <p className="text-[9px] uppercase tracking-wide text-emerald-400 mb-1.5">Answer</p>
            <p className="text-[11px] text-[var(--text-2)] leading-relaxed">{row.answerText}</p>
            <p className="text-[9px] text-[var(--text-4)] mt-2">
              {row.answeredBy} · {row.answeredAt ? formatRelative(row.answeredAt) : ''}
              {row.responseTimeHours && (
                <span className="ml-2 text-sky-400">Response in {row.responseTimeHours}h</span>
              )}
            </p>
          </div>
        )}
      </div>
      <div className="flex items-center gap-6 text-[10px] text-[var(--text-4)]">
        <span>Due: <strong className="text-[var(--text-2)]">{formatDate(row.dueDate)}</strong></span>
        <span>Category: <strong className="text-[var(--text-2)]">{row.category}</strong></span>
        {row.attachments > 0 && <span className="flex items-center gap-1"><Paperclip className="w-3 h-3" />{row.attachments} attachments</span>}
      </div>
    </div>
  )
}

const COLUMNS = [
  col.accessor('caseRef', {
    header: 'Case', size: 130,
    cell: (i) => <span className="font-mono text-[11px] text-sky-400">{i.getValue()}</span>,
  }),
  col.accessor('status', {
    header: 'Status', size: 120,
    cell: (i) => {
      const cfg  = STATUS_CFG[i.getValue()] ?? STATUS_CFG['pending']
      const Icon = cfg.icon
      return (
        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold"
              style={{ background: cfg.bg, color: cfg.color }}>
          <Icon className="w-2.5 h-2.5" />
          {i.getValue()}
        </span>
      )
    },
    filterFn: 'multiselect',
  }),
  col.accessor('priority', {
    header: 'Priority', size: 100,
    cell: (i) => {
      const color = PRIORITY_CFG[i.getValue()] ?? '#6b7280'
      return <span className="text-[11px] font-semibold" style={{ color }}>{i.getValue()}</span>
    },
    filterFn: 'multiselect',
  }),
  col.accessor('questionText', {
    header: 'Question', size: 300,
    cell: (i) => <span className="text-[11px] text-[var(--text-2)] truncate block max-w-[280px]">{i.getValue()}</span>,
  }),
  col.accessor('category', { header: 'Category', size: 180, filterFn: 'multiselect' }),
  col.accessor('requestedBy', { header: 'Requested By', size: 160 }),
  col.accessor('requestedAt', {
    header: 'Requested', size: 120,
    cell: (i) => <span className="text-[11px] text-[var(--text-3)]">{formatRelative(i.getValue())}</span>,
    filterFn: 'daterange',
  }),
  col.accessor('dueDate', {
    header: 'Due Date', size: 110,
    cell: (i) => {
      const isPast = new Date(i.getValue()) < new Date()
      return <span className="text-[11px]" style={{ color: isPast ? '#ef4444' : 'var(--text-3)' }}>{formatDate(i.getValue())}</span>
    },
  }),
  col.accessor('responseTimeHours', {
    header: 'Response Time', size: 130,
    cell: (i) => i.getValue()
      ? <span className="font-mono text-[11px] text-sky-400">{i.getValue()}h</span>
      : <span className="text-[10px] text-[var(--text-4)]">—</span>,
    filterFn: 'numberrange',
  }),
  col.accessor('aiSuggested', {
    header: 'AI Suggested', size: 120,
    cell: (i) => i.getValue()
      ? <span className="flex items-center gap-1 text-[10px] font-semibold text-violet-400"><Brain className="w-3 h-3" />AI</span>
      : <span className="text-[10px] text-[var(--text-4)]">Manual</span>,
    filterFn: 'boolean',
  }),
  col.accessor('escalated', {
    header: 'Escalated', size: 100,
    cell: (i) => i.getValue()
      ? <span className="text-[10px] font-semibold text-purple-400"><ArrowUpRight className="w-3 h-3 inline mr-0.5" />Yes</span>
      : <span className="text-[10px] text-[var(--text-4)]">No</span>,
    filterFn: 'boolean',
  }),
  col.accessor('attachments', {
    header: 'Attachments', size: 100,
    cell: (i) => i.getValue() > 0
      ? <span className="flex items-center gap-1 text-[11px]"><Paperclip className="w-3 h-3 text-[var(--text-4)]" />{i.getValue()}</span>
      : <span className="text-[10px] text-[var(--text-4)]">—</span>,
  }),
]

const FILTER_DEFS: FilterDef[] = [
  { id: 'status',   label: 'Status',   type: 'multiselect', options: Object.keys(STATUS_CFG).map((v) => ({ value: v, label: v, color: STATUS_CFG[v].color })) },
  { id: 'priority', label: 'Priority', type: 'multiselect', options: [{ value:'ROUTINE',label:'Routine',color:'#6b7280' },{ value:'URGENT',label:'Urgent',color:'#f97316' },{ value:'EMERGENT',label:'Emergent',color:'#ef4444' }] },
  { id: 'category', label: 'Category', type: 'multiselect', options: ['Clinical Documentation','Diagnosis Clarification','Treatment Plan','Provider Information','Insurance Eligibility','Medical History'].map((v) => ({ value: v, label: v })) },
  { id: 'aiSuggested', label: 'AI Suggested', type: 'boolean' },
  { id: 'escalated',   label: 'Escalated',    type: 'boolean' },
  { id: 'requestedAt', label: 'Date Range',   type: 'daterange' },
  { id: 'responseTimeHours', label: 'Response Time (h)', type: 'numberrange', min: 0, max: 48 },
]

const ROW_ACTIONS: RowAction<ClarificationRow>[] = [
  { action: 'view',     label: 'View Case',     icon: Eye,         color: '#0ea5e9' },
  { action: 'respond',  label: 'Send Response', icon: Send,        color: '#10b981', condition: (r) => r.status === 'pending' },
  { action: 'escalate', label: 'Escalate',      icon: ArrowUpRight, color: '#a855f7', condition: (r) => r.status === 'pending' },
  { action: 'close',    label: 'Close',         icon: XCircle,     destructive: true, condition: (r) => r.status !== 'answered' },
]

export function ClarificationsTable() {
  const [data] = useState(() => generateClarifications(120))

  return (
    <DataTable
      tableId="clarifications"
      data={data}
      columns={COLUMNS}
      filterDefs={FILTER_DEFS}
      defaultSorting={[{ id: 'requestedAt', desc: true }]}
      expandedRowRenderer={(row) => <ClarificationExpandedRow row={row} />}
      rowActions={ROW_ACTIONS}
      height={580}
      systemViews={[
        { name: 'Pending Response', isSystem: true, columnVisibility: {}, columnOrder: [], sorting: [{ id: 'dueDate', desc: false }], columnFilters: [{ id: 'status', value: ['pending'] }], globalFilter: '', pageSize: 20 },
        { name: 'AI Suggestions',   isSystem: true, columnVisibility: {}, columnOrder: [], sorting: [{ id: 'requestedAt', desc: true }], columnFilters: [{ id: 'aiSuggested', value: true }], globalFilter: '', pageSize: 20 },
        { name: 'Overdue',          isSystem: true, columnVisibility: {}, columnOrder: [], sorting: [{ id: 'dueDate', desc: false }], columnFilters: [{ id: 'status', value: ['pending','escalated'] }], globalFilter: '', pageSize: 20 },
      ]}
    />
  )
}
