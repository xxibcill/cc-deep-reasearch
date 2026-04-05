'use client'

import type { PipelineContext } from '@/types/content-gen'
import { SummaryField, SectionList } from './ui'

export function BuildResearchPackPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.research_pack) {
    return null
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <SectionList label="Proof points" items={ctx.research_pack.proof_points} />
      <SectionList label="Claims requiring verification" items={ctx.research_pack.claims_requiring_verification} />
      <SectionList label="Key facts" items={ctx.research_pack.key_facts} />
      <SummaryField
        label="Research stop reason"
        value={ctx.research_pack.research_stop_reason || 'No stop reason recorded'}
      />
    </div>
  )
}
