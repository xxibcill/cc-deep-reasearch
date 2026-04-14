'use client'

import Link from 'next/link'
import { Archive, CheckCircle2, Play, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { BacklogItemForm } from '@/components/content-gen/backlog-item-form'
import { backlogTitle } from '@/components/content-gen/backlog-shared'
import type { BacklogItem } from '@/types/content-gen'

interface BacklogDetailToolbarProps {
  item: BacklogItem
  busy: boolean
  updateBacklogItem: (id: string, fields: Record<string, unknown>) => Promise<void>
  selectBacklogItem: ((id: string) => Promise<void>) | null | undefined
  startBacklogItem: ((id: string) => Promise<string | null>) | null | undefined
  archiveBacklogItem: ((id: string) => Promise<void>) | null | undefined
  onDelete: () => void
}

export function BacklogDetailToolbar({
  item,
  busy,
  updateBacklogItem,
  selectBacklogItem,
  startBacklogItem,
  archiveBacklogItem,
  onDelete,
}: BacklogDetailToolbarProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-[1.15rem] border border-border/75 bg-surface/92 px-4 py-3 backdrop-blur-sm">
      <nav className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Link href="/content-gen" className="hover:text-foreground transition-colors">
          Content Studio
        </Link>
        <span>/</span>
        <Link href="/content-gen/backlog" className="hover:text-foreground transition-colors">
          Backlog
        </Link>
        <span>/</span>
        <span className="text-foreground">
          {backlogTitle(item).slice(0, 40)}
          {backlogTitle(item).length > 40 ? '…' : ''}
        </span>
      </nav>

      <div className="flex flex-wrap items-center gap-2">
        <BacklogItemForm item={item} onSubmitEdit={updateBacklogItem} />
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-9 gap-2"
          disabled={busy}
          onClick={() => selectBacklogItem?.(item.idea_id)}
        >
          <CheckCircle2 className="h-4 w-4" />
        </Button>
        <Button
          type="button"
          variant="default"
          size="sm"
          className="h-9 gap-2"
          disabled={busy}
          onClick={async () => {
            const p = await startBacklogItem?.(item.idea_id)
            if (p) window.location.href = `/content-gen/pipeline/${p}`
          }}
        >
          <Play className="h-4 w-4" />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-9 gap-2 text-warning hover:text-warning"
          disabled={busy}
          onClick={() => archiveBacklogItem?.(item.idea_id)}
        >
          <Archive className="h-4 w-4" />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-9 gap-2 text-error hover:text-error"
          disabled={busy}
          onClick={onDelete}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
