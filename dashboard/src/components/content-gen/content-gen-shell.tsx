'use client'

import { useEffect } from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { LayoutDashboard, FileText, Settings, ListVideo, ArrowLeft, ListChecks } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { buttonVariants } from '@/components/ui/button'
import { Tabs } from '@/components/ui/tabs'
import useContentGen from '@/hooks/useContentGen'
import { cn } from '@/lib/utils'

const TAB_CONFIG = [
  { value: 'overview', label: 'Overview', icon: LayoutDashboard },
  { value: 'scripts', label: 'Scripts', icon: FileText },
  { value: 'strategy', label: 'Strategy', icon: Settings },
  { value: 'queue', label: 'Queue', icon: ListVideo },
  { value: 'backlog', label: 'Backlog', icon: ListChecks },
]

export function ContentGenShell({ children }: { children: React.ReactNode }) {
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
  const isBacklogRoute = pathname.startsWith('/content-gen/backlog')
  const activeTab = isBacklogRoute ? 'backlog' : searchParams.get('tab') || 'overview'

  const activePipelineCount = pipelines.filter(
    (p) => p.status === 'running' || p.status === 'queued',
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
    router.push(`/content-gen${value === 'overview' ? '' : `?tab=${value}`}`)
  }

  return (
    <div className="mx-auto max-w-content px-page-x py-page-y">
      <section className="panel-shell rounded-[1.45rem] p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            {isPipelineDetail || isBacklogDetail ? (
              <Link
                href={isBacklogDetail ? '/content-gen/backlog' : '/content-gen'}
                className={buttonVariants({
                  variant: 'ghost',
                  size: 'sm',
                  className: 'px-2',
                })}
              >
                <ArrowLeft className="h-4 w-4" />
              </Link>
            ) : null}
            <nav>
              <Tabs
                className={cn('w-full max-w-4xl', 'md:w-auto')}
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
          <div className="mt-3 flex items-center gap-2 text-xs text-warning">
            <span className="h-1.5 w-1.5 rounded-full bg-warning animate-stage-pulse" />
            Monitoring active content runs while viewing pipeline history.
          </div>
        ) : null}
      </section>

      <main className="pt-6">{children}</main>
    </div>
  )
}
