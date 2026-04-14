# Task P2-T2: Execution Brief Generation

## Objective

Generate compact AI briefs that help a superuser move a strong backlog item into production faster.

## Scope

- Produce a brief from one backlog item that includes:
  - audience and problem framing
  - strongest hook direction
  - evidence requirements
  - proof gaps
  - research questions
  - risks before production
- Make the brief viewable without starting a full downstream pipeline.
- Support explicit promotion from brief review into the existing production-start flow.

## Acceptance Criteria

- A superuser can generate a production-readiness brief for a backlog item on demand.
- The brief is grounded in existing backlog metadata and AI-enriched context.
- The brief helps reduce manual setup work before the pipeline starts.

## Status

**Done** — Implemented in:
- `src/cc_deep_research/content_gen/agents/execution_brief.py` — ExecutionBriefAgent
- `src/cc_deep_research/content_gen/prompts/execution_brief.py` — prompt templates
- `src/cc_deep_research/content_gen/router.py` — POST /api/content-gen/backlog-ai/execution-brief endpoint
- `dashboard/src/components/content-gen/execution-brief-panel.tsx` — brief panel UI
- `dashboard/src/app/content-gen/backlog/[ideaId]/page.tsx` — embedded in backlog detail page
- `dashboard/src/types/content-gen.ts` + `dashboard/src/lib/content-gen-api.ts` — TypeScript types and API client

## Advice For The Smaller Coding Agent

- Keep the output concise and operator-friendly.
- Reuse existing content-gen language where possible so the brief feels native to the workflow.
- Do not duplicate full downstream artifacts if a shorter summary is enough.
