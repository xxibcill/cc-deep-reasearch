'use client'

import { useEffect, useState } from 'react'
import dynamic from 'next/dynamic'
import { List, Sparkles } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { EmptyState } from '@/components/ui/empty-state'
import { Button } from '@/components/ui/button'
import useContentGen from '@/hooks/useContentGen'

const BacklogPanel = dynamic(
  () => import('@/components/content-gen/backlog-panel').then((mod) => mod.BacklogPanel),
  {
    ssr: false,
    loading: () => (
      <div className="py-8 text-center text-sm text-muted-foreground">Loading backlog…</div>
    ),
  },
)

const TriageWorkspace = dynamic(
  () => import('@/components/content-gen/triage-workspace').then((mod) => mod.TriageWorkspace),
  {
    ssr: false,
    loading: () => (
      <div className="py-8 text-center text-sm text-muted-foreground">Loading triage workspace…</div>
    ),
  },
)

export default function BacklogPage() {
  const backlog = useContentGen((s) => s.backlog)
  const backlogPath = useContentGen((s) => s.backlogPath)
  const backlogLoading = useContentGen((s) => s.backlogLoading)
  const error = useContentGen((s) => s.error)
  const loadBacklog = useContentGen((s) => s.loadBacklog)
  const createBacklogItem = useContentGen((s) => s.createBacklogItem)
  const updateBacklogItem = useContentGen((s) => s.updateBacklogItem)
  const selectBacklogItem = useContentGen((s) => s.selectBacklogItem)
  const archiveBacklogItem = useContentGen((s) => s.archiveBacklogItem)
  const deleteBacklogItem = useContentGen((s) => s.deleteBacklogItem)
  const startBacklogItem = useContentGen((s) => s.startBacklogItem)

  const [triageMode, setTriageMode] = useState(false)

  useEffect(() => {
    if (backlog.length === 0) {
      void loadBacklog()
    }
  }, [backlog.length, loadBacklog])

  if (backlogLoading) {
    return <div className="py-8 text-center text-sm text-muted-foreground">Loading backlog...</div>
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Backlog load error</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  if (backlog.length === 0) {
    return (
      <div className="flex flex-col gap-4 lg:flex-row lg:gap-6 lg:items-start">
        <div className="flex-1">
          <EmptyState
            icon={List}
            title="No backlog items yet"
            description="Chat with the assistant to create your first item, or items will appear here once added through the research workflow."
          />
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:gap-6 lg:items-start">
      {triageMode ? (
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setTriageMode(false)}
                className="gap-1.5 h-8"
              >
                <List className="h-3.5 w-3.5" />
                Back to backlog
              </Button>
            </div>
          </div>
          <TriageWorkspace onClose={() => setTriageMode(false)} />
        </div>
      ) : (
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-4">
            <div />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setTriageMode(true)}
              className="gap-1.5 h-8"
            >
              <Sparkles className="h-3.5 w-3.5" />
              AI Triage
            </Button>
          </div>
          <BacklogPanel
            items={backlog}
            backlogPath={backlogPath}
            loading={backlogLoading}
            onUpdateStatus={updateBacklogItem}
            onEdit={updateBacklogItem}
            onSelect={selectBacklogItem}
            onArchive={archiveBacklogItem}
            onDelete={deleteBacklogItem}
            onCreate={createBacklogItem}
            onStartProduction={startBacklogItem}
          />
        </div>
      )}
    </div>
  )
}
