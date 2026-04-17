'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, FileText, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Tabs } from '@/components/ui/tabs'
import { ScriptViewer } from '@/components/content-gen/script-viewer'
import { QuickScriptProcessPanel } from '@/components/content-gen/quick-script-process-panel'
import { ScriptBeatView } from '@/components/content-gen/script-detail/script-beat-view'
import { HooksCtaTab } from '@/components/content-gen/script-detail/hooks-cta-tab'
import { getScript } from '@/lib/content-gen-api'
import type { RunScriptingResponse } from '@/types/content-gen'

type TabValue = 'script' | 'hooks' | 'process'

export default function ScriptDetailPage() {
  const params = useParams()
  const router = useRouter()
  const runId = params.runId as string

  const [result, setResult] = useState<RunScriptingResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabValue>('script')

  const refreshResult = useCallback(() => {
    if (!runId) return
    setLoading(true)
    setError(null)
    getScript(runId)
      .then((data) => {
        setResult(data)
        setLoading(false)
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load script')
        setLoading(false)
      })
  }, [runId])

  useEffect(() => {
    refreshResult()
  }, [refreshResult])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex items-center gap-3 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span className="text-sm">Loading script...</span>
        </div>
      </div>
    )
  }

  if (error || !result) {
    return (
      <div className="space-y-4">
        <Alert variant="destructive">
          <AlertDescription>{error || 'Script not found'}</AlertDescription>
        </Alert>
        <Button variant="outline" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Go Back
        </Button>
      </div>
    )
  }

  const beatList = result.context.structure?.beat_list ?? []
  const hasBeats = beatList.length > 0

  const tabs = [
    { value: 'script', label: 'Generated Script' },
    { value: 'hooks', label: 'Hook & CTA' },
    { value: 'process', label: 'Process' },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <FileText className="h-5 w-5 text-muted-foreground" />
          <div>
            <h1 className="text-xl font-semibold font-display">Script Run</h1>
            {result.run_id && (
              <p className="text-xs font-mono text-muted-foreground tabular-nums">
                {result.run_id}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Execution metadata */}
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
              Beat Structure
            </p>
            <p className="mt-1 text-sm text-foreground">
              {result.context.structure.chosen_structure}
            </p>
            {result.context.structure.why_it_fits && (
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                {result.context.structure.why_it_fits}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Quality history */}
      {result.iterations && result.iterations.quality_history.length > 0 && (
        <div className="rounded-sm border border-border bg-background px-3 py-2">
          <p className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
            Quality History
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

      {/* Tabs */}
      <Tabs
        value={activeTab}
        onValueChange={(v) => setActiveTab(v as TabValue)}
        tabs={tabs}
      />

      {/* Tab content */}
      <div>
        {activeTab === 'script' && (
          hasBeats ? (
            <ScriptBeatView script={result.script || ''} beatList={beatList} />
          ) : (
            <ScriptViewer content={result.script || ''} label="Generated Script" showWordCount />
          )
        )}

        {activeTab === 'hooks' && (
          result.context.hooks ? (
            <HooksCtaTab
              hooks={result.context.hooks}
              cta={result.context.cta}
              script={result.script || ''}
              runId={runId}
              onApply={refreshResult}
            />
          ) : (
            <p className="text-sm text-muted-foreground">No hooks available</p>
          )
        )}

        {activeTab === 'process' && (
          <QuickScriptProcessPanel traces={result.context.step_traces ?? []} />
        )}
      </div>
    </div>
  )
}
