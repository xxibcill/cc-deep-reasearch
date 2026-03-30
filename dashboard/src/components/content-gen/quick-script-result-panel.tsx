'use client'

import { QuickScriptProcessPanel } from '@/components/content-gen/quick-script-process-panel'
import { ScriptViewer } from '@/components/content-gen/script-viewer'
import type { RunScriptingResponse } from '@/types/content-gen'

interface QuickScriptResultPanelProps {
  result: RunScriptingResponse
}

export function QuickScriptResultPanel({ result }: QuickScriptResultPanelProps) {
  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-sm border border-border bg-background px-3 py-2">
          <p className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
            Execution
          </p>
          <p className="mt-1 text-sm text-foreground">
            {result.execution_mode === 'iterative' ? 'Iterative refinement' : 'Single pass'}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {result.iterations
              ? `${result.iterations.count}/${result.iterations.max_iterations} iterations used`
              : '1 iteration used'}
          </p>
        </div>

        {result.context.structure && (
          <div className="rounded-sm border border-border bg-background px-3 py-2">
            <p className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
              Beat structure
            </p>
            <p className="mt-1 text-sm text-foreground">
              {result.context.structure.chosen_structure}
            </p>
            {result.context.structure.why_it_fits && (
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                {result.context.structure.why_it_fits}
              </p>
            )}
            {result.context.structure.beat_list.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {result.context.structure.beat_list.map((beat) => (
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

        {result.iterations && result.iterations.quality_history.length > 0 && (
          <div className="rounded-sm border border-border bg-background px-3 py-2 md:col-span-2">
            <p className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
              Quality history
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {result.iterations.quality_history.map((entry) => (
                <span
                  key={entry.iteration}
                  className="rounded-sm border border-border px-2 py-1 text-xs font-mono text-muted-foreground"
                >
                  {`#${entry.iteration} ${(entry.score * 100).toFixed(0)}%${entry.passes ? ' pass' : ''}`}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      <QuickScriptProcessPanel traces={result.context.step_traces ?? []} />

      <ScriptViewer content={result.script || ''} label="Generated Script" />

      {result.run_id && (
        <p className="text-[11px] font-mono text-muted-foreground tabular-nums">
          {result.run_id}
        </p>
      )}
    </div>
  )
}
