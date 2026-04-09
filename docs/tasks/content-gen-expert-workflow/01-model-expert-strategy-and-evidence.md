# Task 01: Add Expert Strategy And Evidence Models

Goal:
Extend the content-gen data contracts so later stages can express expertise, proof rules, and non-generic positioning.

Primary files:
- `src/cc_deep_research/content_gen/models.py`

Scope:
- Add typed models for expert positioning and evidence-oriented planning.
- Extend `StrategyMemory` with fields such as `signature_frameworks`, `contrarian_beliefs`, `proof_rules`, `banned_tropes`, and `expertise_edge`.
- Extend `OpportunityBrief` with fields such as `expert_take`, `non_obvious_claims_to_test`, and `genericity_risks`.
- Extend `BacklogItem` with fields such as `expertise_reason`, `genericity_risk`, and `proof_gap_note`.
- Keep defaults empty so existing saved YAML and JSON still load.

Constraints:
- Prefer additive changes.
- Do not change orchestrator behavior yet.
- Do not rewrite prompts in this task.

Acceptance criteria:
- All new fields are optional-by-default and serializable.
- Existing tests that validate default model construction should still be satisfiable after minor fixture updates.
- No existing CLI or router code should need behavior changes just to import the models.

Validation:
- Run the model-focused tests that touch content-gen defaults.

Out of scope:
- Research pack redesign
- New pipeline stages
- Prompt contract changes

