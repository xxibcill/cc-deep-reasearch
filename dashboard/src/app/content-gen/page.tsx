'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { Play, FileText, ArrowRight } from 'lucide-react'
import useContentGen from '@/hooks/useContentGen'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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

  const renderPipelineList = ({
    title,
    description,
    items,
    statusTone,
  }: {
    title: string
    description: string
    items: typeof pipelines
    statusTone: 'active' | 'history'
  }) => (
    <Card className="rounded-[1.3rem]">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <p className="text-sm text-muted-foreground">{description}</p>
      </CardHeader>
      <CardContent className="space-y-2">
        {items.map((p) => (
          <Link
            key={p.pipeline_id}
            href={`/content-gen/pipeline/${p.pipeline_id}`}
            className="group flex items-center justify-between rounded-[1rem] border border-border/75 bg-surface/62 px-4 py-3 transition-all hover:-translate-y-px hover:border-warning/30 hover:bg-surface-raised/72"
          >
            <div className="flex min-w-0 items-center gap-3">
              <span
                className={`h-2 w-2 shrink-0 rounded-full ${
                  statusTone === 'active'
                    ? 'bg-warning animate-stage-pulse'
                    : p.status === 'completed'
                      ? 'bg-success/70'
                      : 'bg-error/70'
                }`}
              />
              <span
                className={`truncate text-sm ${statusTone === 'active' ? 'font-medium text-foreground' : 'text-foreground/75'}`}
              >
                {p.theme}
              </span>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <span
                className={`text-[11px] font-mono tabular-nums ${
                  statusTone === 'active' ? 'text-warning' : 'text-muted-foreground'
                }`}
              >
                {statusTone === 'active'
                  ? `${String(p.current_stage + 1).padStart(2, '0')}/12`
                  : p.status}
              </span>
              <ArrowRight className="h-3.5 w-3.5 text-muted-foreground transition-colors group-hover:text-warning" />
            </div>
          </Link>
        ))}
      </CardContent>
    </Card>
  )

  // Overview tab content
  const renderOverview = () => (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-6">
      <div className="space-y-6">
        <Card className="overflow-hidden rounded-[1.35rem]">
          <CardHeader className="gap-5 border-b border-border/70 bg-[linear-gradient(135deg,rgba(217,130,60,0.16),rgba(13,44,45,0.08))]">
            <p className="eyebrow">Entry points</p>
            <div className="space-y-2">
              <CardTitle className="text-[2.3rem]">Start from a strong entry point</CardTitle>
              <p className="text-sm text-muted-foreground">
                Launch a full pipeline when you need the end-to-end workflow, or open a quick
                script when you want to iterate on a single idea immediately.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
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
          </CardHeader>
        </Card>

        {error && (
          <Alert variant="destructive">
            <AlertTitle>Content studio error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {activePipelines.length > 0 && (
          renderPipelineList({
            title: 'Active Pipelines',
            description: 'Runs that are still moving through the 12-stage production flow.',
            items: activePipelines,
            statusTone: 'active',
          })
        )}

        {pastPipelines.length > 0 && (
          renderPipelineList({
            title: 'Past Pipelines',
            description: 'Completed, failed, and cancelled runs that are ready for review or reuse.',
            items: pastPipelines,
            statusTone: 'history',
          })
        )}

        {activePipelines.length === 0 && pastPipelines.length === 0 && (
          <Card className="rounded-[1.3rem] border-dashed">
            <CardContent className="flex flex-col items-center justify-center gap-4 py-16 text-center">
              <div className="space-y-1">
                <p className="text-base font-medium text-foreground">No pipelines yet</p>
                <p className="text-sm text-muted-foreground">
                  Start a full production run or open a quick script to seed the workspace.
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setNewPipelineOpen(true)}
                className="gap-2 text-warning hover:bg-warning/10 hover:text-warning"
              >
                Start your first pipeline
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </CardContent>
          </Card>
        )}
      </div>

      <OverviewSidebar onTabChange={handleTabChange} />
    </div>
  )

  return (
    <>
      {activeTab === 'overview' && renderOverview()}

      {activeTab === 'scripts' && (
        <div className="w-full">
          <ScriptsPanel onReuseInputs={openQuickScriptFromHistory} />
        </div>
      )}

      {activeTab === 'strategy' && (
        <div className="max-w-2xl">
          <Card className="rounded-[1.3rem]">
            <CardContent className="p-6">
              <StrategyEditor />
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'queue' && (
        <div className="max-w-3xl">
          <PublishQueuePanel items={publishQueue} onRemove={handleRemoveFromQueue} />
        </div>
      )}

      <Dialog open={newPipelineOpen} onOpenChange={setNewPipelineOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New Pipeline</DialogTitle>
            <DialogDescription>
              Set the theme and launch a new end-to-end content generation run.
            </DialogDescription>
          </DialogHeader>
          <DialogBody>
            <StartPipelineForm
              onSuccess={(pipelineId) => {
                setNewPipelineOpen(false)
                router.push(`/content-gen/pipeline/${pipelineId}`)
              }}
            />
          </DialogBody>
        </DialogContent>
      </Dialog>

      <Dialog open={quickScriptOpen} onOpenChange={setQuickScriptOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Quick Script</DialogTitle>
            <DialogDescription>
              Capture a single idea, generate copy quickly, and feed the result back into the
              broader studio workflow.
            </DialogDescription>
          </DialogHeader>
          <DialogBody>
            <QuickScriptForm initialValues={quickScriptInitialValues} />
          </DialogBody>
        </DialogContent>
      </Dialog>
    </>
  )
}
