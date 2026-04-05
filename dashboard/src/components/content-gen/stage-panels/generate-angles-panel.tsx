'use client'

import { Badge } from '@/components/ui/badge'
import type { PipelineContext } from '@/types/content-gen'
import { getSelectedAngle, getAlternateAngles } from './shared'

export function GenerateAnglesPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.angles) {
    return null
  }

  const selectedAngle = getSelectedAngle(ctx)
  const alternateAngles = getAlternateAngles(ctx)

  return (
    <div className="space-y-4">
      {selectedAngle ? (
        <div className="rounded-[1rem] border border-primary/20 bg-primary/10 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info">Selected angle</Badge>
            <Badge variant="outline">{selectedAngle.format || 'Format pending'}</Badge>
          </div>
          <p className="mt-3 text-sm font-medium text-foreground">{selectedAngle.core_promise}</p>
          <p className="mt-2 text-sm text-foreground/72">{selectedAngle.viewer_problem}</p>
          {ctx.angles.selection_reasoning ? (
            <p className="mt-3 text-sm leading-relaxed text-foreground/78">
              {ctx.angles.selection_reasoning}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="space-y-3">
        <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
          Alternate angles
        </p>
        {alternateAngles.length > 0 ? (
          <div className="grid gap-3">
            {alternateAngles.map((angle) => (
              <div
                key={angle.angle_id}
                className="rounded-[1rem] border border-border/70 bg-background/45 px-4 py-3"
              >
                <p className="text-sm font-medium text-foreground/88">{angle.core_promise}</p>
                <p className="mt-2 text-sm text-foreground/72">{angle.why_this_version_should_exist}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No alternate angles recorded.</p>
        )}
      </div>
    </div>
  )
}
