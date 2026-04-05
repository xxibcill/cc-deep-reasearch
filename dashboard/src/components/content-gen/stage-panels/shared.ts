import type { BacklogItem, IdeaScores, PipelineContext, PipelineStageName } from '@/types/content-gen'

export function uniqueIdeaIds(ideaIds: Array<string | null | undefined>): string[] {
  const seen = new Set<string>()
  const normalized: string[] = []

  for (const ideaId of ideaIds) {
    if (!ideaId || seen.has(ideaId)) {
      continue
    }
    seen.add(ideaId)
    normalized.push(ideaId)
  }

  return normalized
}

export function findSelectedIdeaId(ctx: PipelineContext): string | null {
  return (
    ctx.selected_idea_id ||
    ctx.scoring?.selected_idea_id ||
    ctx.angles?.idea_id ||
    ctx.research_pack?.idea_id ||
    ctx.visual_plan?.idea_id ||
    ctx.production_brief?.idea_id ||
    ctx.packaging?.idea_id ||
    ctx.publish_item?.idea_id ||
    ctx.backlog?.items.find((item) => item.status === 'selected')?.idea_id ||
    ctx.scoring?.produce_now[0] ||
    null
  )
}

export function findSelectedIdea(
  ctx: PipelineContext,
): { item: BacklogItem | null; score: IdeaScores | null } {
  const selectedIdeaId = findSelectedIdeaId(ctx)
  return {
    item: selectedIdeaId ? ctx.backlog?.items.find((item) => item.idea_id === selectedIdeaId) ?? null : null,
    score: selectedIdeaId ? ctx.scoring?.scores.find((score) => score.idea_id === selectedIdeaId) ?? null : null,
  }
}

export function buildShortlist(
  ctx: PipelineContext,
): Array<{ item: BacklogItem; score: IdeaScores | null }> {
  const scoredIdeas = [...(ctx.scoring?.scores ?? [])].sort((left, right) => right.total_score - left.total_score)
  const selectedIdeaId = findSelectedIdeaId(ctx)
  const shortlistIds = ctx.shortlist.length
    ? uniqueIdeaIds([selectedIdeaId, ...ctx.shortlist])
    : ctx.scoring?.shortlist?.length
      ? uniqueIdeaIds([selectedIdeaId, ...ctx.scoring.shortlist])
      : ctx.runner_up_idea_ids.length || ctx.scoring?.runner_up_idea_ids?.length
        ? uniqueIdeaIds([
            selectedIdeaId,
            ...ctx.runner_up_idea_ids,
            ...(ctx.scoring?.runner_up_idea_ids ?? []),
          ])
        : ctx.scoring?.produce_now?.length
          ? uniqueIdeaIds(ctx.scoring.produce_now)
          : scoredIdeas.slice(0, 3).map((score) => score.idea_id)

  return shortlistIds
    .map((ideaId) => ({
      item: ctx.backlog?.items.find((candidate) => candidate.idea_id === ideaId) ?? null,
      score: ctx.scoring?.scores.find((candidate) => candidate.idea_id === ideaId) ?? null,
    }))
    .filter((entry): entry is { item: BacklogItem; score: IdeaScores | null } => Boolean(entry.item))
}

export function getSelectedAngle(ctx: PipelineContext) {
  return ctx.angles?.angle_options.find((option) => option.angle_id === ctx.angles?.selected_angle_id)
}

export function getAlternateAngles(ctx: PipelineContext) {
  return ctx.angles?.angle_options.filter(
    (option) => option.angle_id !== ctx.angles?.selected_angle_id,
  ) ?? []
}

export type { BacklogItem, IdeaScores, PipelineContext, PipelineStageName }
