'use client'

import { Badge } from '@/components/ui/badge'
import type { PipelineContext } from '@/types/content-gen'

export function PublishQueuePanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.publish_item) {
    return null
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">{ctx.publish_item.platform || 'Unknown platform'}</Badge>
        <Badge variant={ctx.publish_item.status === 'published' ? 'default' : 'secondary'}>
          {ctx.publish_item.status || 'Unknown status'}
        </Badge>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-border/70 bg-background/55 px-3 py-3">
          <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Publish Time
          </p>
          <p className="mt-2 text-sm leading-relaxed text-foreground/82">
            {ctx.publish_item.publish_datetime || 'No publish time recorded'}
          </p>
        </div>

        <div className="rounded-xl border border-border/70 bg-background/55 px-3 py-3">
          <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Asset Version
          </p>
          <p className="mt-2 text-sm leading-relaxed text-foreground/82">
            {ctx.publish_item.asset_version || '—'}
          </p>
        </div>

        <div className="rounded-xl border border-border/70 bg-background/55 px-3 py-3">
          <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Caption Version
          </p>
          <p className="mt-2 text-sm leading-relaxed text-foreground/82">
            {ctx.publish_item.caption_version || '—'}
          </p>
        </div>

        <div className="rounded-xl border border-border/70 bg-background/55 px-3 py-3">
          <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            First 30 Min Plan
          </p>
          <p className="mt-2 text-sm leading-relaxed text-foreground/82">
            {ctx.publish_item.first_30_minute_engagement_plan || 'No plan recorded'}
          </p>
        </div>
      </div>

      {ctx.publish_item.pinned_comment && (
        <div className="rounded-xl border border-border/70 bg-background/55 px-3 py-3">
          <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Pinned Comment
          </p>
          <p className="mt-2 text-sm leading-relaxed text-foreground/82">
            {ctx.publish_item.pinned_comment}
          </p>
        </div>
      )}

      {ctx.publish_item.cross_post_targets.length > 0 && (
        <div className="rounded-xl border border-border/70 bg-background/55 px-3 py-3">
          <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Cross-post Targets
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {ctx.publish_item.cross_post_targets.map((target, idx) => (
              <Badge key={idx} variant="outline" className="text-xs">
                {target}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
