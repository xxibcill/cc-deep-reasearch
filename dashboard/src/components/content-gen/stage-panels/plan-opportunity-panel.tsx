'use client'

import type { PipelineContext } from '@/types/content-gen'
import { SummaryField, SectionList } from './ui'

export function PlanOpportunityPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.opportunity_brief) {
    return null
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 lg:grid-cols-2">
        <SummaryField label="Goal" value={ctx.opportunity_brief.goal || 'No goal captured'} />
        <SummaryField
          label="Primary audience"
          value={ctx.opportunity_brief.primary_audience_segment || 'No audience captured'}
        />
        <SummaryField
          label="Content objective"
          value={ctx.opportunity_brief.content_objective || 'No content objective captured'}
        />
        <SummaryField
          label="Freshness rationale"
          value={ctx.opportunity_brief.freshness_rationale || 'No freshness rationale captured'}
        />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <SectionList label="Problem statements" items={ctx.opportunity_brief.problem_statements} />
        <SectionList label="Sub-angles" items={ctx.opportunity_brief.sub_angles} />
        <SectionList label="Proof requirements" items={ctx.opportunity_brief.proof_requirements} />
        <SectionList label="Success criteria" items={ctx.opportunity_brief.success_criteria} />
      </div>
    </div>
  )
}
