import { useState } from 'react'
import { createColumnHelper } from '@tanstack/react-table'
import { motion } from 'framer-motion'
import { UserCheck, Mail, Star, MessageSquare, Award } from 'lucide-react'
import { DataTable } from '@/components/data-table'
import type { FilterDef, RowAction } from '@/components/data-table'
import { formatDate, formatRelative } from '@/lib/utils'
import { generateReviewers, type ReviewerRow } from '../data/mockData'

const col = createColumnHelper<ReviewerRow>()

const STATUS_CFG: Record<string, { color: string; bg: string }> = {
  active:   { color: '#10b981', bg: '#10b98115' },
  on_leave: { color: '#f59e0b', bg: '#f59e0b15' },
  inactive: { color: '#6b7280', bg: '#6b728015' },
}
const ROLE_CFG: Record<string, { color: string }> = {
  reviewer:          { color: '#0ea5e9' },
  senior_reviewer:   { color: '#6366f1' },
  admin:             { color: '#a855f7' },
  medical_director:  { color: '#f59e0b' },
}

function RateBadge({ value, threshold }: { value: number; threshold: number }) {
  const pct   = Math.round(value * 100)
  const color = value >= threshold ? '#10b981' : value >= threshold * 0.85 ? '#f59e0b' : '#ef4444'
  return (
    <div className="flex items-center gap-1.5 w-full">
      <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--surface)' }}>
        <motion.div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }}
                    initial={{ width: 0 }} animate={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] font-mono w-8 text-right" style={{ color }}>{pct}%</span>
    </div>
  )
}


function ReviewerExpandedRow({ row }: { row: ReviewerRow }) {
  const completionRate = row.casesCompleted / row.casesAssigned
  return (
    <div className="px-6 py-4 grid grid-cols-4 gap-6">
      {[
        { label: 'Completion Rate', value: `${Math.round(completionRate * 100)}%`, color: '#10b981' },
        { label: 'Avg Decision',    value: `${row.avgDecisionHours}h`,             color: '#0ea5e9' },
        { label: 'Agreement Rate',  value: `${Math.round(row.agreementRate * 100)}%`, color: '#6366f1' },
        { label: 'Override Rate',   value: `${Math.round(row.overrideRate * 100)}%`, color: '#f59e0b' },
      ].map((stat) => (
        <div key={stat.label} className="rounded-lg p-3 text-center"
             style={{ background: `${stat.color}08`, border: `1px solid ${stat.color}20` }}>
          <p className="text-lg font-bold" style={{ color: stat.color }}>{stat.value}</p>
          <p className="text-[9px] text-[var(--text-4)] mt-0.5">{stat.label}</p>
        </div>
      ))}
      <div className="col-span-4 flex items-center gap-4 text-[10px] text-[var(--text-3)]">
        <span>Joined: {formatDate(row.joinedAt)}</span>
        <span>·</span>
        <span>Region: {row.region}</span>
        <span>·</span>
        <span>Certs: {row.certifications}</span>
        <span>·</span>
        <span>NPS: <strong className="text-emerald-400">{row.nps}</strong></span>
      </div>
    </div>
  )
}

const COLUMNS = [
  col.accessor('name', {
    header: 'Reviewer', size: 200,
    cell: (i) => (
      <span className="flex items-center gap-2">
        <div className="w-6 h-6 rounded-full bg-indigo-500/20 flex items-center justify-center flex-shrink-0">
          <UserCheck className="w-3 h-3 text-indigo-400" />
        </div>
        <span className="font-medium text-[11px]">{i.getValue()}</span>
      </span>
    ),
  }),
  col.accessor('email', {
    header: 'Email', size: 220,
    cell: (i) => (
      <span className="flex items-center gap-1.5 text-[11px] text-[var(--text-3)]">
        <Mail className="w-3 h-3 flex-shrink-0" />
        <span className="truncate">{i.getValue()}</span>
      </span>
    ),
  }),
  col.accessor('status', {
    header: 'Status', size: 110,
    cell: (i) => {
      const cfg = STATUS_CFG[i.getValue()] ?? STATUS_CFG['inactive']
      return (
        <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold"
              style={{ background: cfg.bg, color: cfg.color }}>
          <div className="w-1.5 h-1.5 rounded-full" style={{ background: cfg.color }} />
          {i.getValue().replace('_',' ')}
        </span>
      )
    },
    filterFn: 'multiselect',
  }),
  col.accessor('role', {
    header: 'Role', size: 160,
    cell: (i) => {
      const cfg = ROLE_CFG[i.getValue()] ?? { color: '#6b7280' }
      return <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: cfg.color }}>{i.getValue().replace(/_/g,' ')}</span>
    },
    filterFn: 'multiselect',
  }),
  col.accessor('specialty', { header: 'Specialty', size: 160, filterFn: 'multiselect' }),
  col.accessor('caseload', {
    header: 'Current Load', size: 110,
    cell: (i) => {
      const v = i.getValue()
      const color = v > 20 ? '#ef4444' : v > 15 ? '#f59e0b' : '#10b981'
      return <span className="font-mono text-[11px] font-semibold" style={{ color }}>{v}</span>
    },
    filterFn: 'numberrange',
  }),
  col.accessor('casesCompleted', {
    header: 'Completed', size: 100,
    cell: (i) => <span className="font-mono text-[11px]">{i.getValue()}</span>,
  }),
  col.accessor('avgDecisionHours', {
    header: 'Avg Decision (h)', size: 140,
    cell: (i) => {
      const v = i.getValue()
      const color = v <= 4 ? '#10b981' : v <= 12 ? '#f59e0b' : '#ef4444'
      return <span className="font-mono text-[11px]" style={{ color }}>{v}h</span>
    },
    filterFn: 'numberrange',
  }),
  col.accessor('agreementRate', {
    header: 'Agreement', size: 140,
    cell: (i) => <RateBadge value={i.getValue()} threshold={0.85} />,
    filterFn: 'numberrange',
  }),
  col.accessor('overrideRate', {
    header: 'Override Rate', size: 130,
    cell: (i) => <RateBadge value={i.getValue()} threshold={0.1} />,
  }),
  col.accessor('nps', {
    header: 'NPS', size: 80,
    cell: (i) => {
      const v = i.getValue()
      const color = v >= 70 ? '#10b981' : v >= 50 ? '#f59e0b' : '#ef4444'
      return (
        <span className="flex items-center gap-1 font-mono text-[11px]" style={{ color }}>
          <Star className="w-2.5 h-2.5" />
          {v}
        </span>
      )
    },
  }),
  col.accessor('region', { header: 'Region', size: 110, filterFn: 'multiselect' }),
  col.accessor('lastActive', {
    header: 'Last Active', size: 120,
    cell: (i) => <span className="text-[11px] text-[var(--text-3)]">{formatRelative(i.getValue())}</span>,
  }),
]

const FILTER_DEFS: FilterDef[] = [
  { id: 'status',   label: 'Status',   type: 'multiselect', options: Object.keys(STATUS_CFG).map((v) => ({ value: v, label: v.replace('_',' '), color: STATUS_CFG[v].color })) },
  { id: 'role',     label: 'Role',     type: 'multiselect', options: Object.keys(ROLE_CFG).map((v) => ({ value: v, label: v.replace(/_/g,' '), color: ROLE_CFG[v].color })) },
  { id: 'specialty', label: 'Specialty', type: 'multiselect', options: ['Orthopedics','Cardiology','Neurology','Oncology','Physical Therapy','Radiology','Urology','Gastroenterology'].map((v) => ({ value: v, label: v })) },
  { id: 'caseload', label: 'Caseload',  type: 'numberrange', min: 0, max: 30 },
  { id: 'agreementRate', label: 'Agreement %', type: 'numberrange', min: 0, max: 1 },
  { id: 'region',   label: 'Region',   type: 'multiselect', options: ['Northeast','Southeast','Midwest','Southwest','West','Central'].map((v) => ({ value: v, label: v })) },
]

const ROW_ACTIONS: RowAction<ReviewerRow>[] = [
  { action: 'message', label: 'Message',        icon: MessageSquare, color: '#0ea5e9' },
  { action: 'assign',  label: 'Assign Cases',   icon: UserCheck,     color: '#6366f1' },
  { action: 'certify', label: 'View Certs',     icon: Award,         color: '#f59e0b' },
  { action: 'deactivate', label: 'Deactivate',  destructive: true, condition: (r) => r.status === 'active' },
]

export function ReviewersTable() {
  const [data] = useState(() => generateReviewers(35))

  return (
    <DataTable
      tableId="reviewers"
      data={data}
      columns={COLUMNS}
      filterDefs={FILTER_DEFS}
      defaultSorting={[{ id: 'casesCompleted', desc: true }]}
      expandedRowRenderer={(row) => <ReviewerExpandedRow row={row} />}
      rowActions={ROW_ACTIONS}
      height={560}
      systemViews={[
        { name: 'Active Reviewers', isSystem: true, columnVisibility: {}, columnOrder: [], sorting: [{ id: 'caseload', desc: true }], columnFilters: [{ id: 'status', value: ['active'] }], globalFilter: '', pageSize: 20 },
        { name: 'High Performers',  isSystem: true, columnVisibility: {}, columnOrder: [], sorting: [{ id: 'agreementRate', desc: true }], columnFilters: [{ id: 'agreementRate', value: [0.9, ''] }], globalFilter: '', pageSize: 20 },
      ]}
    />
  )
}
