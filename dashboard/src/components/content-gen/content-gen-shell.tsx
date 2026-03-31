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
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur-sm">
        <div className="mx-auto max-w-[1400px] px-4 py-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-2">
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
                <div className="space-y-1">
                  <h1 className="text-sm font-display font-semibold tracking-tight text-foreground">
                    Content Studio
                  </h1>
                  <p className="text-sm text-muted-foreground">
                    Editorial planning, scripting, and publishing workflows in one workspace.
                  </p>
                </div>
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
            </div>
          </div>
          {!isPipelineDetail && (
            <nav className="mt-4">
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
            <div className="mt-3 flex items-center gap-2 text-xs text-warning">
              <span className="h-1.5 w-1.5 rounded-full bg-warning animate-stage-pulse" />
              Monitoring active content runs while viewing pipeline history.
            </div>
          )}
        </div>
      </header>
      <main className="max-w-[1400px] mx-auto px-4 py-6">
        {children}
      </main>
    </div>
  )
}
