# P4-T2 - Add Rule Governance Lifecycle

## Summary

Introduce explicit lifecycle controls for reusable rules so they can be promoted, reviewed, expired, and deprecated safely.

## Scope

- Add lifecycle metadata such as status, confidence, evidence count, review date, and deprecation state.
- Implement promotion criteria and retirement criteria enforcement.
- Support operator-visible review decisions for durable rules.

## Deliverables

- Rule lifecycle model and persistence
- Promotion and retirement logic
- Operator-facing review workflow hooks

## Dependencies

- P3-T2 structured learnings
- P3-T3 durable guidance promotion

## Acceptance Criteria

- Reusable rules can be promoted and deprecated with explicit lifecycle state.
- Rule history reflects why a rule changed and when it should be reviewed again.

## Status

**Done**

Implemented:
- `RuleLifecycleStatus` enum: `PROMOTED`, `UNDER_REVIEW`, `DEPRECATED`, `EXPIRED`
- Extended `RuleVersion` model with lifecycle metadata: `lifecycle_status`, `confidence`, `evidence_count`, `review_after`, `review_notes`
- `RuleVersionHistory.get_rules_needing_review()`, `get_deprecated_rules()`, `get_stale_rules()`, `can_promote()`, `should_retire()` methods
- `StrategyStore.update_rule_lifecycle()`, `deprecate_rule()`, `mark_rule_under_review()`, `get_rules_for_review()` methods
- `GET /api/content-gen/strategy/rules-for-review` endpoint
- `PATCH /api/content-gen/strategy/rule-lifecycle/{version_id}` endpoint for promotion, deprecation, and review scheduling
- Frontend `RulesForReviewPanel` component showing rules needing review with Promote/Deprecate actions
- Frontend `RuleStatusBadge` component for lifecycle state display
- TypeScript types: `RuleLifecycleStatus`, `RuleVersion` in `dashboard/src/types/content-gen.ts`
- API functions: `getRulesForReview()`, `updateRuleLifecycle()` in `dashboard/src/lib/content-gen-api.ts`
