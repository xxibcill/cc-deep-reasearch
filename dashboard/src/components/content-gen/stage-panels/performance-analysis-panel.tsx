'use client'

import type { PipelineContext } from '@/types/content-gen'
import { SummaryField, SectionList } from './ui'

export function PerformanceAnalysisPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.performance) {
    return null
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <SectionList label="What worked" items={ctx.performance.what_worked} />
      <SectionList label="What failed" items={ctx.performance.what_failed} />
      <SectionList label="Follow-up ideas" items={ctx.performance.follow_up_ideas} />
      <SummaryField label="Next test" value={ctx.performance.next_test || 'No next test recorded'} />
    </div>
  )
}
