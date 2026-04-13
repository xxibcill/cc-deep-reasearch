'use client'

import dynamic from 'next/dynamic'

const BacklogChatPage = dynamic(
  () => import('@/components/content-gen/backlog-chat-panel').then((mod) => mod.BacklogChatPanel),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-full">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          Loading assistant...
        </div>
      </div>
    ),
  },
)

export default function ChatPage() {
  return (
    <div className="h-[calc(100vh-12rem)]">
      <BacklogChatPage />
    </div>
  )
}
