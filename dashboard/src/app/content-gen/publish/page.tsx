'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import useContentGen from '@/hooks/useContentGen'
import { PublishQueuePanel } from '@/components/content-gen/publish-queue-panel'

export default function PublishPage() {
  const publishQueue = useContentGen((s) => s.publishQueue)
  const loadPublishQueue = useContentGen((s) => s.loadPublishQueue)
  const removeFromQueue = useContentGen((s) => s.removeFromQueue)
  const loading = useContentGen((s) => s.publishQueueLoading)

  useEffect(() => {
    loadPublishQueue()
  }, [loadPublishQueue])

  const handleRemove = async (ideaId: string, platform: string) => {
    await removeFromQueue(ideaId, platform)
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href="/content-gen"
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-xl font-bold">Publish Queue</h1>
          <p className="text-sm text-muted-foreground">
            Manage scheduled content for publishing
          </p>
        </div>
      </div>

      <PublishQueuePanel
        items={publishQueue}
        loading={loading}
        onRemove={handleRemove}
      />
    </div>
  )
}
