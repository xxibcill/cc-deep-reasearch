'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { usePathname, useSearchParams } from 'next/navigation'
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

import { usePipeline } from '@/hooks/usePipeline'
import { useScripts } from '@/hooks/useScripts'
import { usePublish } from '@/hooks/usePublish'
import { cn } from '@/lib/utils'

const WORKFLOW_NAV_ITEMS = [
  { value: 'overview', label: 'Overview', href: '/content-gen', icon: LayoutDashboard },
  { value: 'scripts', label: 'Scripting', href: '/content-gen?tab=scripts', icon: FileText },
  { value: 'briefs', label: 'Briefs', href: '/content-gen/briefs', icon: FileTextIcon },
  { value: 'backlog', label: 'Backlog', href: '/content-gen/backlog', icon: ListChecks },
  { value: 'strategy', label: 'Strategy', href: '/content-gen?tab=strategy', icon: Settings },
  { value: 'queue', label: 'Queue', href: '/content-gen?tab=queue', icon: ListVideo },
  { value: 'chat', label: 'Assistant', href: '/content-gen/chat', icon: MessageSquare },
]

function getActiveWorkflow(pathname: string, tab: string | null): string {
  if (pathname.startsWith('/content-gen/backlog')) {
    return 'backlog'
  }
  if (pathname.startsWith('/content-gen/briefs')) {
    return 'briefs'
  }
  if (pathname.startsWith('/content-gen/chat')) {
    return 'chat'
  }
  if (pathname.startsWith('/content-gen/scripts') || pathname.startsWith('/content-gen/scripting')) {
    return 'scripts'
  }

  return tab || 'overview'
}

export function ContentGenNavigation() {
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const loadPipelines = usePipeline((s) => s.loadPipelines)
  const loadScripts = useScripts((s) => s.loadScripts)
  const loadPublishQueue = usePublish((s) => s.loadPublishQueue)
  const pipelines = usePipeline((s) => s.pipelines)
  const scripts = useScripts((s) => s.scripts)
  const publishQueue = usePublish((s) => s.publishQueue)

  const isPipelineDetail = pathname.match(/\/content-gen\/pipeline\/[^/]+$/)
  const isBacklogDetail = pathname.match(/\/content-gen\/backlog\/[^/]+$/)
  const isBriefDetail = pathname.match(/\/content-gen\/briefs\/[^/]+$/)
  const activeWorkflow = getActiveWorkflow(pathname, searchParams.get('tab'))
  const activePipelineCount = pipelines.filter(
    (pipeline) => pipeline.status === 'running' || pipeline.status === 'queued',
  ).length

  const backHref = isBacklogDetail
    ? '/content-gen/backlog'
    : isBriefDetail
      ? '/content-gen/briefs'
      : isPipelineDetail
        ? '/content-gen'
        : null

  const tabsWithBadges = WORKFLOW_NAV_ITEMS.map((item) => {
    if (item.value === 'overview' && activePipelineCount > 0) {
      return { ...item, badge: activePipelineCount }
    }
    if (item.value === 'scripts' && scripts.length > 0) {
      return { ...item, badge: scripts.length }
    }
    if (item.value === 'queue' && publishQueue.length > 0) {
      return { ...item, badge: publishQueue.length }
    }
    return item
  })

  useEffect(() => {
    void Promise.allSettled([
      loadPipelines(),
      loadScripts(),
      loadPublishQueue(),
    ])
  }, [loadPipelines, loadPublishQueue, loadScripts])

  return (
    <div className="flex min-w-0 items-center gap-2">
      {backHref ? (
        <Link
          href={backHref}
          className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-md px-2.5 text-sm text-muted-foreground transition-colors hover:bg-surface-raised/70 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45"
        >
          <ArrowLeft className="h-4 w-4" />
          <span className="hidden sm:inline">Back</span>
        </Link>
      ) : null}

      <nav
        aria-label="Content workflow navigation"
        className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto rounded-md border border-border/70 bg-surface/55 p-1"
      >
        {tabsWithBadges.map((item) => {
          const active = item.value === activeWorkflow
          const Icon = item.icon

          return (
            <Link
              key={item.value}
              href={item.href}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'inline-flex h-8 shrink-0 items-center gap-2 rounded px-2.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45',
                active
                  ? 'bg-background text-foreground shadow-[inset_0_0_0_1px_hsl(var(--border)/0.7)]'
                  : 'text-muted-foreground hover:bg-surface-raised/70 hover:text-foreground',
              )}
            >
              <Icon className={cn('h-3.5 w-3.5', active && 'text-primary')} />
              <span>{item.label}</span>
              {'badge' in item && item.badge !== undefined ? (
                <span
                  className={cn(
                    'min-w-5 rounded px-1.5 py-0.5 text-center font-mono text-[0.65rem] leading-none',
                    active ? 'bg-primary/16 text-primary' : 'bg-muted text-muted-foreground',
                  )}
                >
                  {item.badge}
                </span>
              ) : null}
            </Link>
          )
        })}
      </nav>
    </div>
  )
}
