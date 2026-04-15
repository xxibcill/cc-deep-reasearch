'use client'

import Link from 'next/link'
import { FileText } from 'lucide-react'

import type { PipelineContext } from '@/types/content-gen'
import { Badge } from '@/components/ui/badge'
import { SummaryField, SectionList } from './ui'
import { lifecycleStateBadgeVariant, lifecycleStateLabel } from '@/components/content-gen/brief-shared'

export function PlanOpportunityPanel({ ctx }: { ctx: PipelineContext }) {
  const briefRef = ctx.brief_reference

  return (
    <div className="space-y-4">
      {briefRef && (
        <div className="rounded-[0.95rem] border border-border/75 bg-surface/45 p-3 flex items-start justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <FileText className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                Managed Brief
              </span>
            </div>
            <p className="text-sm font-medium text-foreground/90">
              {briefRef.brief_id || 'Inline brief'}
            </p>
            {briefRef.revision_id && (
              <p className="text-xs font-mono text-muted-foreground">
                Rev {briefRef.revision_version} · {briefRef.revision_id.slice(0, 12)}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Badge variant={lifecycleStateBadgeVariant(briefRef.lifecycle_state)}>
              {lifecycleStateLabel(briefRef.lifecycle_state)}
            </Badge>
            {briefRef.brief_id && (
              <Link
                href={`/content-gen/briefs/${briefRef.brief_id}`}
                className="text-xs text-muted-foreground underline decoration-border underline-offset-2 hover:text-foreground transition-colors"
              >
                Open brief
              </Link>
            )}
          </div>
        </div>
      )}

      <div className="grid gap-3 lg:grid-cols-2">
        <SummaryField label="Goal" value={ctx.opportunity_brief?.goal || 'No goal captured'} />
        <SummaryField
          label="Primary audience"
          value={ctx.opportunity_brief?.primary_audience_segment || 'No audience captured'}
        />
        <SummaryField
          label="Content objective"
          value={ctx.opportunity_brief?.content_objective || 'No content objective captured'}
        />
        <SummaryField
          label="Freshness rationale"
          value={ctx.opportunity_brief?.freshness_rationale || 'No freshness rationale captured'}
        />
      </div>

      <SectionList
        label="Secondary audiences"
        items={ctx.opportunity_brief?.secondary_audience_segments}
        emptyLabel="No secondary audiences specified"
      />

      <SectionList
        label="Research hypotheses"
        items={ctx.opportunity_brief?.research_hypotheses}
        emptyLabel="No research hypotheses"
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionList
          label="Platform constraints"
          items={ctx.opportunity_brief?.platform_constraints}
          emptyLabel="No platform constraints"
        />
        <SectionList
          label="Risk constraints"
          items={ctx.opportunity_brief?.risk_constraints}
          emptyLabel="No risk constraints"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionList label="Problem statements" items={ctx.opportunity_brief?.problem_statements} />
        <SectionList label="Sub-angles" items={ctx.opportunity_brief?.sub_angles} />
        <SectionList label="Proof requirements" items={ctx.opportunity_brief?.proof_requirements} />
        <SectionList label="Success criteria" items={ctx.opportunity_brief?.success_criteria} />
      </div>
    </div>
  )
}
