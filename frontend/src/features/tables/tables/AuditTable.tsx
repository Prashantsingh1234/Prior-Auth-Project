import { useState } from 'react'
import { createColumnHelper } from '@tanstack/react-table'
import { Lock, Brain, FileText, Shield, Activity, MessageSquare, Download } from 'lucide-react'
import { DataTable } from '@/components/data-table'
import type { FilterDef, RowAction } from '@/components/data-table'
import { formatRelative } from '@/lib/utils'
import { generateAuditEntries, type AuditRow } from '../data/mockData'

const col = createColumnHelper<AuditRow>()

const CATEGORY_CFG: Record<string, { color: string; bg: string; icon: React.ElementType }> = {
  decision:      { color: '#10b981', bg: '#10b98115', icon: Activity      },
  ai:            { color: '#8b5cf6', bg: '#8b5cf615', icon: Brain         },
  clarification: { color: '#f59e0b', bg: '#f59e0b15', icon: MessageSquare },
  document:      { color: '#0ea5e9', bg: '#0ea5e915', icon: FileText      },
  policy:        { color: '#6366f1', bg: '#6366f115', icon: Shield        },
  system:        { color: '#6b7280', bg: '#6b728015', icon: Activity      },
  compliance:    { color: '#ef4444', bg: '#ef444415', icon: Shield        },
}
const ROLE_CFG: Record<string, { color: string }> = {
  reviewer:   { color: '#0ea5e9' },
  admin:      { color: '#6366f1' },
  ai_system:  { color: '#8b5cf6' },
  provider:   { color: '#10b981' },
  system:     { color: '#6b7280' },
}

function AuditExpandedRow({ row }: { row: AuditRow }) {
  return (
    <div className="px-6 py-4 grid grid-cols-3 gap-6">
      <div>
        <p className="text-[9px] uppercase tracking-wide text-[var(--text-4)] mb-2">Integrity</p>
        <div className="flex items-center gap-2 p-2 rounded-lg" style={{ background: '#10b98110', border: '1px solid #10b98125' }}>
          <Lock className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
          <span className="font-mono text-[9px] text-emerald-400 break-all">{row.integrityHash}</span>
        </div>
      </div>
      <div>
        <p className="text-[9px] uppercase tracking-wide text-[var(--text-4)] mb-2">Session</p>
        <div className="space-y-1">
          {[['Session ID', row.sessionId],['IP Address', row.ipAddress],['User Agent', 'Mozilla/5.0 Chrome/120']].map(([k,v]) => (
            <div key={k} className="flex items-center gap-2">
              <span className="text-[10px] text-[var(--text-4)] w-24">{k}</span>
              <span className="font-mono text-[10px] text-[var(--text-2)]">{v}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <p className="text-[9px] uppercase tracking-wide text-[var(--text-4)] mb-2">Metadata</p>
        <pre className="text-[9px] font-mono text-[var(--text-3)] bg-[var(--surface)] p-2 rounded overflow-auto max-h-20">
          {JSON.stringify(JSON.parse(row.metadata), null, 2)}
        </pre>
      </div>
    </div>
  )
}

const COLUMNS = [
  col.accessor('occurredAt', {
    header: 'Time', size: 120,
    cell: (i) => <span className="text-[11px] text-[var(--text-3)]">{formatRelative(i.getValue())}</span>,
    filterFn: 'daterange',
  }),
  col.accessor('caseRef', {
    header: 'Case', size: 130,
    cell: (i) => <span className="font-mono text-[11px] text-sky-400">{i.getValue()}</span>,
  }),
  col.accessor('eventType', {
    header: 'Event', size: 180,
    cell: (i) => <span className="font-mono text-[10px] text-[var(--text-2)]">{i.getValue().replace(/_/g,' ')}</span>,
    filterFn: 'multiselect',
  }),
  col.accessor('category', {
    header: 'Category', size: 130,
    cell: (i) => {
      const cfg  = CATEGORY_CFG[i.getValue()] ?? CATEGORY_CFG['system']
      const Icon = cfg.icon
      return (
        <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold"
              style={{ background: cfg.bg, color: cfg.color }}>
          <Icon className="w-2.5 h-2.5" />
          {i.getValue()}
        </span>
      )
    },
    filterFn: 'multiselect',
  }),
  col.accessor('actorName', { header: 'Actor', size: 160 }),
  col.accessor('actorRole', {
    header: 'Role', size: 110,
    cell: (i) => {
      const cfg = ROLE_CFG[i.getValue()] ?? { color: '#6b7280' }
      return <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: cfg.color }}>{i.getValue().replace('_',' ')}</span>
    },
    filterFn: 'multiselect',
  }),
  col.accessor('description', {
    header: 'Description', size: 280,
    cell: (i) => <span className="text-[11px] text-[var(--text-2)] truncate block max-w-[260px]">{i.getValue()}</span>,
  }),
  col.accessor('ipAddress', {
    header: 'IP Address', size: 130,
    cell: (i) => <span className="font-mono text-[11px] text-[var(--text-4)]">{i.getValue()}</span>,
  }),
  col.accessor('immutable', {
    header: 'Integrity', size: 90,
    cell: () => (
      <span className="flex items-center gap-1 text-emerald-400 text-[10px] font-semibold">
        <Lock className="w-3 h-3" />
        IMMUTABLE
      </span>
    ),
  }),
]

const EVENT_TYPES = ['SUBMITTED','ASSIGNED','REVIEWED','APPROVED','DENIED','ESCALATED','AI_PROCESSED','AI_OUTPUT','AI_OVERRIDE','PROMPT_TRACE','RETRIEVAL_TRACE','CLARIFICATION_REQUESTED','DOCUMENT_UPLOADED','DOCUMENT_OCR','POLICY_MATCHED','COMPLIANCE_EXPORT','ACCESS_GRANTED','SLA_WARNING','SLA_BREACHED']
const CATEGORIES  = ['decision','ai','clarification','document','policy','system','compliance']
const ACTOR_ROLES = ['reviewer','admin','ai_system','provider','system']

const FILTER_DEFS: FilterDef[] = [
  { id: 'category',  label: 'Category',   type: 'multiselect', options: CATEGORIES.map((v)  => ({ value: v, label: v, color: CATEGORY_CFG[v].color })) },
  { id: 'actorRole', label: 'Role',       type: 'multiselect', options: ACTOR_ROLES.map((v)  => ({ value: v, label: v.replace('_',' '), color: ROLE_CFG[v]?.color })) },
  { id: 'eventType', label: 'Event Type', type: 'multiselect', options: EVENT_TYPES.map((v) => ({ value: v, label: v.replace(/_/g,' ') })) },
  { id: 'occurredAt', label: 'Date Range', type: 'daterange' },
]

const ROW_ACTIONS: RowAction<AuditRow>[] = [
  { action: 'export', label: 'Export Entry', icon: Download, color: '#10b981' },
  { action: 'view',   label: 'View Case',    icon: Activity, color: '#0ea5e9' },
]

export function AuditTable() {
  const [data] = useState(() => generateAuditEntries(500))

  return (
    <DataTable
      tableId="audit"
      data={data}
      columns={COLUMNS}
      filterDefs={FILTER_DEFS}
      defaultSorting={[{ id: 'occurredAt', desc: true }]}
      expandedRowRenderer={(row) => <AuditExpandedRow row={row} />}
      rowActions={ROW_ACTIONS}
      height={580}
      systemViews={[
        { name: 'AI Events',   isSystem: true, columnVisibility: {}, columnOrder: [], sorting: [{ id: 'occurredAt', desc: true }], columnFilters: [{ id: 'category', value: ['ai'] }], globalFilter: '', pageSize: 50 },
        { name: 'SLA Breaches',isSystem: true, columnVisibility: {}, columnOrder: [], sorting: [{ id: 'occurredAt', desc: true }], columnFilters: [{ id: 'eventType', value: ['SLA_BREACHED','SLA_WARNING'] }], globalFilter: '', pageSize: 20 },
        { name: 'Decisions',   isSystem: true, columnVisibility: {}, columnOrder: [], sorting: [{ id: 'occurredAt', desc: true }], columnFilters: [{ id: 'category', value: ['decision'] }], globalFilter: '', pageSize: 50 },
      ]}
    />
  )
}
