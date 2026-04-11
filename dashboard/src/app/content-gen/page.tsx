'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { Play, FileText, ArrowRight, Link2, X } from 'lucide-react'
import useContentGen from '@/hooks/useContentGen'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
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
import { BacklogPanel } from '@/components/content-gen/backlog-panel'
import { PublishQueuePanel } from '@/components/content-gen/publish-queue-panel'
import { OverviewSidebar } from '@/components/content-gen/overview-sidebar'
import { EmptyState } from '@/components/ui/empty-state'
import {
  createEmptyQuickScriptFields,
  parseQuickScriptPrompt,
  type QuickScriptFields,
} from '@/lib/quick-script'
import {
  buildPipelineThemeFromResearch,
  buildQuickScriptFieldsFromResearch,
  buildResearchContentBridgeFromSearchParams,
  clearResearchContentBridge,
  formatResearchBridgeSource,
  parseContentStudioIntent,
  readResearchContentBridge,
  type ResearchContentBridgePayload,
} from '@/lib/research-content-bridge'
import { TOTAL_PIPELINE_STAGES } from '@/types/content-gen'

export default function ContentGenPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const activeTab = searchParams.get('tab') || 'overview'

  const pipelines = useContentGen((s) => s.pipelines)
  const activePipelineId = useContentGen((s) => s.activePipelineId)
  const pipelineContext = useContentGen((s) => s.pipelineContext)
  const publishQueue = useContentGen((s) => s.publishQueue)
  const backlog = useContentGen((s) => s.backlog)
  const backlogPath = useContentGen((s) => s.backlogPath)
  const backlogLoading = useContentGen((s) => s.backlogLoading)
  const loadAll = useContentGen((s) => s.loadAll)
  const removeFromQueue = useContentGen((s) => s.removeFromQueue)
  const updateBacklogItem = useContentGen((s) => s.updateBacklogItem)
  const selectBacklogItem = useContentGen((s) => s.selectBacklogItem)
  const archiveBacklogItem = useContentGen((s) => s.archiveBacklogItem)
  const deleteBacklogItem = useContentGen((s) => s.deleteBacklogItem)
  const createBacklogItem = useContentGen((s) => s.createBacklogItem)
  const error = useContentGen((s) => s.error)

  const [newPipelineOpen, setNewPipelineOpen] = useState(false)
  const [quickScriptOpen, setQuickScriptOpen] = useState(false)
  const [researchBridge, setResearchBridge] = useState<ResearchContentBridgePayload | null>(null)
  const [pipelineInitialTheme, setPipelineInitialTheme] = useState('')
  const [quickScriptInitialValues, setQuickScriptInitialValues] = useState<QuickScriptFields>(() =>
    createEmptyQuickScriptFields(),
  )

  useEffect(() => {
    void loadAll()
  }, [loadAll])

  useEffect(() => {
    const sourceSessionId = searchParams.get('sourceSession')
    const sourceBridge = sourceSessionId
      ? (readResearchContentBridge(sourceSessionId) ??
        buildResearchContentBridgeFromSearchParams(searchParams))
      : null

    setResearchBridge(sourceBridge)
    setPipelineInitialTheme(sourceBridge ? buildPipelineThemeFromResearch(sourceBridge) : '')
    setQuickScriptInitialValues(
      sourceBridge
        ? {
            ...createEmptyQuickScriptFields(),
            ...buildQuickScriptFieldsFromResearch(sourceBridge),
          }
        : createEmptyQuickScriptFields(),
    )

    const intent = parseContentStudioIntent(searchParams.get('intent'))

    if (intent === 'pipeline') {
      setNewPipelineOpen(true)
    }

    if (intent === 'quick-script') {
      setQuickScriptOpen(true)
    }

    if (!intent) {
      return
    }

    const nextParams = new URLSearchParams(searchParams.toString())
    nextParams.delete('intent')
    const nextHref = nextParams.toString() ? `/content-gen?${nextParams}` : '/content-gen'
    router.replace(nextHref)
  }, [router, searchParams])

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

  const dismissResearchBridge = () => {
    clearResearchContentBridge()
    setResearchBridge(null)
    setPipelineInitialTheme('')
    setQuickScriptInitialValues(createEmptyQuickScriptFields())

    const nextParams = new URLSearchParams(searchParams.toString())
    nextParams.delete('sourceSession')
    nextParams.delete('sourceLabel')
    nextParams.delete('source')
    nextParams.delete('reportReady')
    const nextHref = nextParams.toString() ? `/content-gen?${nextParams}` : '/content-gen'
    router.replace(nextHref)
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
                  ? `${String(p.current_stage + 1).padStart(2, '0')}/${TOTAL_PIPELINE_STAGES}`
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
        {researchBridge ? (
          <Card className="overflow-hidden rounded-[1.35rem] border-primary/25">
            <CardHeader className="gap-4 border-b border-border/70 bg-[linear-gradient(135deg,rgba(217,130,60,0.16),rgba(13,44,45,0.08))]">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="success">Research attached</Badge>
                    <Badge variant="outline">
                      {formatResearchBridgeSource(researchBridge.source)}
                    </Badge>
                    <Badge variant="outline" className="font-mono text-[0.7rem]">
                      {researchBridge.sessionId.slice(0, 8)}
                    </Badge>
                  </div>
                  <div className="space-y-2">
                    <CardTitle className="text-[2rem]">
                      Research is ready for downstream work
                    </CardTitle>
                    <p className="text-sm leading-6 text-muted-foreground">
                      {researchBridge.sessionLabel} is attached to this studio session. Launch a
                      pipeline for a full production pass or open a quick script for a faster reuse
                      loop.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <Button
                      type="button"
                      onClick={() => setNewPipelineOpen(true)}
                      className="gap-2 bg-warning text-background hover:bg-warning/90"
                    >
                      <Play className="h-4 w-4" />
                      Start from Research
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setQuickScriptOpen(true)}
                      className="gap-2"
                    >
                      <FileText className="h-4 w-4" />
                      Open Research Script
                    </Button>
                  </div>
                </div>
                <div className="flex flex-col gap-2 lg:items-end">
                  <Link
                    href={`/session/${researchBridge.sessionId}`}
                    className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-muted-foreground transition-colors hover:text-foreground"
                  >
                    <Link2 className="h-3.5 w-3.5" />
                    Open source session
                  </Link>
                  <Button type="button" variant="ghost" size="sm" onClick={dismissResearchBridge}>
                    <X className="h-3.5 w-3.5" />
                    Clear handoff
                  </Button>
                </div>
              </div>
            </CardHeader>
          </Card>
        ) : null}

        <Card className="overflow-hidden rounded-[1.35rem]">
          <CardHeader className="gap-5 border-b border-border/70 bg-[linear-gradient(135deg,rgba(217,130,60,0.16),rgba(13,44,45,0.08))]">
            <p className="eyebrow">Entry points</p>
            <div className="space-y-2">
              <CardTitle className="text-[2.3rem]">
                {researchBridge
                  ? 'Start from attached research'
                  : 'Start from a strong entry point'}
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                {researchBridge
                  ? 'The launch controls below are prepped for the imported session, but you can still overwrite everything and run the studio independently.'
                  : 'Launch a full pipeline when you need the end-to-end workflow, or open a quick script when you want to iterate on a single idea immediately.'}
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
                onClick={researchBridge ? () => setQuickScriptOpen(true) : openQuickScriptBlank}
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
            <AlertTitle>Studio load error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {activePipelines.length > 0 &&
          renderPipelineList({
            title: 'Active Pipelines',
            description: `Runs that are still moving through the ${TOTAL_PIPELINE_STAGES}-stage production flow.`,
            items: activePipelines,
            statusTone: 'active',
          })}

        {pastPipelines.length > 0 &&
          renderPipelineList({
            title: 'Past Pipelines',
            description:
              'Completed, failed, and cancelled runs that are ready for review or reuse.',
            items: pastPipelines,
            statusTone: 'history',
          })}

        {activePipelines.length === 0 && pastPipelines.length === 0 && (
          <EmptyState
            icon={Play}
            title="No pipelines yet"
            description="Start a full production run or open a quick script to seed the workspace."
            action={
              <Button
                type="button"
                variant="ghost"
                onClick={() => setNewPipelineOpen(true)}
                className="gap-2 text-warning hover:bg-warning/10 hover:text-warning"
              >
                Start your first pipeline
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            }
          />
        )}
      </div>

      <OverviewSidebar onTabChange={handleTabChange} researchBridge={researchBridge} />
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

      {activeTab === 'backlog' && (
        <div className="w-full">
          <BacklogPanel
            items={backlog}
            backlogPath={backlogPath}
            loading={backlogLoading}
            onUpdateStatus={updateBacklogItem}
            onSelect={selectBacklogItem}
            onArchive={archiveBacklogItem}
            onDelete={deleteBacklogItem}
            onCreate={createBacklogItem}
          />
        </div>
      )}

      {activeTab === 'queue' && (
        <div className="">
          <PublishQueuePanel items={publishQueue} onRemove={handleRemoveFromQueue} />
        </div>
      )}

      <Dialog open={newPipelineOpen} onOpenChange={setNewPipelineOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New Pipeline</DialogTitle>
            <DialogDescription>
              {researchBridge
                ? `Seeded from ${researchBridge.sessionLabel}. Adjust the theme or stage range before launching the run.`
                : 'Set the theme and launch a new end-to-end content generation run.'}
            </DialogDescription>
          </DialogHeader>
          <DialogBody>
            <StartPipelineForm
              initialTheme={pipelineInitialTheme}
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
              {researchBridge
                ? `Seeded from ${researchBridge.sessionLabel}. The imported research notes are editable before you generate copy.`
                : 'Capture a single idea, generate copy quickly, and feed the result back into the broader studio workflow.'}
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
