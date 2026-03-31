'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { Play, FileText, ArrowRight } from 'lucide-react'
import useContentGen from '@/hooks/useContentGen'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { StartPipelineForm } from '@/components/content-gen/start-pipeline-form'
import { QuickScriptForm } from '@/components/content-gen/quick-script-form'
import { ScriptsPanel } from '@/components/content-gen/scripts-panel'
import { StrategyEditor } from '@/components/content-gen/strategy-editor'
import { PublishQueuePanel } from '@/components/content-gen/publish-queue-panel'
import { OverviewSidebar } from '@/components/content-gen/overview-sidebar'
import {
  createEmptyQuickScriptFields,
  parseQuickScriptPrompt,
  type QuickScriptFields,
} from '@/lib/quick-script'

export default function ContentGenPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const activeTab = searchParams.get('tab') || 'overview'

  const pipelines = useContentGen((s) => s.pipelines)
  const publishQueue = useContentGen((s) => s.publishQueue)
  const loadAll = useContentGen((s) => s.loadAll)
  const removeFromQueue = useContentGen((s) => s.removeFromQueue)
  const error = useContentGen((s) => s.error)

  const [newPipelineOpen, setNewPipelineOpen] = useState(false)
  const [quickScriptOpen, setQuickScriptOpen] = useState(false)
  const [quickScriptInitialValues, setQuickScriptInitialValues] = useState<QuickScriptFields>(() =>
    createEmptyQuickScriptFields(),
  )

  useEffect(() => {
    void loadAll()
  }, [loadAll])

  const activePipelines = pipelines.filter((p) => p.status === 'running' || p.status === 'queued')
  const pastPipelines = pipelines.filter(
    (p) => p.status === 'completed' || p.status === 'failed' || p.status === 'cancelled',
  )

  const handleTabChange = (tab: string) => {
    router.push(`/content-gen${tab === 'overview' ? '' : `?tab=${tab}`}`)
  }

  const handleRemoveFromQueue = async (ideaId: string, platform: string) => {
    await removeFromQueue(ideaId, platform)
  }

  const openQuickScriptBlank = () => {
    setQuickScriptInitialValues(createEmptyQuickScriptFields())
    setQuickScriptOpen(true)
  }

  const openQuickScriptFromHistory = (rawIdea: string) => {
    setQuickScriptInitialValues(parseQuickScriptPrompt(rawIdea))
    setQuickScriptOpen(true)
  }

  // Overview tab content
  const renderOverview = () => (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-6">
      {/* Left column */}
      <div className="space-y-6">
        {/* Quick actions */}
        <div className="flex gap-3">
          <Button
            type="button"
            onClick={() => setNewPipelineOpen(true)}
            className="gap-2 bg-warning text-background hover:bg-warning/90"
          >
            <Play className="h-4 w-4" />
            New Pipeline
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={openQuickScriptBlank}
            className="gap-2"
          >
            <FileText className="h-4 w-4" />
            Quick Script
          </Button>
        </div>

        {/* Error banner */}
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Content studio error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Active pipelines */}
        {activePipelines.length > 0 && (
          <section>
            <h2 className="text-xs font-mono uppercase tracking-wider text-muted-foreground mb-3">
              Active Pipelines
            </h2>
            <div className="space-y-1">
              {activePipelines.map((p) => (
                <Link
                  key={p.pipeline_id}
                  href={`/content-gen/pipeline/${p.pipeline_id}`}
                  className="flex items-center justify-between px-3 py-2.5 bg-surface border border-border rounded-sm
                    hover:border-warning/30 transition-colors group"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="w-2 h-2 rounded-full bg-warning animate-stage-pulse shrink-0" />
                    <span className="text-sm font-medium truncate">{p.theme}</span>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-[11px] font-mono text-warning tabular-nums">
                      {String(p.current_stage + 1).padStart(2, '0')}/12
                    </span>
                    <ArrowRight className="h-3.5 w-3.5 text-muted-foreground group-hover:text-warning transition-colors" />
                  </div>
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* Past pipelines */}
        {pastPipelines.length > 0 && (
          <section>
            <h2 className="text-xs font-mono uppercase tracking-wider text-muted-foreground mb-3">
              Past Pipelines
            </h2>
            <div className="space-y-1">
              {pastPipelines.map((p) => (
                <Link
                  key={p.pipeline_id}
                  href={`/content-gen/pipeline/${p.pipeline_id}`}
                  className="flex items-center justify-between px-3 py-2.5 bg-surface border border-border rounded-sm
                    hover:border-border/80 transition-colors group"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span
                      className={`w-2 h-2 rounded-full shrink-0 ${
                        p.status === 'completed' ? 'bg-success/60' : 'bg-error/60'
                      }`}
                    />
                    <span className="text-sm text-foreground/70 truncate">{p.theme}</span>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-[11px] font-mono text-muted-foreground tabular-nums">
                      {p.status}
                    </span>
                    <ArrowRight className="h-3.5 w-3.5 text-muted-foreground/50 group-hover:text-foreground transition-colors" />
                  </div>
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* Empty state */}
        {activePipelines.length === 0 && pastPipelines.length === 0 && (
          <section className="py-16 text-center">
            <p className="text-sm text-muted-foreground">No pipelines yet.</p>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setNewPipelineOpen(true)}
              className="mt-4 gap-2 text-warning hover:bg-warning/10 hover:text-warning"
            >
              Start your first pipeline
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </section>
        )}
      </div>

      {/* Right sidebar */}
      <OverviewSidebar onTabChange={handleTabChange} />
    </div>
  )

  return (
    <>
      {/* Tab content */}
      {activeTab === 'overview' && renderOverview()}

      {activeTab === 'scripts' && (
        <div className="w-full">
          <ScriptsPanel onReuseInputs={openQuickScriptFromHistory} />
        </div>
      )}

      {activeTab === 'strategy' && (
        <div className="max-w-2xl">
          <div className="bg-surface border border-border rounded-sm p-6">
            <StrategyEditor />
          </div>
        </div>
      )}

      {activeTab === 'queue' && (
        <div className="max-w-3xl">
          <PublishQueuePanel items={publishQueue} onRemove={handleRemoveFromQueue} />
        </div>
      )}

      {/* New Pipeline dialog */}
      <Dialog open={newPipelineOpen} onOpenChange={setNewPipelineOpen} title="New Pipeline">
        <div className="p-6">
          <StartPipelineForm
            onSuccess={(pipelineId) => {
              setNewPipelineOpen(false)
              router.push(`/content-gen/pipeline/${pipelineId}`)
            }}
          />
        </div>
      </Dialog>

      {/* Quick Script dialog */}
      <Dialog open={quickScriptOpen} onOpenChange={setQuickScriptOpen} title="Quick Script">
        <div className="p-6">
          <QuickScriptForm initialValues={quickScriptInitialValues} />
        </div>
      </Dialog>
    </>
  )
}
