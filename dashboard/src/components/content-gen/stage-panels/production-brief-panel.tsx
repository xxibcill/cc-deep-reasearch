'use client'

import type { PipelineContext } from '@/types/content-gen'
import { SummaryField, SectionList } from './ui'
import { BriefReferenceCard } from './plan-opportunity-panel'

export function ProductionBriefPanel({ ctx }: { ctx: PipelineContext }) {
  const briefRef = ctx.brief_reference
  const executionBrief = ctx.execution_brief

  return (
    <div className="space-y-4">
      {briefRef && (
        <BriefReferenceCard
          label="Source Brief"
          subLabel={briefRef.revision_id ? `Rev ${briefRef.revision_version} · ${briefRef.reference_type}` : undefined}
          briefRef={briefRef}
        />
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <SummaryField label="Location" value={executionBrief?.location || ctx.production_brief?.location || 'No location captured'} />
        <SummaryField label="Setup" value={executionBrief?.setup || ctx.production_brief?.setup || 'No setup captured'} />
        <SummaryField label="Wardrobe" value={executionBrief?.wardrobe || ctx.production_brief?.wardrobe || 'No wardrobe notes captured'} />
        <SummaryField label="Backup Plan" value={executionBrief?.backup_plan || ctx.production_brief?.backup_plan || 'No backup plan captured'} />
        <SummaryField label="Fallback Location" value={executionBrief?.location_fallback || 'No fallback location captured'} />
        <SummaryField label="Asset Reuse Plan" value={executionBrief?.asset_reuse_plan || 'No asset reuse plan captured'} />
        <SectionList label="Props" items={executionBrief?.props || ctx.production_brief?.props} emptyLabel="No props listed" />
        <SectionList label="Prop fallbacks" items={executionBrief?.prop_fallbacks} emptyLabel="No prop fallbacks listed" />
        <SectionList label="Assets to prepare" items={executionBrief?.assets_to_prepare || ctx.production_brief?.assets_to_prepare} emptyLabel="No assets listed" />
        <SectionList label="Existing assets" items={executionBrief?.existing_assets} emptyLabel="No reusable assets identified" />
        <SectionList label="Visual fallbacks" items={executionBrief?.visual_fallbacks} emptyLabel="No visual fallbacks listed" />
        <SectionList label="Audio checks" items={executionBrief?.audio_checks || ctx.production_brief?.audio_checks} emptyLabel="No audio checks listed" />
        <SectionList label="Battery checks" items={executionBrief?.battery_checks || ctx.production_brief?.battery_checks} emptyLabel="No battery checks listed" />
        <SectionList label="Storage checks" items={executionBrief?.storage_checks || ctx.production_brief?.storage_checks} emptyLabel="No storage checks listed" />
        <SectionList label="Pickup lines" items={executionBrief?.pickup_lines_to_capture || ctx.production_brief?.pickup_lines_to_capture} emptyLabel="No pickup lines listed" />
      </div>
    </div>
  )
}
