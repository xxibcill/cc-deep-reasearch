'use client'

import { useState } from 'react'
import { Trash2 } from 'lucide-react'
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
    return <div className="text-muted-foreground text-sm py-8 text-center">Loading publish queue...</div>
  }

  if (!items.length) {
    return (
      <div className="py-12 text-center">
        <p className="text-sm text-muted-foreground">No items in queue</p>
        <p className="text-xs text-muted-foreground/50 mt-1">Run a pipeline to generate content for publishing</p>
      </div>
    )
  }

  return (
    <div className="border border-border rounded-sm overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-surface-raised/50 border-b border-border">
            <th className="text-left px-4 py-2.5 text-xs font-mono uppercase tracking-wider text-muted-foreground font-medium">
              ID
            </th>
            <th className="text-left px-4 py-2.5 text-xs font-mono uppercase tracking-wider text-muted-foreground font-medium">
              Platform
            </th>
            <th className="text-left px-4 py-2.5 text-xs font-mono uppercase tracking-wider text-muted-foreground font-medium">
              Scheduled
            </th>
            <th className="text-left px-4 py-2.5 text-xs font-mono uppercase tracking-wider text-muted-foreground font-medium">
              Status
            </th>
            <th className="text-right px-4 py-2.5 text-xs font-mono uppercase tracking-wider text-muted-foreground font-medium">
              &nbsp;
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((item) => {
            const key = `${item.idea_id}-${item.platform}`
            return (
              <tr key={key} className="hover:bg-surface-raised/30 transition-colors">
                <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground tabular-nums">
                  {item.idea_id.slice(0, 8)}
                </td>
                <td className="px-4 py-2.5 text-foreground/80">{item.platform}</td>
                <td className="px-4 py-2.5 text-muted-foreground text-xs tabular-nums">
                  {item.publish_datetime}
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className={`inline-flex px-2 py-0.5 rounded-sm text-xs font-mono font-medium ${
                      item.status === 'scheduled'
                        ? 'bg-warning/10 text-warning border border-warning/20'
                        : item.status === 'published'
                          ? 'bg-success/10 text-success border border-success/20'
                          : 'bg-surface text-muted-foreground border border-border'
                    }`}
                  >
                    {item.status}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-right">
                  {onRemove && (
                    <button
                      onClick={() => handleRemove(item.idea_id, item.platform)}
                      disabled={removing === key}
                      className="text-muted-foreground/50 hover:text-error transition-colors disabled:opacity-30"
                      title="Remove from queue"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
