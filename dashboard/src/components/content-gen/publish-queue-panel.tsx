'use client'

import { useState } from 'react'
import { Trash2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { PublishItem } from '@/types/content-gen'

interface PublishQueuePanelProps {
  items: PublishItem[]
  loading?: boolean
  onRemove?: (ideaId: string, platform: string) => Promise<void>
}

export function PublishQueuePanel({ items, loading, onRemove }: PublishQueuePanelProps) {
  const [removing, setRemoving] = useState<string | null>(null)

  const handleRemove = async (ideaId: string, platform: string) => {
    if (!onRemove) return

    const key = `${ideaId}-${platform}`
    try {
      setRemoving(key)
      await onRemove(ideaId, platform)
    } finally {
      setRemoving(null)
    }
  }

  if (loading) {
    return <div className="py-8 text-center text-sm text-muted-foreground">Loading publish queue...</div>
  }

  if (!items.length) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-card/70 py-12 text-center">
        <p className="text-sm text-muted-foreground">No items in queue</p>
        <p className="mt-1 text-xs text-muted-foreground/60">
          Run a pipeline to generate content for publishing.
        </p>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card/95 shadow-sm">
      <Table>
        <TableHeader className="bg-surface-raised/60">
          <TableRow className="hover:bg-transparent">
            <TableHead>ID</TableHead>
            <TableHead>Platform</TableHead>
            <TableHead>Scheduled</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">&nbsp;</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => {
            const key = `${item.idea_id}-${item.platform}`

            return (
              <TableRow key={key}>
                <TableCell className="font-mono text-xs text-muted-foreground tabular-nums">
                  {item.idea_id.slice(0, 8)}
                </TableCell>
                <TableCell className="text-foreground/80">{item.platform}</TableCell>
                <TableCell className="text-xs text-muted-foreground tabular-nums">
                  {item.publish_datetime}
                </TableCell>
                <TableCell>
                  <Badge
                    variant={
                      item.status === 'scheduled'
                        ? 'warning'
                        : item.status === 'published'
                          ? 'success'
                          : 'outline'
                    }
                    className="rounded-md px-2 py-1 font-mono"
                  >
                    {item.status}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  {onRemove ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => void handleRemove(item.idea_id, item.platform)}
                      disabled={removing === key}
                      className="h-8 w-8 text-muted-foreground/60 hover:text-error"
                      title="Remove from queue"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  ) : null}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
