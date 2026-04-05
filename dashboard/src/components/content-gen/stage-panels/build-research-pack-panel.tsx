'use client'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import type { PipelineContext } from '@/types/content-gen'
import { SummaryField, SectionList } from './ui'

export function BuildResearchPackPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.research_pack) {
    return null
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <SectionList label="Proof points" items={ctx.research_pack.proof_points} />
        <SectionList label="Key facts" items={ctx.research_pack.key_facts} />
        <SectionList label="Claims requiring verification" items={ctx.research_pack.claims_requiring_verification} />
        <SectionList label="Unsafe/uncertain claims" items={ctx.research_pack.unsafe_or_uncertain_claims} />
      </div>

      <SectionList label="Audience insights" items={ctx.research_pack.audience_insights} emptyLabel="No audience insights" />

      <SectionList label="Competitor observations" items={ctx.research_pack.competitor_observations} emptyLabel="No competitor observations" />

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionList label="Examples" items={ctx.research_pack.examples} emptyLabel="No examples" />
        <SectionList label="Case studies" items={ctx.research_pack.case_studies} emptyLabel="No case studies" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionList label="Gaps to exploit" items={ctx.research_pack.gaps_to_exploit} emptyLabel="No gaps identified" />
        <SectionList label="Assets needed" items={ctx.research_pack.assets_needed} emptyLabel="No assets needed" />
      </div>

      <SummaryField
        label="Research stop reason"
        value={ctx.research_pack.research_stop_reason || 'No stop reason recorded'}
      />
    </div>
  )
}
