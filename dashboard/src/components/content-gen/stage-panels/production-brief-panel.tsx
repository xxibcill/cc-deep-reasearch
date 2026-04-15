'use client'

import Link from 'next/link'
import { FileText } from 'lucide-react'

import type { PipelineContext } from '@/types/content-gen'
import { Badge } from '@/components/ui/badge'
import { SummaryField, SectionList } from './ui'
import { lifecycleStateBadgeVariant, lifecycleStateLabel } from '@/components/content-gen/brief-shared'

export function ProductionBriefPanel({ ctx }: { ctx: PipelineContext }) {
  const briefRef = ctx.brief_reference

  return (
    <div className="space-y-4">
      {briefRef && (
        <div className="rounded-[0.95rem] border border-border/75 bg-surface/45 p-3 flex items-start justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <FileText className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                Source Brief
              </span>
            </div>
            <p className="text-sm font-medium text-foreground/90">
              {briefRef.brief_id || 'Inline brief'}
            </p>
            {briefRef.revision_id && (
              <p className="text-xs font-mono text-muted-foreground">
                Rev {briefRef.revision_version} · {briefRef.reference_type}
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

      <div className="grid gap-4 lg:grid-cols-2">
        <SummaryField label="Location" value={ctx.production_brief?.location || 'No location captured'} />
        <SummaryField label="Setup" value={ctx.production_brief?.setup || 'No setup captured'} />
        <SummaryField label="Wardrobe" value={ctx.production_brief?.wardrobe || 'No wardrobe notes captured'} />
        <SummaryField label="Backup Plan" value={ctx.production_brief?.backup_plan || 'No backup plan captured'} />
        <SectionList label="Props" items={ctx.production_brief?.props} emptyLabel="No props listed" />
        <SectionList label="Assets to prepare" items={ctx.production_brief?.assets_to_prepare} emptyLabel="No assets listed" />
        <SectionList label="Audio checks" items={ctx.production_brief?.audio_checks} emptyLabel="No audio checks listed" />
        <SectionList label="Battery checks" items={ctx.production_brief?.battery_checks} emptyLabel="No battery checks listed" />
        <SectionList label="Storage checks" items={ctx.production_brief?.storage_checks} emptyLabel="No storage checks listed" />
        <SectionList label="Pickup lines" items={ctx.production_brief?.pickup_lines_to_capture} emptyLabel="No pickup lines listed" />
      </div>
    </div>
  )
}
