'use client'

import { useEffect } from 'react'

import { useBacklog } from '@/hooks/useBacklog'
import { ChatThread } from '@/components/content-gen/chat-thread'

export function BacklogChatPanel() {
  const backlog = useBacklog((s) => s.backlog)
  const loadBacklog = useBacklog((s) => s.loadBacklog)

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
