'use client'

import type { PipelineContext } from '@/types/content-gen'
import { SummaryField, SectionList } from './ui'

export function VisualTranslationPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.visual_plan) {
    return null
  }

  return (
    <div className="space-y-4">
      <SummaryField
        label="Visual refresh check"
        value={ctx.visual_plan.visual_refresh_check || 'No visual refresh note captured'}
      />
      <SectionList
        label="Beat coverage"
        items={ctx.visual_plan.visual_plan.map((beat) => `${beat.beat}: ${beat.visual || beat.on_screen_text}`)}
      />
    </div>
  )
}
