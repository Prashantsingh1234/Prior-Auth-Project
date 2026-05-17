import type { FilterFn, Table } from '@tanstack/react-table'

// ─── Module augmentation — register custom filter names ───────────────────────

declare module '@tanstack/react-table' {
  interface FilterFns {
    multiselect: FilterFn<unknown>
    daterange:   FilterFn<unknown>
    numberrange: FilterFn<unknown>
    boolean:     FilterFn<unknown>
  }
}

// ─── Custom filter functions ──────────────────────────────────────────────────

export const multiselectFilter: FilterFn<any> = (row, columnId, filterValue: string[]) => {
  if (!filterValue?.length) return true
  const val = String(row.getValue(columnId) ?? '')
  return filterValue.includes(val)
}
multiselectFilter.autoRemove = (val: string[]) => !val?.length

export const dateRangeFilter: FilterFn<any> = (row, columnId, filterValue: [string, string]) => {
  const [from, to] = filterValue ?? []
  const raw = row.getValue(columnId)
  if (!raw) return true
  const val = new Date(raw as string).getTime()
  if (from && val < new Date(from).getTime()) return false
  if (to   && val > new Date(to + 'T23:59:59').getTime()) return false
  return true
}
dateRangeFilter.autoRemove = (val: [string, string]) => !val?.[0] && !val?.[1]

export const numberRangeFilter: FilterFn<any> = (row, columnId, filterValue: [number | '', number | '']) => {
  const [min, max] = filterValue ?? []
  const val = Number(row.getValue(columnId))
  if (min !== '' && min !== undefined && val < Number(min)) return false
  if (max !== '' && max !== undefined && val > Number(max)) return false
  return true
}
numberRangeFilter.autoRemove = (val: [number | '', number | '']) => val?.[0] === '' && val?.[1] === ''

export const booleanFilter: FilterFn<any> = (row, columnId, filterValue: boolean) => {
  if (filterValue === undefined) return true
  return Boolean(row.getValue(columnId)) === filterValue
}
booleanFilter.autoRemove = (val: boolean) => val === undefined

// ─── CSV export ───────────────────────────────────────────────────────────────

export function exportTableCSV<TData>(table: Table<TData>, filename: string) {
  const SKIP_IDS = new Set(['_select', '_expand', '_actions'])

  const leafCols = table.getVisibleLeafColumns().filter((c) => !SKIP_IDS.has(c.id))

  const headerRow = leafCols.map((col) => {
    const h = col.columnDef.header
    return typeof h === 'string' ? h : col.id
  })

  const dataRows = table.getFilteredRowModel().rows.map((row) =>
    leafCols.map((col) => {
      const val = row.getValue(col.id)
      const str = val == null ? '' : String(val)
      return str.includes(',') || str.includes('"') || str.includes('\n')
        ? `"${str.replace(/"/g, '""')}"`
        : str
    })
  )

  const csv  = [headerRow.join(','), ...dataRows.map((r) => r.join(','))].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = `${filename}-${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
