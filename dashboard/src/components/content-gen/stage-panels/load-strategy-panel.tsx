'use client'

import type { PipelineContext } from '@/types/content-gen'
import { SummaryField, SectionList } from './ui'

export function LoadStrategyPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.strategy) {
    return null
  }

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <SummaryField label="Niche" value={ctx.strategy.niche || 'Not set'} />
      <SummaryField label="Tone rules" value={ctx.strategy.tone_rules.join(' | ') || 'No tone rules yet'} />
      <SectionList label="Content pillars" items={ctx.strategy.content_pillars} emptyLabel="No pillars configured" />
      <SectionList label="Platforms" items={ctx.strategy.platforms} emptyLabel="No platforms configured" />
    </div>
  )
}
