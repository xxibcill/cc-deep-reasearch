'use client'

import { useEffect } from 'react'
import dynamic from 'next/dynamic'
import Link from 'next/link'
import { List, Sparkles } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { EmptyState } from '@/components/ui/empty-state'
import { Button } from '@/components/ui/button'
import { useBacklog } from '@/hooks/useBacklog'

const BacklogPanel = dynamic(
  () => import('@/components/content-gen/backlog-panel').then((mod) => mod.BacklogPanel),
  {
    ssr: false,
    loading: () => (
      <div className="py-8 text-center text-sm text-muted-foreground">Loading backlog…</div>
    ),
  },
)

export default function BacklogPage() {
  const backlog = useBacklog((s) => s.backlog)
  const backlogPath = useBacklog((s) => s.backlogPath)
  const backlogLoading = useBacklog((s) => s.backlogLoading)
  const error = useBacklog((s) => s.error)
  const loadBacklog = useBacklog((s) => s.loadBacklog)
  const createBacklogItem = useBacklog((s) => s.createBacklogItem)
  const updateBacklogItem = useBacklog((s) => s.updateBacklogItem)
  const selectBacklogItem = useBacklog((s) => s.selectBacklogItem)
  const archiveBacklogItem = useBacklog((s) => s.archiveBacklogItem)
  const deleteBacklogItem = useBacklog((s) => s.deleteBacklogItem)
  const startBacklogItem = useBacklog((s) => s.startBacklogItem)

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
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-4">
          <div />
          <Link href="/content-gen/triage">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-1.5 h-8"
            >
              <Sparkles className="h-3.5 w-3.5" />
              AI Triage
            </Button>
          </Link>
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
    </div>
  )
}
