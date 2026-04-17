'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import {
  ArrowLeft,
  FileText,
  FileTextIcon,
  LayoutDashboard,
  ListChecks,
  ListVideo,
  MessageSquare,
  Settings,
} from 'lucide-react'

import useContentGen from '@/hooks/useContentGen'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { buttonVariants } from '@/components/ui/button'
import { Tabs } from '@/components/ui/tabs'

const TAB_CONFIG = [
  { value: 'overview', label: 'Overview', icon: LayoutDashboard },
  { value: 'scripts', label: 'Scripts', icon: FileText },
  { value: 'briefs', label: 'Briefs', icon: FileTextIcon },
  { value: 'strategy', label: 'Strategy', icon: Settings },
  { value: 'queue', label: 'Queue', icon: ListVideo },
  { value: 'backlog', label: 'Backlog', icon: ListChecks },
  { value: 'chat', label: 'Assistant', icon: MessageSquare },
]

export function ContentGenNavigation() {
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()

  const loadPipelines = useContentGen((s) => s.loadPipelines)
  const loadScripts = useContentGen((s) => s.loadScripts)
  const loadPublishQueue = useContentGen((s) => s.loadPublishQueue)
  const pipelines = useContentGen((s) => s.pipelines)
  const scripts = useContentGen((s) => s.scripts)
  const publishQueue = useContentGen((s) => s.publishQueue)

  const isPipelineDetail = pathname.match(/\/content-gen\/pipeline\/[^/]+$/)
  const isBacklogDetail = pathname.match(/\/content-gen\/backlog\/[^/]+$/)
  const isBriefDetail = pathname.match(/\/content-gen\/briefs\/[^/]+$/)
  const isBacklogRoute = pathname.startsWith('/content-gen/backlog')
  const isBriefsRoute = pathname.startsWith('/content-gen/briefs')
  const isChatRoute = pathname.startsWith('/content-gen/chat')
  const activeTab = isBacklogRoute
    ? 'backlog'
    : isBriefsRoute
      ? 'briefs'
      : isChatRoute
        ? 'chat'
        : searchParams.get('tab') || 'overview'

  const activePipelineCount = pipelines.filter(
    (pipeline) => pipeline.status === 'running' || pipeline.status === 'queued',
  ).length

  const tabsWithBadges = TAB_CONFIG.map((tab) => {
    if (tab.value === 'overview' && activePipelineCount > 0) {
      return { ...tab, badge: activePipelineCount }
    }
    if (tab.value === 'scripts' && scripts.length > 0) {
      return { ...tab, badge: scripts.length }
    }
    if (tab.value === 'queue' && publishQueue.length > 0) {
      return { ...tab, badge: publishQueue.length }
    }
    return tab
  })

  useEffect(() => {
    void Promise.allSettled([
      loadPipelines(),
      loadScripts(),
      loadPublishQueue(),
    ])
  }, [loadPipelines, loadPublishQueue, loadScripts])

  const handleTabChange = (value: string) => {
    if (value === 'backlog') {
      router.push('/content-gen/backlog')
      return
    }
    if (value === 'briefs') {
      router.push('/content-gen/briefs')
      return
    }
    if (value === 'chat') {
      router.push('/content-gen/chat')
      return
    }
    router.push(`/content-gen${value === 'overview' ? '' : `?tab=${value}`}`)
  }

  return (
    <div className="flex flex-col gap-3 border-t border-border/60 pt-4">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          {isPipelineDetail || isBacklogDetail || isBriefDetail ? (
            <Link
              href={
                isBacklogDetail
                  ? '/content-gen/backlog'
                  : isBriefDetail
                    ? '/content-gen/briefs'
                    : '/content-gen'
              }
              className={buttonVariants({
                variant: 'ghost',
                size: 'sm',
                className: 'px-2',
              })}
            >
              <ArrowLeft className="h-4 w-4" />
            </Link>
          ) : null}
          <nav aria-label="Content studio sections">
            <Tabs
              className={cn('w-full max-w-4xl md:w-auto')}
              value={activeTab}
              onValueChange={handleTabChange}
              tabs={tabsWithBadges}
            />
          </nav>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {activePipelineCount > 0 ? (
            <Badge variant="warning">
              {activePipelineCount} active pipeline{activePipelineCount === 1 ? '' : 's'}
            </Badge>
          ) : (
            <Badge variant="secondary">No active pipelines</Badge>
          )}
          {scripts.length > 0 ? (
            <Badge variant="outline">{scripts.length} scripts</Badge>
          ) : null}
          {publishQueue.length > 0 ? (
            <Badge variant="outline">{publishQueue.length} queued</Badge>
          ) : null}
        </div>
      </div>

      {isPipelineDetail && activePipelineCount > 0 ? (
        <div className="flex items-center gap-2 text-xs text-warning">
          <span className="h-1.5 w-1.5 animate-stage-pulse rounded-full bg-warning" />
          Monitoring active content runs while viewing pipeline history.
        </div>
      ) : null}
    </div>
  )
}
