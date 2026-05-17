import { useState, useMemo, useRef, useCallback } from 'react'
import {
  useReactTable, getCoreRowModel, getFilteredRowModel,
  getSortedRowModel, getPaginationRowModel, getExpandedRowModel,
  flexRender,
  type SortingState, type ColumnFiltersState, type VisibilityState,
  type ColumnOrderState, type ExpandedState, type RowSelectionState,
  type ColumnSizingState, type Row, type Table as TTable,
} from '@tanstack/react-table'
import { useVirtualizer } from '@tanstack/react-virtual'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowUpDown, ArrowUp, ArrowDown, ChevronRight, Search,
  SlidersHorizontal, Columns3, BookmarkPlus, Download,
  X, Check, ChevronLeft, ChevronRight as ChevRight,
  MoreHorizontal, Bookmark, Trash2, Eye, EyeOff, Filter,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { multiselectFilter, dateRangeFilter, numberRangeFilter, booleanFilter, exportTableCSV } from './utils'
import { useSavedViews } from './useSavedViews'
import type { DataTableProps, FilterDef, SavedView, RowAction } from './types'

// ─── Constants ────────────────────────────────────────────────────────────────

const ROW_H       = 44
const HEADER_H    = 40
const PAGE_SIZES  = [10, 20, 50, 100]

// ─── Sort icon ────────────────────────────────────────────────────────────────

function SortIcon({ sorted }: { sorted: false | 'asc' | 'desc' }) {
  if (sorted === 'asc')  return <ArrowUp   className="w-3 h-3 ml-1 text-sky-400" />
  if (sorted === 'desc') return <ArrowDown className="w-3 h-3 ml-1 text-sky-400" />
  return <ArrowUpDown className="w-3 h-3 ml-1 text-[var(--text-4)] opacity-0 group-hover:opacity-100 transition-opacity" />
}

// ─── Checkbox cell ────────────────────────────────────────────────────────────

function Chk({ checked, indeterminate, onChange }: {
  checked: boolean; indeterminate?: boolean; onChange: (v: boolean) => void
}) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={cn(
        'w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 transition-all',
        checked || indeterminate
          ? 'bg-sky-500 border-sky-500'
          : 'border-[var(--border)] hover:border-sky-400',
      )}
    >
      {indeterminate
        ? <div className="w-2 h-0.5 bg-white rounded" />
        : checked ? <Check className="w-2.5 h-2.5 text-white" strokeWidth={3} /> : null
      }
    </button>
  )
}

// ─── Row actions dropdown ─────────────────────────────────────────────────────

function RowActionsCell<TData>({
  row, actions, onAction,
}: { row: TData; actions: RowAction<TData>[]; onAction?: (a: string, r: TData) => void }) {
  const [open, setOpen] = useState(false)
  const visible = actions.filter((a) => !a.condition || a.condition(row))
  if (!visible.length) return null

  return (
    <div className="relative">
      <button
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v) }}
        className="w-7 h-7 flex items-center justify-center rounded-lg text-[var(--text-4)] hover:bg-[var(--elevated)] hover:text-[var(--text-2)] transition-colors"
      >
        <MoreHorizontal className="w-3.5 h-3.5" />
      </button>
      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -4 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: -4 }}
              className="absolute right-0 top-8 z-50 min-w-[140px] rounded-xl py-1 shadow-xl"
              style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
            >
              {visible.map((a) => {
                const Icon = a.icon
                return (
                  <button
                    key={a.action}
                    onClick={() => { onAction?.(a.action, row); setOpen(false) }}
                    className={cn(
                      'w-full flex items-center gap-2 px-3 py-2 text-[11px] font-medium transition-colors',
                      a.destructive
                        ? 'text-red-400 hover:bg-red-500/10'
                        : 'text-[var(--text-2)] hover:bg-[var(--surface)]',
                    )}
                  >
                    {Icon && <Icon className="w-3.5 h-3.5 flex-shrink-0" style={a.color ? { color: a.color } : {}} />}
                    {a.label}
                  </button>
                )
              })}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}

// ─── Active filter chips ──────────────────────────────────────────────────────

function FilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      className="flex items-center gap-1 pl-2 pr-1 py-0.5 rounded-full text-[10px] font-medium"
      style={{ background: '#6366f118', border: '1px solid #6366f130', color: '#6366f1' }}
    >
      {label}
      <button onClick={onRemove} className="w-4 h-4 flex items-center justify-center rounded-full hover:bg-[#6366f130]">
        <X className="w-2.5 h-2.5" />
      </button>
    </motion.div>
  )
}

// ─── Advanced filter panel ────────────────────────────────────────────────────

function FilterPanel({ filterDefs, columnFilters, onFilterChange, onClearAll }: {
  filterDefs: FilterDef[]
  columnFilters: ColumnFiltersState
  onFilterChange: (id: string, value: unknown) => void
  onClearAll: () => void
}) {
  const getVal = (id: string) => columnFilters.find((f) => f.id === id)?.value

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="overflow-hidden border-b"
      style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}
    >
      <div className="px-3 sm:px-4 py-3 flex flex-wrap gap-2 sm:gap-3 items-end">
        {filterDefs.map((def) => (
          <FilterControl key={def.id} def={def} value={getVal(def.id)} onChange={(v) => onFilterChange(def.id, v)} />
        ))}
        <button
          onClick={onClearAll}
          className="text-[10px] text-[var(--text-4)] hover:text-red-400 transition-colors flex items-center gap-1 mb-0.5"
        >
          <X className="w-3 h-3" />Clear all
        </button>
      </div>
    </motion.div>
  )
}

function FilterControl({ def, value, onChange }: { def: FilterDef; value: unknown; onChange: (v: unknown) => void }) {
  if (def.type === 'text' || def.type === 'select') {
    return (
      <div className="flex flex-col gap-1">
        <label className="text-[9px] uppercase tracking-wide text-[var(--text-4)]">{def.label}</label>
        {def.type === 'select' && def.options ? (
          <select
            value={String(value ?? '')}
            onChange={(e) => onChange(e.target.value || undefined)}
            className="h-7 px-2 text-xs rounded-lg bg-[var(--elevated)] border border-[var(--border)] text-[var(--text-2)] focus:outline-none focus:border-sky-500 min-w-[120px]"
          >
            <option value="">All</option>
            {def.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        ) : (
          <input
            type="text"
            value={String(value ?? '')}
            placeholder={def.placeholder ?? def.label}
            onChange={(e) => onChange(e.target.value || undefined)}
            className="h-7 px-2 text-xs rounded-lg bg-[var(--elevated)] border border-[var(--border)] text-[var(--text-2)] focus:outline-none focus:border-sky-500 min-w-[140px]"
          />
        )}
      </div>
    )
  }

  if (def.type === 'multiselect' && def.options) {
    const selected = (value as string[] | undefined) ?? []
    return (
      <div className="flex flex-col gap-1">
        <label className="text-[9px] uppercase tracking-wide text-[var(--text-4)]">{def.label}</label>
        <MultiSelectDropdown
          options={def.options}
          selected={selected}
          onChange={(vals) => onChange(vals.length ? vals : undefined)}
        />
      </div>
    )
  }

  if (def.type === 'daterange') {
    const [from, to] = (value as [string, string] | undefined) ?? ['', '']
    return (
      <div className="flex flex-col gap-1">
        <label className="text-[9px] uppercase tracking-wide text-[var(--text-4)]">{def.label}</label>
        <div className="flex items-center gap-1">
          <input type="date" value={from}
            onChange={(e) => onChange([e.target.value, to])}
            className="h-7 px-2 text-xs rounded-lg bg-[var(--elevated)] border border-[var(--border)] text-[var(--text-2)] focus:outline-none focus:border-sky-500" />
          <span className="text-[10px] text-[var(--text-4)]">–</span>
          <input type="date" value={to}
            onChange={(e) => onChange([from, e.target.value])}
            className="h-7 px-2 text-xs rounded-lg bg-[var(--elevated)] border border-[var(--border)] text-[var(--text-2)] focus:outline-none focus:border-sky-500" />
        </div>
      </div>
    )
  }

  if (def.type === 'numberrange') {
    const [min, max] = (value as [number | '', number | ''] | undefined) ?? ['', '']
    return (
      <div className="flex flex-col gap-1">
        <label className="text-[9px] uppercase tracking-wide text-[var(--text-4)]">{def.label}</label>
        <div className="flex items-center gap-1">
          <input type="number" value={String(min)} placeholder="Min"
            onChange={(e) => onChange([e.target.value === '' ? '' : Number(e.target.value), max])}
            className="h-7 px-2 text-xs rounded-lg bg-[var(--elevated)] border border-[var(--border)] text-[var(--text-2)] focus:outline-none focus:border-sky-500 w-20" />
          <span className="text-[10px] text-[var(--text-4)]">–</span>
          <input type="number" value={String(max)} placeholder="Max"
            onChange={(e) => onChange([min, e.target.value === '' ? '' : Number(e.target.value)])}
            className="h-7 px-2 text-xs rounded-lg bg-[var(--elevated)] border border-[var(--border)] text-[var(--text-2)] focus:outline-none focus:border-sky-500 w-20" />
        </div>
      </div>
    )
  }

  if (def.type === 'boolean') {
    return (
      <div className="flex flex-col gap-1">
        <label className="text-[9px] uppercase tracking-wide text-[var(--text-4)]">{def.label}</label>
        <div className="flex items-center gap-2 h-7">
          {['All', 'Yes', 'No'].map((opt) => (
            <button key={opt}
              onClick={() => onChange(opt === 'All' ? undefined : opt === 'Yes')}
              className={cn('px-2.5 py-1 rounded-lg text-[10px] font-medium transition-colors',
                (opt === 'All' && value === undefined) || (opt === 'Yes' && value === true) || (opt === 'No' && value === false)
                  ? 'bg-sky-500/20 text-sky-400'
                  : 'text-[var(--text-3)] hover:bg-[var(--elevated)]')}
            >
              {opt}
            </button>
          ))}
        </div>
      </div>
    )
  }

  return null
}

function MultiSelectDropdown({ options, selected, onChange }: {
  options: { value: string; label: string; color?: string }[]
  selected: string[]
  onChange: (v: string[]) => void
}) {
  const [open, setOpen] = useState(false)
  const label = selected.length === 0 ? 'All' : selected.length === 1
    ? (options.find((o) => o.value === selected[0])?.label ?? selected[0])
    : `${selected.length} selected`

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="h-7 px-2 text-xs rounded-lg bg-[var(--elevated)] border border-[var(--border)] text-[var(--text-2)] flex items-center gap-1.5 min-w-[130px] hover:border-sky-500 transition-colors"
      >
        <span className="flex-1 text-left">{label}</span>
        <ChevRight className={cn('w-3 h-3 transition-transform flex-shrink-0', open && 'rotate-90')} />
      </button>
      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="absolute left-0 top-8 z-50 min-w-[160px] rounded-xl py-1 shadow-xl max-h-48 overflow-y-auto"
              style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
            >
              {options.map((opt) => {
                const isChecked = selected.includes(opt.value)
                return (
                  <button
                    key={opt.value}
                    onClick={() => {
                      const next = isChecked ? selected.filter((v) => v !== opt.value) : [...selected, opt.value]
                      onChange(next)
                    }}
                    className="w-full flex items-center gap-2 px-3 py-1.5 text-[11px] hover:bg-[var(--surface)] transition-colors"
                  >
                    <div className={cn('w-3.5 h-3.5 rounded border-2 flex items-center justify-center flex-shrink-0',
                      isChecked ? 'bg-sky-500 border-sky-500' : 'border-[var(--border)]')}>
                      {isChecked && <Check className="w-2 h-2 text-white" strokeWidth={3} />}
                    </div>
                    {opt.color && <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: opt.color }} />}
                    <span className="text-[var(--text-2)]">{opt.label}</span>
                  </button>
                )
              })}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}

// ─── Column configuration panel ───────────────────────────────────────────────

function ColumnConfigPanel<TData>({
  table, onClose,
}: { table: TTable<TData>; onClose: () => void }) {
  const cols = table.getAllLeafColumns().filter((c) => c.columnDef.enableHiding !== false)

  return (
    <motion.div
      initial={{ opacity: 0, x: 8 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 8 }}
      className="absolute right-0 top-9 z-50 w-56 rounded-xl py-2 shadow-xl"
      style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center justify-between px-3 pb-2 border-b border-[var(--border)]">
        <span className="text-[10px] font-bold uppercase tracking-wide text-[var(--text-4)]">Columns</span>
        <button onClick={() => table.resetColumnVisibility()}
                className="text-[9px] text-sky-400 hover:underline">Reset</button>
      </div>
      <div className="max-h-64 overflow-y-auto">
        {cols.map((col) => {
          const label = typeof col.columnDef.header === 'string' ? col.columnDef.header : col.id
          return (
            <button key={col.id}
              onClick={() => col.toggleVisibility()}
              className="w-full flex items-center gap-2 px-3 py-2 text-[11px] hover:bg-[var(--surface)] transition-colors"
            >
              {col.getIsVisible()
                ? <Eye    className="w-3.5 h-3.5 text-sky-400 flex-shrink-0" />
                : <EyeOff className="w-3.5 h-3.5 text-[var(--text-4)] flex-shrink-0" />}
              <span className={cn('flex-1 text-left', col.getIsVisible() ? 'text-[var(--text-2)]' : 'text-[var(--text-4)]')}>
                {label}
              </span>
            </button>
          )
        })}
      </div>
      <div className="px-3 pt-2 border-t border-[var(--border)]">
        <button onClick={onClose} className="w-full py-1 text-[10px] text-[var(--text-4)] hover:text-[var(--text-2)] transition-colors">
          Close
        </button>
      </div>
    </motion.div>
  )
}

// ─── Saved views panel ────────────────────────────────────────────────────────

function SavedViewsPanel({ views, onApply, onSave, onDelete, onClose, currentName }: {
  views: SavedView[]
  onApply:  (v: SavedView) => void
  onSave:   (name: string) => void
  onDelete: (id: string) => void
  onClose:  () => void
  currentName?: string
}) {
  const [newName, setNewName] = useState('')

  return (
    <motion.div
      initial={{ opacity: 0, x: 8 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 8 }}
      className="absolute right-0 top-9 z-50 w-64 rounded-xl py-2 shadow-xl"
      style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
    >
      <div className="px-3 pb-2 border-b border-[var(--border)]">
        <span className="text-[10px] font-bold uppercase tracking-wide text-[var(--text-4)]">Saved Views</span>
      </div>
      <div className="max-h-52 overflow-y-auto">
        {views.length === 0 && (
          <p className="text-[10px] text-[var(--text-4)] text-center py-4">No saved views yet</p>
        )}
        {views.map((v) => (
          <div key={v.id}
            className={cn('flex items-center gap-2 px-3 py-2 hover:bg-[var(--surface)] transition-colors',
              currentName === v.name && 'bg-sky-500/10')}
          >
            <button className="flex-1 flex items-center gap-2 text-left" onClick={() => onApply(v)}>
              <Bookmark className={cn('w-3 h-3 flex-shrink-0', v.isSystem ? 'text-amber-400' : 'text-sky-400')} />
              <span className="text-[11px] text-[var(--text-2)] truncate">{v.name}</span>
            </button>
            {!v.isSystem && (
              <button onClick={() => onDelete(v.id)}
                      className="text-[var(--text-4)] hover:text-red-400 transition-colors p-0.5">
                <Trash2 className="w-3 h-3" />
              </button>
            )}
          </div>
        ))}
      </div>
      <div className="px-3 pt-2 border-t border-[var(--border)] space-y-2">
        <div className="flex gap-1">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && newName.trim()) { onSave(newName.trim()); setNewName('') } }}
            placeholder="View name…"
            className="flex-1 h-7 px-2 text-xs rounded-lg bg-[var(--surface)] border border-[var(--border)] text-[var(--text-2)] focus:outline-none focus:border-sky-500"
          />
          <button
            onClick={() => { if (newName.trim()) { onSave(newName.trim()); setNewName('') } }}
            disabled={!newName.trim()}
            className="h-7 px-2 rounded-lg text-[10px] bg-sky-500/20 text-sky-400 disabled:opacity-40 hover:bg-sky-500/30 transition-colors"
          >
            Save
          </button>
        </div>
        <button onClick={onClose} className="w-full py-1 text-[10px] text-[var(--text-4)] hover:text-[var(--text-2)] transition-colors">
          Close
        </button>
      </div>
    </motion.div>
  )
}

// ─── Pagination bar ───────────────────────────────────────────────────────────

function PaginationBar<TData>({ table, total }: { table: TTable<TData>; total: number }) {
  const { pageIndex, pageSize } = table.getState().pagination
  const start = pageIndex * pageSize + 1
  const end   = Math.min(start + pageSize - 1, total)

  return (
    <div className="flex items-center justify-between px-3 sm:px-4 py-2 border-t flex-shrink-0 gap-2"
         style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>

      {/* Rows per page — hidden on mobile */}
      <div className="hidden sm:flex items-center gap-2">
        <span className="text-[10px] text-[var(--text-4)]">Rows:</span>
        {PAGE_SIZES.map((s) => (
          <button key={s}
            onClick={() => table.setPageSize(s)}
            className={cn('w-8 h-6 text-[10px] rounded transition-colors',
              pageSize === s ? 'bg-sky-500/20 text-sky-400 font-semibold' : 'text-[var(--text-4)] hover:bg-[var(--elevated)]')}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Row count — always visible */}
      <span className="text-[10px] text-[var(--text-4)] sm:hidden">
        {total.toLocaleString()} rows
      </span>

      <div className="flex items-center gap-2 sm:gap-3">
        <span className="text-[10px] text-[var(--text-4)]">
          {start}–{end} / {total.toLocaleString()}
        </span>
        <div className="flex items-center gap-0.5 sm:gap-1">
          <button onClick={() => table.firstPage()} disabled={!table.getCanPreviousPage()}
                  className="w-7 h-7 sm:w-6 sm:h-6 flex items-center justify-center rounded text-[var(--text-4)] disabled:opacity-30 hover:bg-[var(--elevated)] transition-colors">
            <ChevronLeft className="w-3.5 h-3.5 sm:w-3 sm:h-3" />
          </button>
          {Array.from({ length: Math.min(5, table.getPageCount()) }, (_, i) => {
            const page = Math.max(0, Math.min(
              pageIndex - 2 + i,
              table.getPageCount() - 5 + i,
            ))
            return (
              <button key={page} onClick={() => table.setPageIndex(page)}
                      className={cn('w-7 h-7 sm:w-6 sm:h-6 text-[10px] rounded transition-colors',
                        page === pageIndex ? 'bg-sky-500/20 text-sky-400 font-semibold' : 'text-[var(--text-4)] hover:bg-[var(--elevated)]')}>
                {page + 1}
              </button>
            )
          })}
          <button onClick={() => table.lastPage()} disabled={!table.getCanNextPage()}
                  className="w-7 h-7 sm:w-6 sm:h-6 flex items-center justify-center rounded text-[var(--text-4)] disabled:opacity-30 hover:bg-[var(--elevated)] transition-colors">
            <ChevRight className="w-3.5 h-3.5 sm:w-3 sm:h-3" />
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Main DataTable component ─────────────────────────────────────────────────

export function DataTable<TData>({
  tableId,
  data,
  columns,
  filterDefs = [],
  defaultColumnVisibility = {},
  defaultSorting = [],
  expandedRowRenderer,
  rowActions = [],
  onRowAction,
  loading = false,
  height = 520,
  enableSelection = true,
  systemViews = [],
}: DataTableProps<TData>) {

  // ── Table state
  const [sorting,         setSorting]         = useState<SortingState>(defaultSorting)
  const [columnFilters,   setColumnFilters]   = useState<ColumnFiltersState>([])
  const [globalFilter,    setGlobalFilter]    = useState('')
  const [colVis,          setColVis]          = useState<VisibilityState>(defaultColumnVisibility)
  const [columnOrder,     setColumnOrder]     = useState<ColumnOrderState>([])
  const [columnSizing,    setColumnSizing]    = useState<ColumnSizingState>({})
  const [expanded,        setExpanded]        = useState<ExpandedState>({})
  const [rowSelection,    setRowSelection]    = useState<RowSelectionState>({})
  const [pagination,      setPagination]      = useState({ pageIndex: 0, pageSize: 20 })

  // ── UI state
  const [showFilters,    setShowFilters]    = useState(false)
  const [showColConfig,  setShowColConfig]  = useState(false)
  const [showViews,      setShowViews]      = useState(false)
  const [activeViewName, setActiveViewName] = useState<string | undefined>()
  const [searchInput,    setSearchInput]    = useState('')

  const containerRef = useRef<HTMLDivElement>(null)
  const { views, save: saveView, remove: removeView } = useSavedViews(tableId, systemViews)

  // ── Debounce global filter
  const searchTimer = useRef<ReturnType<typeof setTimeout>>()
  const handleSearch = (v: string) => {
    setSearchInput(v)
    clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => { setGlobalFilter(v); setPagination((p) => ({ ...p, pageIndex: 0 })) }, 200)
  }

  // ── Column definitions with built-in select/expand/actions
  const allColumns = useMemo(() => {
    type ColDef = typeof columns[number]
    const cols: ColDef[] = []

    if (enableSelection) {
      cols.push({
        id: '_select',
        header: ({ table: t }: { table: TTable<TData> }) => (
          <Chk
            checked={t.getIsAllPageRowsSelected()}
            indeterminate={t.getIsSomePageRowsSelected()}
            onChange={(v) => t.toggleAllPageRowsSelected(v)}
          />
        ),
        cell: ({ row }: { row: Row<TData> }) => (
          <Chk checked={row.getIsSelected()} onChange={(v) => row.toggleSelected(v)} />
        ),
        size: 44, minSize: 44, maxSize: 44,
        enableSorting: false, enableHiding: false, enableResizing: false,
      } as ColDef)
    }

    if (expandedRowRenderer) {
      cols.push({
        id: '_expand',
        header: () => null,
        cell: ({ row }: { row: Row<TData> }) => (
          <button onClick={(e) => { e.stopPropagation(); row.toggleExpanded() }}
                  className="w-6 h-6 flex items-center justify-center rounded text-[var(--text-4)] hover:text-[var(--text-2)] hover:bg-[var(--elevated)] transition-all">
            <ChevronRight className={cn('w-3 h-3 transition-transform', row.getIsExpanded() && 'rotate-90')} />
          </button>
        ),
        size: 36, minSize: 36, maxSize: 36,
        enableSorting: false, enableHiding: false, enableResizing: false,
      } as ColDef)
    }

    cols.push(...columns)

    if (rowActions.length > 0) {
      cols.push({
        id: '_actions',
        header: '',
        cell: ({ row }: { row: Row<TData> }) => (
          <RowActionsCell row={row.original} actions={rowActions} onAction={onRowAction} />
        ),
        size: 52, minSize: 52, maxSize: 52,
        enableSorting: false, enableHiding: false, enableResizing: false,
      } as ColDef)
    }

    return cols
  }, [columns, enableSelection, expandedRowRenderer, rowActions, onRowAction])

  // ── Table instance
  const table = useReactTable<TData>({
    data,
    columns: allColumns,
    state: {
      sorting, columnFilters, globalFilter, columnVisibility: colVis,
      columnOrder, columnSizing, expanded, rowSelection, pagination,
    },
    onSortingChange:         setSorting,
    onColumnFiltersChange:   (u) => { setColumnFilters(u); setPagination((p) => ({ ...p, pageIndex: 0 })) },
    onGlobalFilterChange:    setGlobalFilter,
    onColumnVisibilityChange: setColVis,
    onColumnOrderChange:     setColumnOrder,
    onColumnSizingChange:    setColumnSizing,
    onExpandedChange:        setExpanded,
    onRowSelectionChange:    setRowSelection,
    onPaginationChange:      setPagination,
    getCoreRowModel:         getCoreRowModel(),
    getFilteredRowModel:     getFilteredRowModel(),
    getSortedRowModel:       getSortedRowModel(),
    getPaginationRowModel:   getPaginationRowModel(),
    getExpandedRowModel:     getExpandedRowModel(),
    columnResizeMode:        'onChange',
    filterFns: { multiselect: multiselectFilter, daterange: dateRangeFilter, numberrange: numberRangeFilter, boolean: booleanFilter },
    globalFilterFn:          'includesString',
    autoResetPageIndex:      false,
  })

  // ── Virtualization (applied to current page rows)
  const { rows } = table.getRowModel()
  const rowVirtualizer = useVirtualizer({
    count:           rows.length,
    getScrollElement: () => containerRef.current,
    estimateSize:    () => ROW_H,
    overscan:        8,
    measureElement:  (el) => el?.getBoundingClientRect().height ?? ROW_H,
  })

  // ── Active filter chips
  const activeFilters = columnFilters.map((f) => {
    const def = filterDefs.find((d) => d.id === f.id)
    if (!def) return null
    let valueLabel = ''
    if (def.type === 'multiselect') {
      const vals = f.value as string[]
      valueLabel = vals.map((v) => def.options?.find((o) => o.value === v)?.label ?? v).join(', ')
    } else if (def.type === 'daterange') {
      const [from, to] = f.value as [string, string]
      valueLabel = `${from || '…'} – ${to || '…'}`
    } else if (def.type === 'numberrange') {
      const [min, max] = f.value as [number | '', number | '']
      valueLabel = `${min ?? '…'} – ${max ?? '…'}`
    } else {
      valueLabel = String(f.value)
    }
    return { id: f.id, label: `${def.label}: ${valueLabel}` }
  }).filter(Boolean) as Array<{ id: string; label: string }>

  // ── Saved view apply
  const applyView = useCallback((view: SavedView) => {
    setColVis(view.columnVisibility)
    setColumnOrder(view.columnOrder)
    setSorting(view.sorting)
    setColumnFilters(view.columnFilters)
    setGlobalFilter(view.globalFilter)
    setSearchInput(view.globalFilter)
    setPagination((p) => ({ ...p, pageSize: view.pageSize, pageIndex: 0 }))
    setActiveViewName(view.name)
    setShowViews(false)
  }, [])

  const handleSaveView = useCallback((name: string) => {
    saveView(name, {
      columnVisibility: colVis,
      columnOrder,
      sorting,
      columnFilters,
      globalFilter,
      pageSize: pagination.pageSize,
    })
    setActiveViewName(name)
    setShowViews(false)
  }, [saveView, colVis, columnOrder, sorting, columnFilters, globalFilter, pagination.pageSize])

  // ── Column filter helper
  const setFilter = (id: string, value: unknown) => {
    if (value === undefined || value === '' || (Array.isArray(value) && !value.length)) {
      setColumnFilters((f) => f.filter((x) => x.id !== id))
    } else {
      setColumnFilters((f) => {
        const existing = f.findIndex((x) => x.id === id)
        if (existing >= 0) return f.map((x, i) => i === existing ? { id, value } : x)
        return [...f, { id, value }]
      })
    }
    setPagination((p) => ({ ...p, pageIndex: 0 }))
  }

  const selectedCount = Object.values(rowSelection).filter(Boolean).length
  const totalFiltered = table.getFilteredRowModel().rows.length

  // ── Column total width
  const totalWidth = table.getTotalSize()

  return (
    <div className="flex flex-col h-full min-h-0 rounded-xl overflow-hidden"
         style={{ border: '1px solid var(--border)', background: 'var(--surface)' }}>

      {/* ── Toolbar ─────────────────────────────────────────────────────── */}
      <div className="border-b flex-shrink-0" style={{ borderColor: 'var(--border)', background: 'var(--elevated)' }}>

        {/* Row 1: search + actions */}
        <div className="flex items-center gap-2 px-3 py-2">

          {/* Search */}
          <div className="relative flex-1 min-w-0 max-w-xs">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-4)]" />
            <input
              value={searchInput}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder="Search…"
              className="w-full h-8 sm:h-7 pl-8 pr-3 text-xs rounded-lg bg-[var(--surface)] border border-[var(--border)] text-[var(--text-2)] focus:outline-none focus:border-sky-500 transition-colors"
            />
            {searchInput && (
              <button onClick={() => { handleSearch(''); setGlobalFilter('') }}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-4)] hover:text-[var(--text-2)]">
                <X className="w-3 h-3" />
              </button>
            )}
          </div>

          {/* Active filter chips — desktop only */}
          <div className="hidden sm:flex items-center gap-1 flex-1 flex-wrap">
            <AnimatePresence>
              {activeFilters.map((f) => (
                <FilterChip key={f.id} label={f.label} onRemove={() => setFilter(f.id, undefined)} />
              ))}
            </AnimatePresence>
          </div>

          {/* Selection info */}
          {selectedCount > 0 && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-sky-500/15 text-sky-400 font-semibold whitespace-nowrap">
              {selectedCount} sel.
            </span>
          )}

          <span className="text-[10px] text-[var(--text-4)] whitespace-nowrap hidden sm:inline">
            {totalFiltered.toLocaleString()} rows
          </span>

          {/* Filter toggle */}
          {filterDefs.length > 0 && (
            <button
              onClick={() => setShowFilters((v) => !v)}
              className={cn('flex items-center gap-1 sm:gap-1.5 h-8 sm:h-7 px-2 sm:px-2.5 rounded-lg text-[10px] font-medium transition-colors',
                showFilters || activeFilters.length > 0
                  ? 'bg-indigo-500/15 text-indigo-400'
                  : 'text-[var(--text-3)] hover:bg-[var(--surface)]')}
            >
              <SlidersHorizontal className="w-3 h-3" />
              <span className="hidden sm:inline">Filters</span>
              {activeFilters.length > 0 && (
                <span className="w-4 h-4 rounded-full bg-indigo-500 text-white text-[9px] font-bold flex items-center justify-center">
                  {activeFilters.length}
                </span>
              )}
            </button>
          )}

          {/* Column config */}
          <div className="relative">
            <button
              onClick={() => { setShowColConfig((v) => !v); setShowViews(false) }}
              className={cn('flex items-center gap-1.5 h-8 sm:h-7 px-2 sm:px-2.5 rounded-lg text-[10px] font-medium transition-colors',
                showColConfig ? 'bg-[var(--surface)] text-[var(--text-1)]' : 'text-[var(--text-3)] hover:bg-[var(--surface)]')}
            >
              <Columns3 className="w-3 h-3" />
            </button>
            <AnimatePresence>
              {showColConfig && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowColConfig(false)} />
                  <div className="relative z-50">
                    <ColumnConfigPanel table={table} onClose={() => setShowColConfig(false)} />
                  </div>
                </>
              )}
            </AnimatePresence>
          </div>

          {/* Saved views */}
          <div className="relative">
            <button
              onClick={() => { setShowViews((v) => !v); setShowColConfig(false) }}
              className={cn('flex items-center gap-1.5 h-8 sm:h-7 px-2 sm:px-2.5 rounded-lg text-[10px] font-medium transition-colors',
                showViews ? 'bg-[var(--surface)] text-[var(--text-1)]' : 'text-[var(--text-3)] hover:bg-[var(--surface)]')}
            >
              <BookmarkPlus className="w-3 h-3" />
              {activeViewName && <span className="text-sky-400 hidden sm:inline">{activeViewName}</span>}
            </button>
            <AnimatePresence>
              {showViews && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowViews(false)} />
                  <div className="relative z-50">
                    <SavedViewsPanel
                      views={views}
                      onApply={applyView}
                      onSave={handleSaveView}
                      onDelete={removeView}
                      onClose={() => setShowViews(false)}
                      currentName={activeViewName}
                    />
                  </div>
                </>
              )}
            </AnimatePresence>
          </div>

          {/* CSV export */}
          <button
            onClick={() => exportTableCSV(table, tableId)}
            className="flex items-center gap-1.5 h-8 sm:h-7 px-2 sm:px-2.5 rounded-lg text-[10px] font-medium text-[var(--text-3)] hover:bg-[var(--surface)] hover:text-emerald-400 transition-colors"
            title="Export filtered rows to CSV"
          >
            <Download className="w-3 h-3" />
          </button>
        </div>

        {/* Row 2: active filter chips on mobile */}
        {activeFilters.length > 0 && (
          <div className="flex items-center gap-1 px-3 pb-2 flex-wrap sm:hidden">
            <AnimatePresence>
              {activeFilters.map((f) => (
                <FilterChip key={f.id} label={f.label} onRemove={() => setFilter(f.id, undefined)} />
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>

      {/* ── Filter panel ─────────────────────────────────────────────────── */}
      <AnimatePresence>
        {showFilters && filterDefs.length > 0 && (
          <FilterPanel
            filterDefs={filterDefs}
            columnFilters={columnFilters}
            onFilterChange={setFilter}
            onClearAll={() => { setColumnFilters([]); setPagination((p) => ({ ...p, pageIndex: 0 })) }}
          />
        )}
      </AnimatePresence>

      {/* ── Table ────────────────────────────────────────────────────────── */}
      <div
        ref={containerRef}
        style={{ height: `${height}px`, overflow: 'auto', position: 'relative', touchAction: 'pan-y pan-x', WebkitOverflowScrolling: 'touch' } as React.CSSProperties}
        className="flex-shrink-0"
      >
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-[var(--surface)]/80 backdrop-blur-sm">
            <motion.div className="w-6 h-6 rounded-full border-2 border-sky-500 border-t-transparent"
                        animate={{ rotate: 360 }} transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }} />
          </div>
        )}

        <table style={{ display: 'grid', minWidth: `${totalWidth}px`, width: '100%' }}>

          {/* Sticky header */}
          <thead style={{ display: 'grid', position: 'sticky', top: 0, zIndex: 4, background: 'var(--elevated)' }}>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} style={{ display: 'flex', width: '100%' }}>
                {hg.headers.map((header) => (
                  <th
                    key={header.id}
                    style={{
                      display: 'flex', alignItems: 'center',
                      width: header.getSize(),
                      height: HEADER_H,
                      padding: '0 10px',
                      position: 'relative',
                      overflow: 'hidden',
                      userSelect: 'none',
                      borderRight:  '1px solid var(--border)',
                      borderBottom: '2px solid var(--border)',
                      background:   'var(--elevated)',
                    }}
                    className="group"
                  >
                    {header.isPlaceholder ? null : (
                      <div
                        className={cn('flex items-center gap-0 flex-1 min-w-0 text-[10px] font-bold uppercase tracking-wide text-[var(--text-3)]',
                          header.column.getCanSort() && 'cursor-pointer hover:text-[var(--text-1)]')}
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        <span className="truncate">
                          {flexRender(header.column.columnDef.header, header.getContext())}
                        </span>
                        <SortIcon sorted={header.column.getIsSorted()} />
                      </div>
                    )}
                    {/* Resize handle */}
                    {header.column.getCanResize() && (
                      <div
                        onMouseDown={header.getResizeHandler()}
                        onTouchStart={header.getResizeHandler()}
                        style={{
                          position: 'absolute', right: 0, top: 0,
                          height: '100%', width: 4, cursor: 'col-resize',
                          background: header.column.getIsResizing() ? '#0ea5e9' : 'transparent',
                        }}
                        className="hover:!bg-sky-500/40"
                        onClick={(e) => e.stopPropagation()}
                      />
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>

          {/* Virtualized body */}
          <tbody style={{ display: 'grid', position: 'relative', height: `${rowVirtualizer.getTotalSize()}px` }}>
            {rows.length === 0 && !loading && (
              <tr style={{ display: 'flex', position: 'absolute', width: '100%', top: 0 }}>
                <td style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', height: 200 }}>
                  <div className="flex flex-col items-center gap-2">
                    <Filter className="w-8 h-8 text-[var(--text-4)]" />
                    <p className="text-xs text-[var(--text-4)]">No rows match the current filters</p>
                  </div>
                </td>
              </tr>
            )}
            {rowVirtualizer.getVirtualItems().map((vr) => {
              const row = rows[vr.index]
              return (
                <tr
                  key={row.id}
                  data-index={vr.index}
                  ref={rowVirtualizer.measureElement}
                  style={{
                    display: 'flex', flexDirection: 'column',
                    position: 'absolute', transform: `translateY(${vr.start}px)`,
                    width: '100%',
                    background: row.getIsSelected() ? 'rgba(14,165,233,0.06)' : vr.index % 2 === 0 ? 'var(--surface)' : 'var(--elevated)',
                  }}
                  className="group/row hover:!bg-sky-500/[0.04] transition-colors"
                >
                  {/* Data cells */}
                  <div style={{ display: 'flex', minHeight: ROW_H, width: '100%' }}>
                    {row.getVisibleCells().map((cell) => (
                      <td
                        key={cell.id}
                        style={{
                          display: 'flex', alignItems: 'center',
                          width:  cell.column.getSize(),
                          minHeight: ROW_H,
                          padding: '0 10px',
                          overflow: 'hidden',
                          borderRight:  '1px solid var(--border)',
                          borderBottom: '1px solid var(--border)',
                          fontSize: 12,
                          color: 'var(--text-2)',
                        }}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </div>

                  {/* Expanded content */}
                  {row.getIsExpanded() && expandedRowRenderer && (
                    <div style={{
                      width: '100%',
                      borderBottom: '2px solid var(--border)',
                      background: 'var(--surface)',
                    }}>
                      {expandedRowRenderer(row.original, row as Row<TData>)}
                    </div>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* ── Pagination ────────────────────────────────────────────────────── */}
      <PaginationBar table={table} total={totalFiltered} />
    </div>
  )
}
