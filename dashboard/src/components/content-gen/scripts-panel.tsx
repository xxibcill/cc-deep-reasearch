'use client'

import { useEffect, useState } from 'react'

import { QuickScriptResultPanel } from '@/components/content-gen/quick-script-result-panel'
import { Button } from '@/components/ui/button'
import { CollapsiblePanel } from '@/components/ui/collapsible-panel'
import useContentGen from '@/hooks/useContentGen'
import type { RunScriptingResponse } from '@/types/content-gen'

interface ScriptsPanelProps {
  onReuseInputs?: (rawIdea: string) => void
}

export function ScriptsPanel({ onReuseInputs }: ScriptsPanelProps) {
  const scripts = useContentGen((s) => s.scripts)
  const loadScripts = useContentGen((s) => s.loadScripts)
  const loading = useContentGen((s) => s.scriptsLoading)

  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [scriptResults, setScriptResults] = useState<Record<string, RunScriptingResponse>>({})

  useEffect(() => {
    void loadScripts()
  }, [loadScripts])

  const handleExpand = async (runId: string) => {
    if (expandedId === runId) {
      setExpandedId(null)
      return
    }

    setExpandedId(runId)

    if (!scriptResults[runId]) {
      try {
        const { getScript } = await import('@/lib/content-gen-api')
        const data = await getScript(runId)
        setScriptResults((prev) => ({ ...prev, [runId]: data }))
      } catch {
        setScriptResults((prev) => ({
          ...prev,
          [runId]: {
            run_id: runId,
            raw_idea: '',
            script: '[Error loading saved result]',
            word_count: 0,
            context: {
              raw_idea: '',
              research_context: '',
              tone: '',
              cta: '',
              core_inputs: null,
              angle: null,
              structure: null,
              beat_intents: null,
              hooks: null,
              draft: null,
              retention_revised: null,
              tightened: null,
              annotated_script: null,
              visual_notes: null,
              qc: null,
              step_traces: [],
            },
            execution_mode: 'single_pass',
          },
        }))
      }
    }
  }

  if (loading) {
    return <div className="py-8 text-center text-sm text-muted-foreground">Loading scripts...</div>
  }

  if (scripts.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-card/70 py-16 text-center">
        <p className="text-sm text-muted-foreground">No scripts yet.</p>
        <p className="mt-1 text-xs text-muted-foreground/60">
          Run the scripting pipeline to generate your first script.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {scripts.map((run) => (
        <CollapsiblePanel
          key={run.run_id}
          open={expandedId === run.run_id}
          onOpenChange={() => void handleExpand(run.run_id)}
          summary={
            <div className="space-y-1">
              <div className="truncate text-sm font-medium text-foreground/90">
                {run.raw_idea || 'Untitled'}
              </div>
              <div className="text-[11px] font-mono text-muted-foreground tabular-nums">
                {run.run_id}
              </div>
            </div>
          }
          meta={
            <div className="flex items-center gap-3 text-xs font-mono text-muted-foreground tabular-nums">
              <span className="hidden sm:inline">
                {run.execution_mode === 'iterative' && run.iterations
                  ? `${run.iterations.count}/${run.iterations.max_iterations}x`
                  : '1x'}
              </span>
              <span>{run.word_count}w</span>
              <span className="hidden sm:inline">{run.saved_at}</span>
            </div>
          }
        >
          <div className="space-y-3">
            {onReuseInputs ? (
              <div className="flex items-center justify-end">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => onReuseInputs(run.raw_idea)}
                >
                  Reuse Inputs
                </Button>
              </div>
            ) : null}

            {scriptResults[run.run_id] ? (
              <QuickScriptResultPanel result={scriptResults[run.run_id]} />
            ) : (
              <p className="text-sm text-muted-foreground">Loading saved result...</p>
            )}
          </div>
        </CollapsiblePanel>
      ))}
    </div>
  )
}
