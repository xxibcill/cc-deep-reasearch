'use client'

import type { PipelineContext } from '@/types/content-gen'
import { SummaryField, SectionList } from './ui'
import { BriefReferenceCard } from './plan-opportunity-panel'

/** Returns first truthy, non-empty string or undefined. */
function firstTruthy(...values: (string | null | undefined)[]): string | undefined {
  for (const v of values) {
    if (v != null && v.trim() !== '') return v
  }
  return undefined
}

/** Returns first non-empty array or undefined. */
function firstNonEmptyArray<T>(...arrays: (T[] | null | undefined)[]): T[] | undefined {
  for (const arr of arrays) {
    if (arr != null && arr.length > 0) return arr
  }
  return undefined
}

export function ProductionBriefPanel({ ctx }: { ctx: PipelineContext }) {
  const briefRef = ctx.brief_reference
  const executionBrief = ctx.execution_brief

  const location = firstTruthy(executionBrief?.location, ctx.production_brief?.location)
  const setup = firstTruthy(executionBrief?.setup, ctx.production_brief?.setup)
  const wardrobe = firstTruthy(executionBrief?.wardrobe, ctx.production_brief?.wardrobe)
  const backupPlan = firstTruthy(executionBrief?.backup_plan, ctx.production_brief?.backup_plan)
  const locationFallback = executionBrief?.location_fallback
  const assetReusePlan = executionBrief?.asset_reuse_plan
  const props = firstNonEmptyArray(...[executionBrief?.props, ctx.production_brief?.props])
  const assetsToPrepare = firstNonEmptyArray(...[executionBrief?.assets_to_prepare, ctx.production_brief?.assets_to_prepare])
  const existingAssets = executionBrief?.existing_assets
  const visualFallbacks = executionBrief?.visual_fallbacks
  const audioChecks = firstNonEmptyArray(...[executionBrief?.audio_checks, ctx.production_brief?.audio_checks])
  const batteryChecks = firstNonEmptyArray(...[executionBrief?.battery_checks, ctx.production_brief?.battery_checks])
  const storageChecks = firstNonEmptyArray(...[executionBrief?.storage_checks, ctx.production_brief?.storage_checks])
  const pickupLines = firstNonEmptyArray(...[executionBrief?.pickup_lines_to_capture, ctx.production_brief?.pickup_lines_to_capture])

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
        <SummaryField label="Location" value={location} fallback="No location captured" />
        <SummaryField label="Setup" value={setup} fallback="No setup captured" />
        <SummaryField label="Wardrobe" value={wardrobe} fallback="No wardrobe notes captured" />
        <SummaryField label="Backup Plan" value={backupPlan} fallback="No backup plan captured" />
        <SummaryField label="Fallback Location" value={locationFallback} fallback="No fallback location captured" />
        <SummaryField label="Asset Reuse Plan" value={assetReusePlan} fallback="No asset reuse plan captured" />
        <SectionList label="Props" items={props} emptyLabel="No props listed" />
        <SectionList label="Prop fallbacks" items={executionBrief?.prop_fallbacks} emptyLabel="No prop fallbacks listed" />
        <SectionList label="Assets to prepare" items={assetsToPrepare} emptyLabel="No assets listed" />
        <SectionList label="Existing assets" items={existingAssets} emptyLabel="No reusable assets identified" />
        <SectionList label="Visual fallbacks" items={visualFallbacks} emptyLabel="No visual fallbacks listed" />
        <SectionList label="Audio checks" items={audioChecks} emptyLabel="No audio checks listed" />
        <SectionList label="Battery checks" items={batteryChecks} emptyLabel="No battery checks listed" />
        <SectionList label="Storage checks" items={storageChecks} emptyLabel="No storage checks listed" />
        <SectionList label="Pickup lines" items={pickupLines} emptyLabel="No pickup lines listed" />
      </div>
    </div>
  )
}
