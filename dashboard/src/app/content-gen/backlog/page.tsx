'use client'

import { useEffect } from 'react'
import dynamic from 'next/dynamic'
import { List } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { EmptyState } from '@/components/ui/empty-state'
import useContentGen from '@/hooks/useContentGen'

const BacklogPanel = dynamic(
  () => import('@/components/content-gen/backlog-panel').then((mod) => mod.BacklogPanel),
  {
    ssr: false,
    loading: () => <div className="py-8 text-center text-sm text-muted-foreground">Loading backlog…</div>,
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
      <EmptyState
        icon={List}
        title="No backlog items yet"
        description="The persistent backlog is empty. Items will appear here once they are added through the research workflow."
      />
    )
  }

  return (
    <div className="w-full">
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
      />
    </div>
  )
}
