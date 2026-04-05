'use client'

import type { PipelineContext } from '@/types/content-gen'
import { SummaryField, SectionList } from './ui'

function MetricsGrid({ metrics }: { metrics: Record<string, unknown> }) {
  const entries = Object.entries(metrics)
  
  if (entries.length === 0) {
    return <p className="text-sm text-muted-foreground">No metrics recorded</p>
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
      {entries.map(([key, value]) => (
        <div
          key={key}
          className="rounded-lg border border-border/70 bg-background/55 px-2 py-2"
        >
          <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground truncate">
            {key}
          </p>
          <p className="mt-1 text-sm font-medium text-foreground/90 truncate" title={String(value)}>
            {String(value)}
          </p>
        </div>
      ))}
    </div>
  )
}

export function PerformanceAnalysisPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.performance) {
    return null
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border/70 bg-background/55 px-3 py-3">
        <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground mb-3">
          Metrics
        </p>
        <MetricsGrid metrics={ctx.performance.metrics} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionList label="What worked" items={ctx.performance.what_worked} />
        <SectionList label="What failed" items={ctx.performance.what_failed} />
        <SectionList label="Audience signals" items={ctx.performance.audience_signals} />
        <SectionList label="Dropoff hypotheses" items={ctx.performance.dropoff_hypotheses} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SummaryField label="Hook diagnosis" value={ctx.performance.hook_diagnosis} />
        <SummaryField label="Lesson" value={ctx.performance.lesson} />
      </div>

      <SummaryField label="Next test" value={ctx.performance.next_test || 'No next test recorded'} />

      <SectionList label="Follow-up ideas" items={ctx.performance.follow_up_ideas} />
      <SectionList label="Backlog updates" items={ctx.performance.backlog_updates} />
    </div>
  )
}
