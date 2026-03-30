'use client'

import { useEffect, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import useContentGen from '@/hooks/useContentGen'
import { QuickScriptResultPanel } from '@/components/content-gen/quick-script-result-panel'
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
    loadScripts()
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
    return <div className="text-muted-foreground text-sm py-8 text-center">Loading scripts...</div>
  }

  if (scripts.length === 0) {
    return (
      <div className="py-16 text-center">
        <p className="text-sm text-muted-foreground">No scripts yet.</p>
        <p className="text-xs text-muted-foreground/50 mt-1">
          Run the scripting pipeline to generate your first script.
        </p>
      </div>
    )
  }

  return (
    <div className="divide-y divide-border">
      {scripts.map((run) => (
        <div key={run.run_id} className="bg-surface">
          <button
            onClick={() => handleExpand(run.run_id)}
            className="w-full flex items-center justify-between px-3 py-3 text-sm hover:bg-surface-raised/50 transition-colors"
          >
            <div className="flex items-center gap-2 min-w-0">
              {expandedId === run.run_id ? (
                <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              )}
              <span className="truncate text-foreground/80">{run.raw_idea || 'Untitled'}</span>
            </div>
            <div className="flex items-center gap-3 shrink-0 text-xs text-muted-foreground font-mono tabular-nums">
              <span className="hidden sm:inline">
                {run.execution_mode === 'iterative' && run.iterations
                  ? `${run.iterations.count}/${run.iterations.max_iterations}x`
                  : '1x'}
              </span>
              <span>{run.word_count}w</span>
              <span className="hidden sm:inline">{run.saved_at}</span>
            </div>
          </button>
          {expandedId === run.run_id && (
            <div className="px-3 pb-4 pt-1 border-t border-border animate-fade-in">
              <div className="mb-3 flex items-center justify-end">
                <button
                  type="button"
                  onClick={() => onReuseInputs?.(run.raw_idea)}
                  className="rounded-sm border border-warning/30 bg-warning/10 px-3 py-1.5 text-xs font-medium text-warning transition-colors hover:bg-warning/15"
                >
                  Reuse Inputs
                </button>
              </div>
              {scriptResults[run.run_id] ? (
                <QuickScriptResultPanel result={scriptResults[run.run_id]} />
              ) : (
                <p className="text-sm text-muted-foreground">Loading saved result...</p>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
