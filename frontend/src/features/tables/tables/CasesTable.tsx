import { useState } from 'react'
import { createColumnHelper } from '@tanstack/react-table'
import { motion } from 'framer-motion'
import { FileText, CheckCircle2, XCircle, Clock, AlertTriangle, ArrowUpRight, Brain, Eye, UserCheck, Download } from 'lucide-react'
import { DataTable } from '@/components/data-table'
import type { FilterDef, RowAction } from '@/components/data-table'
import { formatDate, formatRelative } from '@/lib/utils'
import { generateCases, type CaseRow } from '../data/mockData'

const col = createColumnHelper<CaseRow>()

// ─── Status badge ─────────────────────────────────────────────────────────────

const STATUS_CFG: Record<string, { color: string; bg: string; icon: React.ElementType }> = {
  SUBMITTED:    { color: '#0ea5e9', bg: '#0ea5e915', icon: FileText     },
  UNDER_REVIEW: { color: '#f59e0b', bg: '#f59e0b15', icon: Eye          },
  PENDING_INFO: { color: '#f97316', bg: '#f9731615', icon: Clock        },
  APPROVED:     { color: '#10b981', bg: '#10b98115', icon: CheckCircle2 },
  DENIED:       { color: '#ef4444', bg: '#ef444415', icon: XCircle      },
  ESCALATED:    { color: '#a855f7', bg: '#a855f715', icon: ArrowUpRight },
  WITHDRAWN:    { color: '#6b7280', bg: '#6b728015', icon: FileText     },
}
const PRIORITY_CFG: Record<string, { color: string }> = {
  ROUTINE:  { color: '#6b7280' },
  URGENT:   { color: '#f97316' },
  EMERGENT: { color: '#ef4444' },
}
const AI_CFG: Record<string, { color: string }> = {
  APPROVE:      { color: '#10b981' },
  DENY:         { color: '#ef4444' },
  REQUEST_INFO: { color: '#f59e0b' },
  ESCALATE:     { color: '#a855f7' },
}

function StatusBadge({ status }: { status: string }) {
  const cfg  = STATUS_CFG[status] ?? { color: '#6b7280', bg: '#6b728015', icon: FileText }
  const Icon = cfg.icon
  return (
    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold whitespace-nowrap"
          style={{ background: cfg.bg, color: cfg.color }}>
      <Icon className="w-2.5 h-2.5" />
      {status.replace('_',' ')}
    </span>
  )
}

function ConfBar({ value }: { value: number }) {
  const color = value >= 0.85 ? '#10b981' : value >= 0.70 ? '#f59e0b' : '#ef4444'
  return (
    <div className="flex items-center gap-1.5 w-full">
      <div className="flex-1 h-1.5 rounded-full bg-[var(--surface)] overflow-hidden">
        <motion.div className="h-full rounded-full" style={{ width: `${value * 100}%`, background: color }}
                    initial={{ width: 0 }} animate={{ width: `${value * 100}%` }} transition={{ duration: 0.5 }} />
      </div>
      <span className="text-[10px] font-mono" style={{ color }}>{Math.round(value * 100)}%</span>
    </div>
  )
}

// ─── Expanded row ──────────────────────────────────────────────────────────────

function CaseExpandedRow({ row }: { row: CaseRow }) {
  return (
    <div className="px-6 py-4 grid grid-cols-3 gap-6">
      <div>
        <p className="text-[9px] uppercase tracking-wide text-[var(--text-4)] mb-2">Patient Details</p>
        <div className="space-y-1">
          {[['Member ID', row.patientId],['DOB', formatDate(row.dob)],['Plan', row.insurancePlan]].map(([k,v]) => (
            <div key={k} className="flex items-center gap-2">
              <span className="text-[10px] text-[var(--text-4)] w-20">{k}</span>
              <span className="text-[10px] text-[var(--text-2)] font-medium">{v}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <p className="text-[9px] uppercase tracking-wide text-[var(--text-4)] mb-2">Provider</p>
        <div className="space-y-1">
          {[['Name', row.provider],['Specialty', row.specialty],['NPI', row.npi]].map(([k,v]) => (
            <div key={k} className="flex items-center gap-2">
              <span className="text-[10px] text-[var(--text-4)] w-20">{k}</span>
              <span className="text-[10px] text-[var(--text-2)] font-medium">{v}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <p className="text-[9px] uppercase tracking-wide text-[var(--text-4)] mb-2">Clinical</p>
        <div className="space-y-1">
          {[['ICD Codes', row.diagnosisCodes],['Documents', `${row.documentsCount} files`],['SLA', `${row.slaHours}h remaining`]].map(([k,v]) => (
            <div key={k} className="flex items-center gap-2">
              <span className="text-[10px] text-[var(--text-4)] w-20">{k}</span>
              <span className="text-[10px] text-[var(--text-2)] font-medium truncate max-w-[140px]">{v}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Column definitions ───────────────────────────────────────────────────────

const COLUMNS = [
  col.accessor('caseNumber', {
    header: 'Case #', size: 130,
    cell: (i) => <span className="font-mono text-[11px] text-sky-400">{i.getValue()}</span>,
  }),
  col.accessor('status', {
    header: 'Status', size: 150,
    cell: (i) => <StatusBadge status={i.getValue()} />,
    filterFn: 'multiselect',
  }),
  col.accessor('priority', {
    header: 'Priority', size: 100,
    cell: (i) => {
      const cfg = PRIORITY_CFG[i.getValue()] ?? { color: '#6b7280' }
      return <span className="text-[11px] font-semibold" style={{ color: cfg.color }}>{i.getValue()}</span>
    },
    filterFn: 'multiselect',
  }),
  col.accessor('patientName', { header: 'Patient', size: 160 }),
  col.accessor('procedureCode', {
    header: 'CPT', size: 80,
    cell: (i) => <span className="font-mono text-[11px]">{i.getValue()}</span>,
  }),
  col.accessor('procedureDesc', { header: 'Procedure', size: 200 }),
  col.accessor('provider', { header: 'Provider', size: 170 }),
  col.accessor('aiRecommendation', {
    header: 'AI Rec', size: 130,
    cell: (i) => {
      const cfg = AI_CFG[i.getValue()] ?? { color: '#6b7280' }
      return (
        <span className="flex items-center gap-1 text-[10px] font-semibold" style={{ color: cfg.color }}>
          <Brain className="w-3 h-3" />
          {i.getValue().replace('_',' ')}
        </span>
      )
    },
    filterFn: 'multiselect',
  }),
  col.accessor('aiConfidence', {
    header: 'AI Confidence', size: 130,
    cell: (i) => <ConfBar value={i.getValue()} />,
    filterFn: 'numberrange',
  }),
  col.accessor('reviewer', {
    header: 'Reviewer', size: 150,
    cell: (i) => i.getValue()
      ? <span className="flex items-center gap-1 text-[11px]"><UserCheck className="w-3 h-3 text-sky-400" />{i.getValue()}</span>
      : <span className="text-[10px] text-[var(--text-4)]">Unassigned</span>,
  }),
  col.accessor('submittedAt', {
    header: 'Submitted', size: 130,
    cell: (i) => <span className="text-[11px] text-[var(--text-3)]">{formatRelative(i.getValue())}</span>,
    filterFn: 'daterange',
  }),
  col.accessor('slaHours', {
    header: 'SLA (hrs)', size: 100,
    cell: (i) => {
      const h = i.getValue()
      const color = h < 12 ? '#ef4444' : h < 24 ? '#f59e0b' : '#10b981'
      return <span className="font-mono text-[11px]" style={{ color }}>{h}h</span>
    },
    filterFn: 'numberrange',
  }),
  col.accessor('insurancePlan', { header: 'Plan', size: 160, filterFn: 'multiselect' }),
  col.accessor('documentsCount', {
    header: 'Docs', size: 70,
    cell: (i) => <span className="flex items-center gap-1 text-[11px]"><FileText className="w-3 h-3 text-[var(--text-4)]" />{i.getValue()}</span>,
  }),
]

const FILTER_DEFS: FilterDef[] = [
  { id: 'status',   label: 'Status',   type: 'multiselect', options: Object.keys(STATUS_CFG).map((v) => ({ value: v, label: v.replace('_',' '), color: STATUS_CFG[v].color })) },
  { id: 'priority', label: 'Priority', type: 'multiselect', options: [{ value:'ROUTINE',label:'Routine',color:'#6b7280' },{ value:'URGENT',label:'Urgent',color:'#f97316' },{ value:'EMERGENT',label:'Emergent',color:'#ef4444' }] },
  { id: 'aiRecommendation', label: 'AI Rec', type: 'multiselect', options: [{ value:'APPROVE',label:'Approve',color:'#10b981' },{ value:'DENY',label:'Deny',color:'#ef4444' },{ value:'REQUEST_INFO',label:'Request Info',color:'#f59e0b' },{ value:'ESCALATE',label:'Escalate',color:'#a855f7' }] },
  { id: 'aiConfidence', label: 'AI Confidence', type: 'numberrange', min: 0, max: 1 },
  { id: 'submittedAt',  label: 'Submitted',     type: 'daterange' },
  { id: 'slaHours',     label: 'SLA Hours',     type: 'numberrange', min: 0, max: 72 },
]

const ROW_ACTIONS: RowAction<CaseRow>[] = [
  { action: 'review',  label: 'Open Review',  icon: Eye,        color: '#0ea5e9' },
  { action: 'approve', label: 'Quick Approve', icon: CheckCircle2, color: '#10b981', condition: (r) => r.status === 'UNDER_REVIEW' },
  { action: 'deny',    label: 'Quick Deny',    icon: XCircle,    color: '#ef4444', condition: (r) => r.status === 'UNDER_REVIEW', destructive: true },
  { action: 'assign',  label: 'Assign',        icon: UserCheck,  color: '#6366f1', condition: (r) => !r.reviewer },
  { action: 'export',  label: 'Export',        icon: Download,   color: '#6b7280' },
]

const SYSTEM_VIEWS = [
  { name: 'Pending Review', isSystem: true, columnVisibility: {}, columnOrder: [], sorting: [{ id: 'submittedAt', desc: false }], columnFilters: [{ id: 'status', value: ['SUBMITTED','UNDER_REVIEW'] }], globalFilter: '', pageSize: 20 },
  { name: 'AI Conflicts',   isSystem: true, columnVisibility: {}, columnOrder: [], sorting: [{ id: 'aiConfidence', desc: false }], columnFilters: [{ id: 'aiConfidence', value: ['', 0.7] }], globalFilter: '', pageSize: 20 },
  { name: 'SLA At Risk',    isSystem: true, columnVisibility: {}, columnOrder: [], sorting: [{ id: 'slaHours', desc: false }], columnFilters: [{ id: 'slaHours', value: ['', 24] }], globalFilter: '', pageSize: 20 },
]

// ─── Component ────────────────────────────────────────────────────────────────

export function CasesTable() {
  const [data]   = useState(() => generateCases(250))
  const [action, setAction] = useState<{ action: string; caseNumber: string } | null>(null)

  return (
    <div className="h-full flex flex-col gap-3">
      {action && (
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg text-[11px]"
                    style={{ background: '#10b98115', border: '1px solid #10b98130', color: '#10b981' }}>
          <AlertTriangle className="w-3.5 h-3.5" />
          Action <strong>{action.action}</strong> triggered on case <strong>{action.caseNumber}</strong>
          <button onClick={() => setAction(null)} className="ml-auto"><XCircle className="w-3.5 h-3.5" /></button>
        </motion.div>
      )}
      <DataTable
        tableId="cases"
        data={data}
        columns={COLUMNS}
        filterDefs={FILTER_DEFS}
        defaultSorting={[{ id: 'submittedAt', desc: true }]}
        defaultColumnVisibility={{ npi: false, diagnosisCodes: false }}
        expandedRowRenderer={(row) => <CaseExpandedRow row={row} />}
        rowActions={ROW_ACTIONS}
        onRowAction={(a, row) => setAction({ action: a, caseNumber: row.caseNumber })}
        height={580}
        systemViews={SYSTEM_VIEWS}
      />
    </div>
  )
}
