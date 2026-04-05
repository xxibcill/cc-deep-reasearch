'use client'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import type { PipelineContext } from '@/types/content-gen'
import { SectionList } from './ui'
import { findSelectedIdea } from './shared'

export function BuildBacklogPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.backlog) {
    return null
  }

  const selectedIdea = findSelectedIdea(ctx)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Badge variant="info">{ctx.backlog.items.length} ideas</Badge>
        <Badge variant="secondary">
          {ctx.backlog.items.filter((item) => item.status === 'selected').length} selected
        </Badge>
        {ctx.backlog.rejected_count > 0 ? (
          <Badge variant="warning">{ctx.backlog.rejected_count} rejected</Badge>
        ) : null}
      </div>
      {ctx.backlog.is_degraded ? (
        <Alert variant="warning">
          <AlertTitle>Backlog degraded</AlertTitle>
          <AlertDescription>
            {ctx.backlog.degradation_reason || 'The backlog stage completed with degraded output.'}
          </AlertDescription>
        </Alert>
      ) : null}
      {selectedIdea.item ? (
        <div className="rounded-[1rem] border border-border/80 bg-background/55 p-4">
          <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Selected backlog item
          </p>
          <p className="mt-2 text-sm font-medium text-foreground">{selectedIdea.item.idea}</p>
          <p className="mt-2 text-sm leading-relaxed text-foreground/75">{selectedIdea.item.potential_hook}</p>
        </div>
      ) : null}
      <SectionList
        label="Rejected reasons"
        items={ctx.backlog.rejection_reasons}
        emptyLabel="No backlog rejections recorded"
      />
    </div>
  )
}
