'use client'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { backlogHook, backlogSummary, backlogTitle } from '@/components/content-gen/backlog-shared'
import type { BacklogItem, PipelineContext } from '@/types/content-gen'
import { SectionList } from './ui'
import { findSelectedIdea } from './shared'

function BacklogItemCard({ item, isSelected }: { item: BacklogItem; isSelected: boolean }) {
  return (
    <div
      className={`rounded-xl border p-3 ${
        isSelected
          ? 'border-success/30 bg-success-muted/10'
          : 'border-border/70 bg-background/45'
      }`}
    >
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <Badge variant={isSelected ? 'success' : 'secondary'} className="text-[10px]">
          {item.category}
        </Badge>
        <Badge variant="outline" className="text-[10px]">
          Score: {item.priority_score}
        </Badge>
        <Badge
          variant={
            item.risk_level === 'high'
              ? 'destructive'
              : item.risk_level === 'medium'
                ? 'warning'
                : 'outline'
          }
          className="text-[10px]"
        >
          {item.risk_level} risk
        </Badge>
      </div>
      <p className="text-sm font-medium text-foreground">{backlogTitle(item)}</p>
      <p className="mt-1 text-xs text-foreground/72">{backlogSummary(item)}</p>
      <p className="mt-1 text-xs text-foreground/72">
        <span className="font-medium">Audience:</span> {item.audience}
      </p>
      <p className="mt-1 text-xs text-foreground/72">
        <span className="font-medium">Why now:</span> {item.why_now}
      </p>
      {item.evidence && (
        <p className="mt-1 text-xs text-foreground/65">
          <span className="font-medium">Evidence:</span> {item.evidence}
        </p>
      )}
      {backlogHook(item) && !isSelected && (
        <p className="mt-2 text-xs text-foreground/65 italic">Hook: {backlogHook(item)}</p>
      )}
    </div>
  )
}

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

      {ctx.backlog.items.length > 0 && (
        <div className="space-y-2">
          {ctx.backlog.items.map((item) => (
            <BacklogItemCard
              key={item.idea_id}
              item={item}
              isSelected={item.idea_id === selectedIdea.item?.idea_id}
            />
          ))}
        </div>
      )}

      <SectionList
        label="Rejected reasons"
        items={ctx.backlog.rejection_reasons}
        emptyLabel="No backlog rejections recorded"
      />
    </div>
  )
}
