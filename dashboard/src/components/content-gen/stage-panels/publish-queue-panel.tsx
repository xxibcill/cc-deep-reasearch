'use client'

import type { PipelineContext } from '@/types/content-gen'
import { SummaryField, SectionList } from './ui'

export function PublishQueuePanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.publish_item) {
    return null
  }

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <SummaryField label="Platform" value={ctx.publish_item.platform || 'No platform recorded'} />
      <SummaryField label="Publish time" value={ctx.publish_item.publish_datetime || 'No publish time recorded'} />
      <SectionList label="Cross-post targets" items={ctx.publish_item.cross_post_targets} emptyLabel="No cross-post targets" />
      <SummaryField
        label="First 30 minute plan"
        value={ctx.publish_item.first_30_minute_engagement_plan || 'No engagement plan recorded'}
      />
    </div>
  )
}
