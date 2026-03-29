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
    return <div className="text-muted-foreground text-sm">Loading publish queue...</div>
  }

  if (!items.length) {
    return (
      <div className="text-center py-8 text-muted-foreground text-sm">
        Publish queue is empty
      </div>
    )
  }

  return (
    <div className="border rounded-md overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-muted/50">
          <tr>
            <th className="text-left px-4 py-2 font-medium">Idea ID</th>
            <th className="text-left px-4 py-2 font-medium">Platform</th>
            <th className="text-left px-4 py-2 font-medium">Scheduled</th>
            <th className="text-left px-4 py-2 font-medium">Status</th>
            <th className="text-right px-4 py-2 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {items.map((item) => {
            const key = `${item.idea_id}-${item.platform}`
            return (
              <tr key={key} className="hover:bg-muted/30 transition-colors">
                <td className="px-4 py-2 font-mono text-xs">{item.idea_id}</td>
                <td className="px-4 py-2">{item.platform}</td>
                <td className="px-4 py-2 text-muted-foreground">{item.publish_datetime}</td>
                <td className="px-4 py-2">
                  <span
                    className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                      item.status === 'scheduled'
                        ? 'bg-blue-100 text-blue-700'
                        : item.status === 'published'
                          ? 'bg-green-100 text-green-700'
                          : 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {item.status}
                  </span>
                </td>
                <td className="px-4 py-2 text-right">
                  {onRemove && (
                    <button
                      onClick={() => handleRemove(item.idea_id, item.platform)}
                      disabled={removing === key}
                      className="text-muted-foreground hover:text-red-600 transition-colors disabled:opacity-50"
                      title="Remove from queue"
                    >
                      <Trash2 className="h-4 w-4" />
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
