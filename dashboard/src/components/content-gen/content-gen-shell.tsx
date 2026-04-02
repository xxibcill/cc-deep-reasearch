'use client'

import { useEffect } from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { LayoutDashboard, FileText, Settings, ListVideo, ArrowLeft } from 'lucide-react'
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
]

export function ContentGenShell({
  children,
}: {
  children: React.ReactNode
}) {
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
    (p) => p.status === 'running' || p.status === 'queued'
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
    router.push(`/content-gen${value === 'overview' ? '' : `?tab=${value}`}`)
  }

  return (
    <div>
      <div className="border-b bg-background">
        <div className="mx-auto max-w-content px-page-x py-3">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-3">
              {isPipelineDetail && (
                <Link
                  href="/content-gen"
                  className={buttonVariants({
                    variant: 'ghost',
                    size: 'sm',
                    className: '-ml-2 gap-2 px-2 text-muted-foreground',
                  })}
                >
                  <ArrowLeft className="h-4 w-4" />
                  Back
                </Link>
              )}
              <p className="text-sm text-muted-foreground">
                Editorial planning, scripting, and publishing workflows.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {activePipelineCount > 0 ? (
                <Badge variant="warning">
                  {activePipelineCount} active pipeline{activePipelineCount === 1 ? '' : 's'}
                </Badge>
              ) : (
                <Badge variant="secondary">No active pipelines</Badge>
              )}
            </div>
          </div>
          {!isPipelineDetail && (
            <nav className="mt-3">
              <Tabs
                className={cn('w-full max-w-3xl', 'md:w-auto')}
                value={activeTab}
                onValueChange={handleTabChange}
                tabs={tabsWithBadges}
                stretch
              />
            </nav>
          )}
          {isPipelineDetail && activePipelineCount > 0 && (
            <div className="mt-2 flex items-center gap-2 text-xs text-warning">
              <span className="h-1.5 w-1.5 rounded-full bg-warning animate-stage-pulse" />
              Monitoring active content runs while viewing pipeline history.
            </div>
          )}
        </div>
      </div>
      <main className="mx-auto max-w-content px-page-x py-page-y">
        {children}
      </main>
    </div>
  )
}
