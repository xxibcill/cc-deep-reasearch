'use client'

import { useEffect } from 'react'
import dynamic from 'next/dynamic'
import { List } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { EmptyState } from '@/components/ui/empty-state'
import useContentGen from '@/hooks/useContentGen'
import { BacklogChatPanel } from '@/components/content-gen/backlog-chat-panel'

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

  const handleItemsChanged = () => {
    void loadBacklog()
  }

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
        {/* Chat panel takes full width on mobile, wider on desktop */}
        <div className="w-full lg:w-[26rem] lg:shrink-0">
          <div className="rounded-[1.15rem] border border-border/75 bg-card/62 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
            <BacklogChatPanel
              items={[]}
              selectedIdeaId={null}
              onItemsChanged={handleItemsChanged}
            />
          </div>
        </div>
        {/* Empty state for backlog alongside chat */}
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
      {/* Chat panel — narrower on desktop */}
      <div className="w-full lg:w-[26rem] lg:shrink-0">
        <div className="sticky top-4 rounded-[1.15rem] border border-border/75 bg-card/62 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
          <BacklogChatPanel
            items={backlog}
            selectedIdeaId={backlog.find((i) => i.status === 'selected')?.idea_id ?? null}
            onItemsChanged={handleItemsChanged}
          />
        </div>
      </div>

      {/* Backlog panel */}
      <div className="flex-1 min-w-0">
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
    </div>
  )
}