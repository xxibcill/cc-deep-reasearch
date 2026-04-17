'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import {
  ArrowLeft,
  ChevronDown,
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
  const containerRef = useRef<HTMLDivElement>(null)
  const [isOpen, setIsOpen] = useState(false)

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
  const activeTabConfig = TAB_CONFIG.find((tab) => tab.value === activeTab) ?? TAB_CONFIG[0]
  const backHref = isBacklogDetail
    ? '/content-gen/backlog'
    : isBriefDetail
      ? '/content-gen/briefs'
      : isPipelineDetail
        ? '/content-gen'
        : null
  const currentSectionLabel = isPipelineDetail
    ? 'Pipeline detail'
    : isBacklogDetail
      ? 'Backlog item'
      : isBriefDetail
        ? 'Brief detail'
        : activeTabConfig.label
  const routeSignature = useMemo(
    () => `${pathname}?${searchParams.toString()}`,
    [pathname, searchParams],
  )

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

  useEffect(() => {
    setIsOpen(false)
  }, [routeSignature])

  useEffect(() => {
    if (!isOpen) {
      return
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target
      if (!(target instanceof Node)) {
        return
      }
      if (!containerRef.current?.contains(target)) {
        setIsOpen(false)
      }
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false)
      }
    }

    window.addEventListener('mousedown', handlePointerDown)
    window.addEventListener('keydown', handleKeyDown)

    return () => {
      window.removeEventListener('mousedown', handlePointerDown)
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen])

  const handleTabChange = (value: string) => {
    setIsOpen(false)
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
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        className="inline-flex h-10 items-center gap-2 rounded-[0.9rem] border border-border/70 bg-surface/62 px-2.5 text-sm text-muted-foreground transition-all duration-200 hover:border-primary/35 hover:bg-surface-raised/78 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45 sm:px-3"
        aria-expanded={isOpen}
        aria-controls="content-gen-sections-panel"
      >
        <LayoutDashboard className="h-4 w-4 shrink-0 text-primary" />
        <span className="hidden sm:inline text-foreground">Studio</span>
        <span className="hidden max-w-[8rem] truncate text-[0.78rem] text-muted-foreground lg:inline">
          {currentSectionLabel}
        </span>
        {activePipelineCount > 0 ? (
          <span className="inline-flex min-w-5 items-center justify-center rounded-full bg-warning-muted px-1.5 py-0.5 text-[0.65rem] font-mono uppercase tracking-[0.12em] text-warning">
            {activePipelineCount}
          </span>
        ) : null}
        <ChevronDown
          className={cn(
            'hidden h-3.5 w-3.5 shrink-0 transition-transform duration-200 sm:block',
            isOpen && 'rotate-180',
          )}
        />
      </button>

      <div
        id="content-gen-sections-panel"
        className={cn(
          'pointer-events-none absolute right-0 top-full z-[70] mt-2 w-[min(46rem,calc(100vw-2rem))] max-w-[calc(100vw-2rem)] origin-top-right transition-all duration-180',
          isOpen ? 'translate-y-0 opacity-100' : 'translate-y-1.5 opacity-0',
        )}
      >
        <div
          className={cn(
            'overflow-hidden rounded-[1.1rem] border border-border/70 bg-popover/96 shadow-panel backdrop-blur-xl',
            isOpen ? 'pointer-events-auto' : 'pointer-events-none',
          )}
        >
          <div className="flex flex-col gap-3 border-b border-border/60 px-4 py-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="text-[0.65rem] font-medium uppercase tracking-[0.18em] text-muted-foreground">
                Content Studio
              </div>
              <div className="mt-1 flex min-w-0 items-center gap-2">
                <span className="truncate text-sm font-medium text-foreground">
                  {currentSectionLabel}
                </span>
                {backHref ? (
                  <Link
                    href={backHref}
                    className={buttonVariants({
                      variant: 'ghost',
                      size: 'sm',
                      className: 'h-7 px-2 text-[0.68rem]',
                    })}
                    onClick={() => setIsOpen(false)}
                  >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    Back
                  </Link>
                ) : null}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 sm:justify-end">
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

          <div className="px-4 py-4">
            <nav aria-label="Content studio sections">
              <Tabs
                className={cn('w-full max-w-4xl md:w-auto')}
                value={activeTab}
                onValueChange={handleTabChange}
                tabs={tabsWithBadges}
              />
            </nav>

            {isPipelineDetail && activePipelineCount > 0 ? (
              <div className="mt-3 flex items-center gap-2 text-xs text-warning">
                <span className="h-1.5 w-1.5 animate-stage-pulse rounded-full bg-warning" />
                Monitoring active content runs while viewing pipeline history.
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}
