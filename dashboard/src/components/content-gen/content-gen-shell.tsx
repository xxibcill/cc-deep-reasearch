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

  const loadAll = useContentGen((s) => s.loadAll)
  const pipelines = useContentGen((s) => s.pipelines)
  const scripts = useContentGen((s) => s.scripts)
  const publishQueue = useContentGen((s) => s.publishQueue)

  const isPipelineDetail = pathname.match(/\/content-gen\/pipeline\/[^/]+$/)
  const activeTab = searchParams.get('tab') || 'overview'

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
    loadAll()
  }, [loadAll])

  const handleTabChange = (value: string) => {
    if (value === 'backlog') {
      router.push('/content-gen/backlog')
      return
    }
    router.push(`/content-gen${value === 'overview' ? '' : `?tab=${value}`}`)
  }

  return (
    <div className="mx-auto max-w-content px-page-x py-page-y">
      <section className="panel-shell rounded-[1.45rem] p-6">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              {isPipelineDetail ? (
                <Link
                  href="/content-gen"
                  className={buttonVariants({
                    variant: 'ghost',
                    size: 'sm',
                    className: 'px-3',
                  })}
                >
                  <ArrowLeft className="h-4 w-4" />
                  Back
                </Link>
              ) : null}
              <p className="eyebrow">Content production workspace</p>
            </div>
            <div className="space-y-3">
              <h1 className="font-display text-[2.8rem] font-semibold uppercase tracking-[0.02em] text-foreground">
                Content Studio
              </h1>
              <p className=" text-sm leading-6 text-muted-foreground">
                Editorial planning, scripting, quality control, and publish queue visibility in one
                operational surface.
              </p>
            </div>
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
              <Badge variant="outline">{scripts.length} scripts tracked</Badge>
            ) : null}
            {publishQueue.length > 0 ? (
              <Badge variant="outline">{publishQueue.length} queued for publish</Badge>
            ) : null}
          </div>
        </div>

        {!isPipelineDetail ? (
          <nav className="mt-5">
            <Tabs
              className={cn('w-full max-w-4xl', 'md:w-auto')}
              value={activeTab}
              onValueChange={handleTabChange}
              tabs={tabsWithBadges}
              stretch
            />
          </nav>
        ) : null}

        {isPipelineDetail && activePipelineCount > 0 ? (
          <div className="mt-4 flex items-center gap-2 text-xs text-warning">
            <span className="h-1.5 w-1.5 rounded-full bg-warning animate-stage-pulse" />
            Monitoring active content runs while viewing pipeline history.
          </div>
        ) : null}
      </section>

      <main className="pt-8">{children}</main>
    </div>
  )
}
