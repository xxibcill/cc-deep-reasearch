'use client'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { getStatusBadgeVariant } from '@/lib/utils'
import type { IdeaScores, PipelineContext } from '@/types/content-gen'
import { buildShortlist, findSelectedIdea } from './shared'

function ScoreBreakdown({ scores }: { scores: IdeaScores }) {
  const scoreFields: { key: keyof IdeaScores; label: string }[] = [
    { key: 'relevance', label: 'Relevance' },
    { key: 'novelty', label: 'Novelty' },
    { key: 'authority_fit', label: 'Authority Fit' },
    { key: 'production_ease', label: 'Production' },
    { key: 'evidence_strength', label: 'Evidence' },
    { key: 'hook_strength', label: 'Hook' },
    { key: 'repurposing', label: 'Repurposing' },
  ]

  return (
    <div className="mt-3 grid grid-cols-4 gap-1 text-[10px]">
      {scoreFields.map((field) => (
        <div key={field.key} className="text-center">
          <span className="text-muted-foreground">{field.label}</span>
          <p className="font-mono font-medium text-foreground">
            {(scores[field.key] as number)?.toFixed(1) ?? '-'}
          </p>
        </div>
      ))}
    </div>
  )
}

function ScoredIdeaCard({ item, score, isSelected }: { item: { idea_id: string; idea: string; problem: string }; score: IdeaScores | null | undefined; isSelected: boolean }) {
  return (
    <div
      className={`rounded-xl border p-3 ${
        isSelected
          ? 'border-success/30 bg-success-muted/10'
          : 'border-border/70 bg-background/45'
      }`}
    >
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <Badge variant={isSelected ? 'success' : 'secondary'} className="text-[10px]">
          {item.idea_id}
        </Badge>
        {score && (
          <>
            <Badge variant="outline" className="text-[10px]">
              Total: {score.total_score?.toFixed(1)}
            </Badge>
            <Badge variant={getStatusBadgeVariant(score.recommendation)} className="text-[10px]">
              {score.recommendation}
            </Badge>
          </>
        )}
      </div>
      <p className="text-sm font-medium text-foreground">{item.idea}</p>
      <p className="mt-1 text-xs text-foreground/72">{item.problem}</p>
      {score && <ScoreBreakdown scores={score} />}
      {score?.reason && (
        <p className="mt-2 text-xs text-foreground/65 italic">{score.reason}</p>
      )}
    </div>
  )
}

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

      {shortlistedIdeas.length > 0 && (
        <div className="space-y-3">
          <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Scored ideas
          </p>
          {selectionReasoning ? (
            <p className="text-sm leading-relaxed text-foreground/78 italic">
              {selectionReasoning}
            </p>
          ) : null}
          <div className="grid gap-3">
            {shortlistedIdeas.map(({ item, score }) => (
              <ScoredIdeaCard
                key={item.idea_id}
                item={item}
                score={score}
                isSelected={item.idea_id === selectedIdea.item?.idea_id}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
