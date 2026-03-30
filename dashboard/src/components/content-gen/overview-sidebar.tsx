'use client'

import Link from 'next/link'
import { ArrowRight } from 'lucide-react'
import useContentGen from '@/hooks/useContentGen'

interface OverviewSidebarProps {
  onTabChange: (tab: string) => void
}

export function OverviewSidebar({ onTabChange }: OverviewSidebarProps) {
  const strategy = useContentGen((s) => s.strategy)
  const scripts = useContentGen((s) => s.scripts)
  const publishQueue = useContentGen((s) => s.publishQueue)

  const recentScripts = scripts.slice(0, 5)
  const scheduledCount = publishQueue.filter((i) => i.status === 'scheduled').length
  const nextScheduled = publishQueue.find((i) => i.status === 'scheduled')

  return (
    <div className="space-y-4">
      {/* Strategy summary */}
      <div className="bg-surface border border-border rounded-sm p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
            Strategy
          </h3>
          <button
            onClick={() => onTabChange('strategy')}
            className="text-xs text-muted-foreground hover:text-warning transition-colors"
          >
            Edit
          </button>
        </div>
        {strategy ? (
          <div className="space-y-2">
            <p className="text-sm font-medium text-foreground/90">{strategy.niche || 'No niche set'}</p>
            {strategy.content_pillars?.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {strategy.content_pillars.slice(0, 3).map((pillar, i) => (
                  <span
                    key={i}
                    className="text-[11px] px-2 py-0.5 bg-surface-raised rounded-sm text-muted-foreground"
                  >
                    {pillar}
                  </span>
                ))}
              </div>
            )}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">No strategy configured</p>
        )}
      </div>

      {/* Recent scripts */}
      {recentScripts.length > 0 && (
        <div className="bg-surface border border-border rounded-sm p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
              Recent Scripts
            </h3>
            <button
              onClick={() => onTabChange('scripts')}
              className="text-xs text-muted-foreground hover:text-warning transition-colors"
            >
              View all
            </button>
          </div>
          <div className="space-y-1">
            {recentScripts.map((s) => (
              <div
                key={s.run_id}
                className="flex items-center justify-between py-1.5"
              >
                <span className="text-sm text-foreground/70 truncate max-w-[65%]">
                  {s.raw_idea || 'Untitled'}
                </span>
                <span className="text-xs font-mono text-muted-foreground tabular-nums shrink-0">
                  {s.word_count}w
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Queue summary */}
      <div className="bg-surface border border-border rounded-sm p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
            Publish Queue
          </h3>
          {publishQueue.length > 0 && (
            <button
              onClick={() => onTabChange('queue')}
              className="text-xs text-muted-foreground hover:text-warning transition-colors"
            >
              View all
            </button>
          )}
        </div>
        {publishQueue.length > 0 ? (
          <div className="space-y-1">
            <p className="text-sm text-foreground/80">
              {scheduledCount} scheduled
            </p>
            {nextScheduled && (
              <p className="text-xs text-muted-foreground font-mono tabular-nums">
                Next: {nextScheduled.publish_datetime}
              </p>
            )}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">No items in queue</p>
        )}
      </div>
    </div>
  )
}
