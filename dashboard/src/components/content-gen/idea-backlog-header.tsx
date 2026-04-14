'use client'

import { Badge } from '@/components/ui/badge'
import {
  formatTimestamp,
  statusBadgeVariant,
  recommendationBadgeVariant,
} from '@/components/content-gen/backlog-shared'

interface IdeaBacklogHeaderProps {
  item: {
    idea_id: string
    idea: string
    status: string
    category?: string | null
    latest_recommendation?: string | null
    risk_level?: string | null
    content_type?: string | null
    latest_score?: number | null
    priority_score?: number | null
    created_at?: string | null
    updated_at?: string | null
  }
}

export function IdeaBacklogHeader({ item }: IdeaBacklogHeaderProps) {
  return (
    <div className="rounded-[1.15rem] border border-border/75 bg-card/95 p-5 shadow-[0_18px_48px_rgba(0,0,0,0.18)]">
      <div className="grid gap-6 xl:grid-cols-[1fr_auto] xl:items-start">
        {/* Left: Idea + metadata */}
        <div className="space-y-4">
          <div className="space-y-1.5">
            <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
              Idea
            </p>
            <h1 className="text-2xl font-semibold leading-tight text-foreground">{item.idea}</h1>
          </div>

          <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
            <KeyValue label="Status" value={<Badge variant={statusBadgeVariant(item.status)}>{item.status}</Badge>} />
            <KeyValue label="Category" value={item.category ? <Badge variant="outline">{item.category}</Badge> : <EmptyVal />} />
            <KeyValue
              label="Recommendation"
              value={
                item.latest_recommendation ? (
                  <Badge variant={recommendationBadgeVariant(item.latest_recommendation)}>
                    {item.latest_recommendation}
                  </Badge>
                ) : (
                  <EmptyVal />
                )
              }
            />
            {item.risk_level ? (
              <KeyValue
                label="Risk"
                value={
                  <Badge
                    variant={
                      item.risk_level === 'high'
                        ? 'destructive'
                        : item.risk_level === 'medium'
                          ? 'warning'
                          : 'secondary'
                    }
                  >
                    {item.risk_level}
                  </Badge>
                }
              />
            ) : (
              <KeyValue label="Risk" value={<EmptyVal />} />
            )}
            <KeyValue label="Content type" value={<span className="text-sm">{item.content_type || '—'}</span>} />
            <KeyValue
              label="Last updated"
              value={
                <span className="font-mono text-xs">
                  {formatTimestamp(item.updated_at ?? item.created_at ?? undefined)}
                </span>
              }
            />
          </div>
        </div>

        {/* Right: Score stack */}
        <div className="flex shrink-0 gap-3 xl:flex-col xl:items-end">
          <ScoreCard label="Score" value={item.latest_score ?? item.priority_score} />
          <ScoreCard label="Priority" value={item.priority_score} />
        </div>
      </div>

      {/* ID footer */}
      <div className="mt-3 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground/50">
        {item.idea_id}
      </div>
    </div>
  )
}

function KeyValue({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="space-y-0.5">
      <p className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground/60">{label}</p>
      <div className="text-sm text-foreground/88">{value}</div>
    </div>
  )
}

function EmptyVal() {
  return <span className="text-foreground/30 text-sm">—</span>
}

function ScoreCard({ label, value }: { label: string; value: number | null | undefined }) {
  return (
    <div className="rounded-[0.95rem] border border-border/70 bg-background/45 px-4 py-3 text-right shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
      <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-2xl tabular-nums text-foreground">
        {value !== undefined && value !== null ? (
          <span className="font-mono tabular-nums">{value}</span>
        ) : (
          <span className="text-foreground/30">—</span>
        )}
      </p>
    </div>
  )
}
