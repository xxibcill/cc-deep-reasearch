'use client'

import Link from 'next/link'
import { Clock3, FileText, Lightbulb } from 'lucide-react'

import { ResearchContentActions } from '@/components/research-content-actions'
import useContentGen from '@/hooks/useContentGen'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  formatResearchBridgeSource,
  type ResearchContentBridgePayload,
} from '@/lib/research-content-bridge'

interface OverviewSidebarProps {
  onTabChange: (tab: string) => void
  researchBridge: ResearchContentBridgePayload | null
}

export function OverviewSidebar({ onTabChange, researchBridge }: OverviewSidebarProps) {
  const strategy = useContentGen((s) => s.strategy)
  const scripts = useContentGen((s) => s.scripts)
  const publishQueue = useContentGen((s) => s.publishQueue)

  const recentScripts = scripts.slice(0, 5)
  const scheduledCount = publishQueue.filter((i) => i.status === 'scheduled').length
  const nextScheduled = publishQueue.find((i) => i.status === 'scheduled')

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-start justify-between space-y-0">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-muted-foreground">
              <FileText className="h-3.5 w-3.5" />
              Research Handoff
            </div>
            <CardTitle className="text-base">
              {researchBridge ? 'Attached research source' : 'Bring research downstream'}
            </CardTitle>
          </div>
          {researchBridge ? (
            <Badge variant={researchBridge.hasReport ? 'success' : 'secondary'}>
              {researchBridge.hasReport ? 'Report ready' : 'Context only'}
            </Badge>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-3">
          {researchBridge ? (
            <>
              <div className="space-y-2">
                <p className="text-sm font-medium text-foreground/90">
                  {researchBridge.sessionLabel}
                </p>
                <p className="text-xs leading-5 text-muted-foreground">
                  Imported from {formatResearchBridgeSource(researchBridge.source)}. Use this
                  session to seed a full pipeline or a quicker script pass.
                </p>
              </div>
              <ResearchContentActions
                payload={researchBridge}
                orientation="column"
                primaryIntent="quick-script"
              />
              <Link
                href={`/session/${researchBridge.sessionId}`}
                className="text-xs text-muted-foreground underline decoration-border underline-offset-4 transition-colors hover:text-foreground"
              >
                Open source session
              </Link>
            </>
          ) : (
            <p className="text-xs leading-5 text-muted-foreground">
              Report-ready research sessions can send operators here directly. The content studio
              still works independently when you want to start from a blank brief.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between space-y-0">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-muted-foreground">
              <Lightbulb className="h-3.5 w-3.5" />
              Strategy
            </div>
            <CardTitle className="text-base">Editorial focus</CardTitle>
          </div>
          <Button onClick={() => onTabChange('strategy')} size="sm" type="button" variant="ghost">
            Edit
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {strategy ? (
            <div className="space-y-2">
              <p className="text-sm font-medium text-foreground/90">
                {strategy.niche || 'No niche set'}
              </p>
              {strategy.content_pillars?.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {strategy.content_pillars.slice(0, 3).map((pillar, i) => (
                    <Badge key={i} variant="outline">{pillar.name}</Badge>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">No strategy configured</p>
          )}
        </CardContent>
      </Card>

      {recentScripts.length > 0 && (
        <Card>
          <CardHeader className="flex flex-row items-start justify-between space-y-0">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-muted-foreground">
                <FileText className="h-3.5 w-3.5" />
                Recent Scripts
              </div>
              <CardTitle className="text-base">Latest writing runs</CardTitle>
            </div>
            <Button onClick={() => onTabChange('scripts')} size="sm" type="button" variant="ghost">
              View all
            </Button>
          </CardHeader>
          <CardContent className="space-y-2">
            {recentScripts.map((s) => (
              <div
                key={s.run_id}
                className="flex items-center justify-between rounded-lg border border-border/70 bg-muted/10 px-3 py-2"
              >
                <span className="text-sm text-foreground/70 truncate max-w-[65%]">
                  {s.raw_idea || 'Untitled'}
                </span>
                <span className="text-xs font-mono text-muted-foreground tabular-nums shrink-0">
                  {s.word_count}w
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-row items-start justify-between space-y-0">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-muted-foreground">
              <Clock3 className="h-3.5 w-3.5" />
              Publish Queue
            </div>
            <CardTitle className="text-base">Scheduling snapshot</CardTitle>
          </div>
          {publishQueue.length > 0 && (
            <Button onClick={() => onTabChange('queue')} size="sm" type="button" variant="ghost">
              View all
            </Button>
          )}
        </CardHeader>
        <CardContent className="space-y-2">
          {publishQueue.length > 0 ? (
            <div className="space-y-2">
              <Badge variant={scheduledCount > 0 ? 'success' : 'secondary'}>
                {scheduledCount} scheduled
              </Badge>
              {nextScheduled && (
                <p className="text-xs font-mono tabular-nums text-muted-foreground">
                  Next: {nextScheduled.publish_datetime}
                </p>
              )}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">No items in queue</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
