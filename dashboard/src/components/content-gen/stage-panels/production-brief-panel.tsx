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
      <SummaryField label="Wardrobe" value={ctx.production_brief.wardrobe || 'No wardrobe notes captured'} />
      <SummaryField label="Backup Plan" value={ctx.production_brief.backup_plan || 'No backup plan captured'} />
      <SectionList label="Props" items={ctx.production_brief.props} emptyLabel="No props listed" />
      <SectionList label="Assets to prepare" items={ctx.production_brief.assets_to_prepare} emptyLabel="No assets listed" />
      <SectionList label="Audio checks" items={ctx.production_brief.audio_checks} emptyLabel="No audio checks listed" />
      <SectionList label="Battery checks" items={ctx.production_brief.battery_checks} emptyLabel="No battery checks listed" />
      <SectionList label="Storage checks" items={ctx.production_brief.storage_checks} emptyLabel="No storage checks listed" />
      <SectionList label="Pickup lines" items={ctx.production_brief.pickup_lines_to_capture} emptyLabel="No pickup lines listed" />
    </div>
  )
}
