'use client'

import { useEffect } from 'react'

import useContentGen from '@/hooks/useContentGen'
import { ChatThread } from '@/components/content-gen/chat-thread'

export function BacklogChatPanel() {
  const backlog = useContentGen((s) => s.backlog)
  const loadBacklog = useContentGen((s) => s.loadBacklog)

  const selectedIdeaId = backlog.find((i) => i.status === 'selected')?.idea_id ?? null

  useEffect(() => {
    if (backlog.length === 0) {
      void loadBacklog()
    }
  }, [backlog.length, loadBacklog])

  return (
    <ChatThread
      backlog={backlog}
      selectedIdeaId={selectedIdeaId}
      variant="editor"
    />
  )
}
