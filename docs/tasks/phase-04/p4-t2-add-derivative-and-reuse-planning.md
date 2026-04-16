# P4-T2 - Add Derivative And Reuse Planning

## Objective

Turn one approved argument into a repeatable derivative pack instead of treating reuse as a manual follow-on idea.

## Scope

- extract derivative opportunities such as alternate hooks, quote cards, thread variants, newsletter snippets, and follow-up shorts
- capture reusable proof points, examples, and CTAs at the draft layer
- store reuse opportunities where backlog and performance review can find them later

## Affected Areas

- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/storage/`
- `docs/content-gen-backlog.md`
- `docs/content-generation.md`

## Dependencies

- P4-T1 must define the combined draft package

## Acceptance Criteria

- each approved draft records at least one reuse path or an explicit reason none exists
- derivative opportunities can be fed back into the backlog without redoing the full idea-selection lane
- reuse metadata survives publish and performance analysis
