'use client'

import { QuickScriptProcessPanel } from '@/components/content-gen/quick-script-process-panel'
import { ScriptViewer } from '@/components/content-gen/script-viewer'
import type { PipelineContext } from '@/types/content-gen'

export function RunScriptingPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.scripting) {
    return null
  }

  const scripting = ctx.scripting
  const finalScript =
    scripting.qc?.final_script ||
    scripting.tightened?.content ||
    scripting.draft?.content ||
    ''
  const finalWordCount =
    scripting.tightened?.word_count ||
    scripting.draft?.word_count ||
    (finalScript ? finalScript.trim().split(/\s+/).length : 0)
  const traceIterations = new Set(scripting.step_traces.map((trace) => trace.iteration))
  const iterationCount = traceIterations.size || 1
  const executionMode = iterationCount > 1 ? 'Iterative refinement' : 'Single pass'

  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-sm border border-border bg-background px-3 py-2">
          <p className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
            Execution
          </p>
          <p className="mt-1 text-sm text-foreground">
            {executionMode}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {iterationCount > 1 ? `${iterationCount} passes captured` : '1 pass captured'}
          </p>
        </div>

        {scripting.structure && (
          <div className="rounded-sm border border-border bg-background px-3 py-2">
            <p className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
              Beat structure
            </p>
            <p className="mt-1 text-sm text-foreground">
              {scripting.structure.chosen_structure}
            </p>
            {scripting.structure.why_it_fits && (
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                {scripting.structure.why_it_fits}
              </p>
            )}
            {scripting.structure.beat_list.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {scripting.structure.beat_list.map((beat) => (
                  <span
                    key={beat}
                    className="rounded-sm border border-border px-2 py-1 text-xs font-mono text-muted-foreground"
                  >
                    {beat}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {finalWordCount > 0 && (
          <div className="rounded-sm border border-border bg-background px-3 py-2">
            <p className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
              Word Count
            </p>
            <p className="mt-1 text-sm text-foreground">{finalWordCount}</p>
          </div>
        )}
      </div>

      {scripting.tone && (
        <div className="rounded-sm border border-border bg-background px-3 py-2">
          <p className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
            Tone
          </p>
          <p className="mt-1 text-sm text-foreground">{scripting.tone}</p>
        </div>
      )}

      {scripting.cta && (
        <div className="rounded-sm border border-border bg-background px-3 py-2">
          <p className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
            Call to Action
          </p>
          <p className="mt-1 text-sm text-foreground">{scripting.cta}</p>
        </div>
      )}

      {scripting.angle && (
        <div className="rounded-sm border border-border bg-background px-3 py-2">
          <p className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
            Angle
          </p>
          <p className="mt-1 text-sm text-foreground">{scripting.angle.angle}</p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            {scripting.angle.why_it_works}
          </p>
        </div>
      )}

      {scripting.hooks && (
        <div className="rounded-sm border border-border bg-background px-3 py-2">
          <p className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
            Hook
          </p>
          <p className="mt-1 text-sm text-foreground">{scripting.hooks.best_hook}</p>
          {scripting.hooks.best_hook_reason && (
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {scripting.hooks.best_hook_reason}
            </p>
          )}
        </div>
      )}

      <ScriptViewer content={finalScript} label="Final Script" />

      <QuickScriptProcessPanel traces={scripting.step_traces} label="Scripting Process" />
    </div>
  )
}
