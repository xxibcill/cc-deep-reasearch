'use client'

import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

export interface DataTableColumn<T> {
  id: string
  header: string
  render: (item: T) => ReactNode
  className?: string
}

export interface DataTableSelectionConfig {
  selectedIds: Set<string>
  onToggle: (id: string) => void
  onToggleAll: () => void
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[]
  data: T[]
  keyField: keyof T
  onRowClick?: (item: T, e: React.MouseEvent) => void
  selection?: DataTableSelectionConfig
  bulkActions?: ReactNode
}

export function DataTable<T>({
  columns,
  data,
  keyField,
  onRowClick,
  selection,
  bulkActions,
}: DataTableProps<T>) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card/95 shadow-sm">
      <Table>
        <TableHeader className="bg-surface-raised/60">
          <TableRow className="hover:bg-transparent">
            {selection && (
              <TableHead className="w-10">
                <input
                  type="checkbox"
                  checked={selection.selectedIds.size === data.length && data.length > 0}
                  onChange={selection.onToggleAll}
                  className="h-4 w-4 rounded border-input"
                />
              </TableHead>
            )}
            {columns.map((col) => (
              <TableHead key={col.id} className={col.className}>
                {col.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((item) => {
            const key = String(item[keyField])
            return (
              <TableRow
                key={key}
                onClick={onRowClick ? (e) => onRowClick(item, e) : undefined}
                className={cn(
                  onRowClick && 'cursor-pointer hover:bg-surface/50',
                  selection?.selectedIds.has(key) && 'bg-primary/5'
                )}
              >
                {selection && (
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selection.selectedIds.has(key)}
                      onChange={() => selection.onToggle(key)}
                      className="h-4 w-4 rounded border-input"
                    />
                  </TableCell>
                )}
                {columns.map((col) => (
                  <TableCell key={col.id} className={col.className}>
                    {col.render(item)}
                  </TableCell>
                ))}
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
      {bulkActions}
    </div>
  )
}
