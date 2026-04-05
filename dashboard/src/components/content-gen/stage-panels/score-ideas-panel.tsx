'use client'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { getStatusBadgeVariant } from '@/lib/utils'
import type { PipelineContext } from '@/types/content-gen'
import { buildShortlist, findSelectedIdea } from './shared'

export function ScoreIdeasPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.scoring) {
    return null
  }

  const selectedIdea = findSelectedIdea(ctx)
  const shortlistedIdeas = buildShortlist(ctx)
  const alternateIdeas = shortlistedIdeas.filter((entry) => entry.item.idea_id !== selectedIdea.item?.idea_id)
  const selectionReasoning = ctx.selection_reasoning || ctx.scoring.selection_reasoning || null

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Badge variant="success">{ctx.scoring.produce_now.length} produce now</Badge>
        <Badge variant="info">{shortlistedIdeas.length} shortlisted</Badge>
        <Badge variant="secondary">{ctx.scoring.hold.length} hold</Badge>
        <Badge variant="destructive">{ctx.scoring.killed.length} kill</Badge>
      </div>
      {ctx.scoring.is_degraded ? (
        <Alert variant="warning">
          <AlertTitle>Scoring degraded</AlertTitle>
          <AlertDescription>
            {ctx.scoring.degradation_reason || 'The scoring stage completed with degraded output.'}
          </AlertDescription>
        </Alert>
      ) : null}

      {selectedIdea.item ? (
        <div className="rounded-[1rem] border border-success/25 bg-success-muted/10 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="success">Chosen idea</Badge>
            {selectedIdea.score ? (
              <Badge variant="outline">score {selectedIdea.score.total_score}</Badge>
            ) : null}
            {selectedIdea.score?.recommendation ? (
              <Badge variant={getStatusBadgeVariant(selectedIdea.score.recommendation)}>
                {selectedIdea.score.recommendation}
              </Badge>
            ) : null}
          </div>
          <p className="mt-3 text-sm font-medium text-foreground">{selectedIdea.item.idea}</p>
          <p className="mt-2 text-sm text-foreground/72">
            {selectedIdea.item.problem}
          </p>
          {selectionReasoning ? (
            <p className="mt-3 text-sm leading-relaxed text-foreground/78">
              {selectionReasoning}
            </p>
          ) : selectedIdea.score?.reason ? (
            <p className="mt-3 text-sm leading-relaxed text-foreground/78">
              {selectedIdea.score.reason}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="space-y-3">
        <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
          Shortlist context
        </p>
        {alternateIdeas.length > 0 ? (
          <div className="grid gap-3">
            {alternateIdeas.map(({ item, score }) => (
              <div
                key={item.idea_id}
                className="rounded-[1rem] border border-border/70 bg-background/45 px-4 py-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary">{item.idea_id}</Badge>
                  {score ? <Badge variant="outline">score {score.total_score}</Badge> : null}
                  {score?.recommendation ? (
                    <Badge variant={getStatusBadgeVariant(score.recommendation)}>
                      {score.recommendation}
                    </Badge>
                  ) : null}
                </div>
                <p className="mt-2 text-sm font-medium text-foreground/90">{item.idea}</p>
                {score?.reason ? (
                  <p className="mt-2 text-sm leading-relaxed text-foreground/72">{score.reason}</p>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No alternate shortlist ideas recorded.</p>
        )}
      </div>
    </div>
  )
}
