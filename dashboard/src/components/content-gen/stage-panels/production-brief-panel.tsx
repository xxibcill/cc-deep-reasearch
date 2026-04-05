'use client'

import type { PipelineContext } from '@/types/content-gen'
import { SummaryField, SectionList } from './ui'

export function ProductionBriefPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.production_brief) {
    return null
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <SummaryField label="Location" value={ctx.production_brief.location || 'No location captured'} />
      <SummaryField label="Setup" value={ctx.production_brief.setup || 'No setup captured'} />
      <SectionList label="Props" items={ctx.production_brief.props} emptyLabel="No props listed" />
      <SectionList label="Assets to prepare" items={ctx.production_brief.assets_to_prepare} emptyLabel="No assets listed" />
    </div>
  )
}
