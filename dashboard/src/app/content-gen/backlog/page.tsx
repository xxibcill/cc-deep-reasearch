'use client'

import { useEffect } from 'react'
import { List } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { EmptyState } from '@/components/ui/empty-state'
import { BacklogPanel } from '@/components/content-gen/backlog-panel'
import useContentGen from '@/hooks/useContentGen'

export default function BacklogPage() {
  const backlog = useContentGen((s) => s.backlog)
  const backlogPath = useContentGen((s) => s.backlogPath)
  const backlogLoading = useContentGen((s) => s.backlogLoading)
  const error = useContentGen((s) => s.error)
  const loadBacklog = useContentGen((s) => s.loadBacklog)

  useEffect(() => {
    void loadBacklog()
  }, [loadBacklog])

  if (backlogLoading) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        Loading backlog...
      </div>
    )
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
    <div className="w-full max-w-5xl">
      <BacklogPanel
        items={backlog}
        backlogPath={backlogPath}
        loading={backlogLoading}
      />
    </div>
  )
}
