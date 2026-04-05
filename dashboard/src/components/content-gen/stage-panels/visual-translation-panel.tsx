'use client'

import type { BeatVisual, PipelineContext } from '@/types/content-gen'
import { SummaryField } from './ui'

function BeatTableRow({ beat }: { beat: BeatVisual }) {
  return (
    <tr className="border-b border-border/50 last:border-0">
      <td className="py-2 pr-3 align-top">
        <span className="text-xs font-medium text-foreground/70">{beat.beat}</span>
      </td>
      <td className="py-2 pr-3 align-top">
        <span className="text-xs text-foreground/80 line-clamp-2">{beat.spoken_line || '—'}</span>
      </td>
      <td className="py-2 pr-3 align-top">
        <span className="text-xs text-foreground/80 line-clamp-2">{beat.visual || '—'}</span>
      </td>
      <td className="py-2 pr-3 align-top">
        <span className="text-xs text-foreground/60">{beat.shot_type || '—'}</span>
      </td>
      <td className="py-2 pr-3 align-top">
        <span className="text-xs text-foreground/60">{beat.on_screen_text || '—'}</span>
      </td>
      <td className="py-2 pr-3 align-top">
        <span className="text-xs text-foreground/60">{beat.prop_or_asset || '—'}</span>
      </td>
      <td className="py-2 pr-3 align-top">
        <span className="text-xs text-foreground/60">{beat.transition || '—'}</span>
      </td>
      <td className="py-2 align-top">
        <span className="text-xs text-foreground/60">{beat.retention_function || '—'}</span>
      </td>
    </tr>
  )
}

export function VisualTranslationPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.visual_plan) {
    return null
  }

  return (
    <div className="space-y-4">
      <SummaryField
        label="Visual refresh check"
        value={ctx.visual_plan.visual_refresh_check || 'No visual refresh note captured'}
      />
      {ctx.visual_plan.visual_plan.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-border/70">
          <table className="w-full text-left text-xs">
            <thead className="bg-background/80">
              <tr>
                <th className="py-2 pr-3 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Beat</th>
                <th className="py-2 pr-3 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Spoken</th>
                <th className="py-2 pr-3 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Visual</th>
                <th className="py-2 pr-3 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Shot</th>
                <th className="py-2 pr-3 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Text</th>
                <th className="py-2 pr-3 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Asset</th>
                <th className="py-2 pr-3 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Trans</th>
                <th className="py-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Retention</th>
              </tr>
            </thead>
            <tbody>
              {ctx.visual_plan.visual_plan.map((beat, idx) => (
                <BeatTableRow key={`${beat.beat}-${idx}`} beat={beat} />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No beats captured</p>
      )}
    </div>
  )
}
