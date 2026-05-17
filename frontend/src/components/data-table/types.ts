import type {
  ColumnDef, SortingState, ColumnFiltersState,
  VisibilityState, ColumnOrderState, Row,
} from '@tanstack/react-table'

export type FilterType = 'text' | 'select' | 'multiselect' | 'daterange' | 'numberrange' | 'boolean'

export interface FilterOption {
  value: string
  label: string
  color?: string
}

export interface FilterDef {
  id:           string
  label:        string
  type:         FilterType
  options?:     FilterOption[]
  min?:         number
  max?:         number
  placeholder?: string
}

export interface SavedView {
  id:               string
  name:             string
  createdAt:        string
  isSystem?:        boolean
  columnVisibility: VisibilityState
  columnOrder:      ColumnOrderState
  sorting:          SortingState
  columnFilters:    ColumnFiltersState
  globalFilter:     string
  pageSize:         number
}

export interface RowAction<TData> {
  action:      string
  label:       string
  icon?:       React.ElementType
  color?:      string
  destructive?: boolean
  condition?:  (row: TData) => boolean
}

export interface DataTableProps<TData> {
  tableId:                string
  data:                   TData[]
  columns:                ColumnDef<TData, any>[]
  filterDefs?:            FilterDef[]
  defaultColumnVisibility?: VisibilityState
  defaultSorting?:        SortingState
  expandedRowRenderer?:   (row: TData, tableRow: Row<TData>) => React.ReactNode
  rowActions?:            RowAction<TData>[]
  onRowAction?:           (action: string, row: TData) => void
  loading?:               boolean
  height?:                number
  enableSelection?:       boolean
  systemViews?:           Omit<SavedView, 'id' | 'createdAt'>[]
}
