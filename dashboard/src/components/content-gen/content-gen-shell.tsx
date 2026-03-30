'use client'

import { useEffect } from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { LayoutDashboard, FileText, Settings, ListVideo, ArrowLeft } from 'lucide-react'
import { Tabs } from '@/components/ui/tabs'
import useContentGen from '@/hooks/useContentGen'

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
      <header className="sticky top-0 z-40 bg-background/95 backdrop-blur-sm border-b border-border">
        <div className="max-w-[1400px] mx-auto px-4">
          <div className="flex items-center justify-between h-12">
            <div className="flex items-center gap-3">
              {isPipelineDetail && (
                <Link
                  href="/content-gen"
                  className="text-muted-foreground hover:text-foreground transition-colors p-1 -ml-1"
                >
                  <ArrowLeft className="h-4 w-4" />
                </Link>
              )}
              <h1 className="text-sm font-display font-semibold tracking-tight text-foreground">
                Content Studio
              </h1>
            </div>
            {isPipelineDetail && activePipelineCount > 0 && (
              <span className="flex items-center gap-1.5 text-xs font-mono text-warning">
                <span className="w-1.5 h-1.5 rounded-full bg-warning animate-stage-pulse" />
                {activePipelineCount} active
              </span>
            )}
          </div>
          {!isPipelineDetail && (
            <nav className="pb-2">
              <Tabs
                value={activeTab}
                onValueChange={handleTabChange}
                tabs={tabsWithBadges}
                stretch
              />
            </nav>
          )}
        </div>
      </header>
      <main className="max-w-[1400px] mx-auto px-4 py-6">
        {children}
      </main>
    </div>
  )
}
