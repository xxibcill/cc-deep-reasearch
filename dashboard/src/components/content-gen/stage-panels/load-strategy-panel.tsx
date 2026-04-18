'use client'

import { Badge } from '@/components/ui/badge'
import type { AudienceSegment, ContentExample, PipelineContext } from '@/types/content-gen'
import { SummaryField, SectionList } from './ui'

function AudienceSegmentCard({ segment }: { segment: AudienceSegment }) {
  return (
    <div className="rounded-xl border border-border/70 bg-background/55 px-3 py-2">
      <p className="text-sm font-medium text-foreground">{segment.name}</p>
      <p className="mt-1 text-xs text-foreground/72">{segment.description}</p>
      {segment.pain_points.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {segment.pain_points.slice(0, 3).map((point, i) => (
            <Badge key={i} variant="outline" className="text-[10px] px-1.5 py-0">
              {point}
            </Badge>
          ))}
          {segment.pain_points.length > 3 && (
            <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
              +{segment.pain_points.length - 3}
            </Badge>
          )}
        </div>
      )}
    </div>
  )
}

function ContentExampleCard({ example, variant }: { example: ContentExample; variant: 'winner' | 'loser' }) {
  return (
    <div className="rounded-lg border border-border/50 bg-background/40 px-2 py-1.5">
      <p className="text-xs font-medium text-foreground">{example.title}</p>
      <p className="mt-1 text-[10px] leading-relaxed text-foreground/65">{example.why_it_worked_or_failed}</p>
    </div>
  )
}

export function LoadStrategyPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.strategy) {
    return null
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 lg:grid-cols-2">
        <SummaryField label="Niche" value={ctx.strategy.niche || 'Not set'} />
        <SummaryField label="Tone rules" value={ctx.strategy.tone_rules.join(' | ') || 'No tone rules yet'} />
        <SectionList label="Content pillars" items={ctx.strategy.content_pillars.map(p => p.name)} emptyLabel="No pillars configured" />
        <SectionList label="Platforms" items={ctx.strategy.platforms} emptyLabel="No platforms configured" />
      </div>
      
      <SectionList
        label="Audience segments"
        items={[]}
        emptyLabel="No audience segments configured"
      >
        {ctx.strategy.audience_segments.length > 0 ? (
          <div className="grid gap-2 sm:grid-cols-2">
            {ctx.strategy.audience_segments.map((segment, i) => (
              <AudienceSegmentCard key={i} segment={segment} />
            ))}
          </div>
        ) : null}
      </SectionList>

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionList label="Proof standards" items={ctx.strategy.proof_standards} emptyLabel="No proof standards" />
        <SectionList label="Forbidden claims" items={ctx.strategy.forbidden_claims} emptyLabel="No forbidden claims" />
      </div>

      <SummaryField label="CTA rules" value={ctx.strategy.offer_cta_rules.join(' | ') || 'No CTA rules'} />

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-2">
          <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Past winners ({ctx.strategy.past_winners.length})
          </p>
          {ctx.strategy.past_winners.length > 0 ? (
            <div className="space-y-2">
              {ctx.strategy.past_winners.slice(0, 3).map((example, i) => (
                <ContentExampleCard key={i} example={example} variant="winner" />
              ))}
              {ctx.strategy.past_winners.length > 3 && (
                <p className="text-xs text-muted-foreground">+{ctx.strategy.past_winners.length - 3} more winners</p>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No past winners recorded</p>
          )}
        </div>
        <div className="space-y-2">
          <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Past losers ({ctx.strategy.past_losers.length})
          </p>
          {ctx.strategy.past_losers.length > 0 ? (
            <div className="space-y-2">
              {ctx.strategy.past_losers.slice(0, 3).map((example, i) => (
                <ContentExampleCard key={i} example={example} variant="loser" />
              ))}
              {ctx.strategy.past_losers.length > 3 && (
                <p className="text-xs text-muted-foreground">+{ctx.strategy.past_losers.length - 3} more losers</p>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No past losers recorded</p>
          )}
        </div>
      </div>
    </div>
  )
}
