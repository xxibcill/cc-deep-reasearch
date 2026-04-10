'use client'

import { Badge } from '@/components/ui/badge'
import type { AngleOption, PipelineContext } from '@/types/content-gen'
import { getSelectedAngle, getAlternateAngles } from './shared'

function AngleCard({ angle, isSelected }: { angle: AngleOption; isSelected: boolean }) {
  return (
    <div
      className={`rounded-xl border p-3 ${
        isSelected
          ? 'border-primary/30 bg-primary/10'
          : 'border-border/70 bg-background/45'
      }`}
    >
      <div className="flex flex-wrap items-center gap-2 mb-2">
        {isSelected ? (
          <Badge variant="info" className="text-[10px]">Selected</Badge>
        ) : (
          <Badge variant="secondary" className="text-[10px]">Alternate</Badge>
        )}
        <Badge variant="outline" className="text-[10px]">{angle.format || 'Format pending'}</Badge>
        <Badge variant="outline" className="text-[10px]">{angle.tone || 'Tone pending'}</Badge>
      </div>
      <p className="text-sm font-medium text-foreground">{angle.core_promise}</p>
      <div className="mt-2 space-y-1 text-xs text-foreground/72">
        <p><span className="font-medium">Target:</span> {angle.target_audience}</p>
        <p><span className="font-medium">Problem:</span> {angle.viewer_problem}</p>
        <p><span className="font-medium">Takeaway:</span> {angle.primary_takeaway}</p>
        <p><span className="font-medium">Lens:</span> {angle.lens}</p>
        <p><span className="font-medium">CTA:</span> {angle.cta}</p>
      </div>
      {angle.why_this_version_should_exist && (
        <p className="mt-2 text-xs italic text-foreground/65">{angle.why_this_version_should_exist}</p>
      )}
    </div>
  )
}

export function GenerateAnglesPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.angles) {
    return null
  }

  const selectedAngle = getSelectedAngle(ctx)
  const alternateAngles = getAlternateAngles(ctx)

  return (
    <div className="space-y-4">
      {selectedAngle && <AngleCard angle={selectedAngle} isSelected={true} />}

      {alternateAngles.length > 0 && (
        <div className="space-y-3">
          <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Alternate angles ({alternateAngles.length})
          </p>
          <div className="grid gap-3">
            {alternateAngles.map((angle) => (
              <AngleCard key={angle.angle_id} angle={angle} isSelected={false} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
