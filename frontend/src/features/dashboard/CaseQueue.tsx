import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { motion } from 'framer-motion'
import {
  ArrowUpDown, ChevronLeft, ChevronRight,
  Search, Filter, Loader2,
} from 'lucide-react'
import { StatusBadge, PriorityBadge, RecommendationBadge } from '@/components/common/StatusBadge'
import { ConfidenceBar } from '@/components/common/ConfidenceBar'
import { cn, formatRelative } from '@/lib/utils'

interface CaseRow {
  id: string
  caseNumber: string
  patientName: string
  procedure: string
  cptCode: string
  status: any
  priority: any
  aiRecommendation: any
  confidence: number
  submittedAt: string
  reviewerName?: string
}

const MOCK_CASES: CaseRow[] = [
  { id: 'c1', caseNumber: 'PA-2024-001', patientName: 'Maria Gonzalez',   procedure: 'Total Knee Arthroplasty', cptCode: '27447', status: 'UNDER_REVIEW', priority: 'URGENT',   aiRecommendation: 'APPROVE',       confidence: 0.91, submittedAt: new Date(Date.now() - 3600000).toISOString() },
  { id: 'c2', caseNumber: 'PA-2024-002', patientName: 'James Wilson',     procedure: 'Lumbar Spinal Fusion',   cptCode: '22633', status: 'SUBMITTED',    priority: 'ROUTINE',  aiRecommendation: 'DENY',          confidence: 0.78, submittedAt: new Date(Date.now() - 7200000).toISOString() },
  { id: 'c3', caseNumber: 'PA-2024-003', patientName: 'Sarah Thompson',   procedure: 'Hip Replacement',        cptCode: '27130', status: 'UNDER_REVIEW', priority: 'EMERGENT', aiRecommendation: 'APPROVE',       confidence: 0.95, submittedAt: new Date(Date.now() - 1800000).toISOString() },
  { id: 'c4', caseNumber: 'PA-2024-004', patientName: 'Robert Chen',      procedure: 'MRI Brain with Contrast', cptCode: '70553', status: 'PENDING_INFO', priority: 'ROUTINE',  aiRecommendation: 'REQUEST_INFO',  confidence: 0.54, submittedAt: new Date(Date.now() - 14400000).toISOString() },
  { id: 'c5', caseNumber: 'PA-2024-005', patientName: 'Emily Rodriguez',  procedure: 'Cardiac Catheterization', cptCode: '93454', status: 'UNDER_REVIEW', priority: 'URGENT',   aiRecommendation: 'ESCALATE',      confidence: 0.62, submittedAt: new Date(Date.now() - 900000).toISOString() },
  { id: 'c6', caseNumber: 'PA-2024-006', patientName: 'David Kim',        procedure: 'Sleeve Gastrectomy',     cptCode: '43775', status: 'SUBMITTED',    priority: 'ROUTINE',  aiRecommendation: 'DENY',          confidence: 0.83, submittedAt: new Date(Date.now() - 28800000).toISOString() },
  { id: 'c7', caseNumber: 'PA-2024-007', patientName: 'Lisa Martinez',    procedure: 'Cochlear Implant',       cptCode: '69930', status: 'SUBMITTED',    priority: 'ROUTINE',  aiRecommendation: 'APPROVE',       confidence: 0.88, submittedAt: new Date(Date.now() - 21600000).toISOString() },
  { id: 'c8', caseNumber: 'PA-2024-008', patientName: 'Michael Brown',    procedure: 'Stereotactic Radiosurgery', cptCode: '61796', status: 'ESCALATED',  priority: 'EMERGENT', aiRecommendation: 'ESCALATE',      confidence: 0.71, submittedAt: new Date(Date.now() - 5400000).toISOString() },
]

export function CaseQueue() {
  const navigate = useNavigate()
  const [sorting, setSorting] = useState<SortingState>([])
  const [globalFilter, setGlobalFilter] = useState('')

  const columns = useMemo<ColumnDef<CaseRow>[]>(() => [
    {
      accessorKey: 'caseNumber',
      header: ({ column }) => (
        <button
          className="flex items-center gap-1 text-xs font-medium text-[var(--text-3)] uppercase tracking-wide hover:text-[var(--text-1)] transition-colors"
          onClick={() => column.toggleSorting()}
        >
          Case # <ArrowUpDown className="w-3 h-3" />
        </button>
      ),
      cell: ({ getValue }) => (
        <span className="mono text-xs text-brand-400">{getValue() as string}</span>
      ),
    },
    {
      accessorKey: 'patientName',
      header: () => <span className="text-xs font-medium text-[var(--text-3)] uppercase tracking-wide">Patient</span>,
      cell: ({ getValue }) => (
        <span className="text-sm text-[var(--text-1)] font-medium">{getValue() as string}</span>
      ),
    },
    {
      accessorKey: 'procedure',
      header: () => <span className="text-xs font-medium text-[var(--text-3)] uppercase tracking-wide">Procedure</span>,
      cell: ({ row }) => (
        <div>
          <p className="text-sm text-[var(--text-1)] leading-snug">{row.original.procedure}</p>
          <p className="text-xs text-[var(--text-3)] mono mt-0.5">CPT {row.original.cptCode}</p>
        </div>
      ),
    },
    {
      accessorKey: 'priority',
      header: () => <span className="text-xs font-medium text-[var(--text-3)] uppercase tracking-wide">Priority</span>,
      cell: ({ getValue }) => <PriorityBadge priority={getValue() as any} />,
    },
    {
      accessorKey: 'status',
      header: () => <span className="text-xs font-medium text-[var(--text-3)] uppercase tracking-wide">Status</span>,
      cell: ({ getValue }) => <StatusBadge status={getValue() as any} />,
    },
    {
      accessorKey: 'aiRecommendation',
      header: () => <span className="text-xs font-medium text-[var(--text-3)] uppercase tracking-wide">AI Rec.</span>,
      cell: ({ getValue }) => <RecommendationBadge recommendation={getValue() as any} />,
    },
    {
      accessorKey: 'confidence',
      header: ({ column }) => (
        <button
          className="flex items-center gap-1 text-xs font-medium text-[var(--text-3)] uppercase tracking-wide hover:text-[var(--text-1)] transition-colors"
          onClick={() => column.toggleSorting()}
        >
          Confidence <ArrowUpDown className="w-3 h-3" />
        </button>
      ),
      cell: ({ getValue }) => (
        <ConfidenceBar value={getValue() as number} size="sm" className="min-w-24" />
      ),
    },
    {
      accessorKey: 'submittedAt',
      header: () => <span className="text-xs font-medium text-[var(--text-3)] uppercase tracking-wide">Submitted</span>,
      cell: ({ getValue }) => (
        <span className="text-xs text-[var(--text-3)]">{formatRelative(getValue() as string)}</span>
      ),
    },
  ], [])

  const table = useReactTable({
    data: MOCK_CASES,
    columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 6 } },
  })

  return (
    <div className="card h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[var(--border)]">
        <div>
          <p className="text-sm font-semibold text-[var(--text-1)]">Review Queue</p>
          <p className="text-xs text-[var(--text-3)]">{table.getFilteredRowModel().rows.length} cases</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-3)]" />
            <input
              value={globalFilter}
              onChange={(e) => setGlobalFilter(e.target.value)}
              placeholder="Search cases…"
              className="input pl-8 py-1.5 text-xs w-48"
            />
          </div>
          <button className="btn btn-ghost py-1.5 px-3 text-xs gap-1.5">
            <Filter className="w-3.5 h-3.5" /> Filter
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full">
          <thead className="sticky top-0 bg-[var(--surface)] border-b border-[var(--border)]">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => (
                  <th key={header.id} className="text-left px-4 py-3 whitespace-nowrap">
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row, i) => (
              <motion.tr
                key={row.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                onClick={() => navigate(`/cases/${row.original.id}`)}
                className="border-b border-[var(--border)] cursor-pointer hover:bg-[var(--elevated)] transition-colors group"
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-4 py-3">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--border)]">
        <p className="text-xs text-[var(--text-3)]">
          Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
        </p>
        <div className="flex items-center gap-1">
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="p-1.5 rounded-md text-[var(--text-2)] hover:bg-[var(--elevated)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="p-1.5 rounded-md text-[var(--text-2)] hover:bg-[var(--elevated)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}