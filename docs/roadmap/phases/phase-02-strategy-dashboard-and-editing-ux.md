# Phase 02 - Strategy Dashboard And Editing UX

## Functional Feature Outcome

Operators can manage strategy through structured dashboard workflows, including first-class content pillar management, instead of editing comma-separated lists and raw JSON.

## Why This Phase Exists

The current strategy editor makes the system harder to use than the data model requires. Even today, the backend supports nested concepts like audience segments, proof rules, contrarian beliefs, and winners/losers, but the UI only exposes a small flat subset and forces list editing through comma-separated text inputs. This phase turns strategy from a thin settings form into an operator workspace.

## Scope

- Replace the single flat `StrategyEditor` with sectioned strategy management flows.
- Make content pillars first-class records with add, edit, reorder, and archive behavior.
- Introduce structured editors for nested objects like audience segments, proof rules, contrarian beliefs, examples, and CTA policy.
- Preserve import/export as an advanced path rather than the main editing path.
- Surface strategy completeness and validation feedback in the dashboard.

## Tasks

| Task | Summary |
| --- | --- |
| [P2-T1](../tasks/phase-02/p2-t1-redesign-strategy-workspace.md) | Redesign the strategy page into a sectioned workspace with clear editing domains. |
| [P2-T2](../tasks/phase-02/p2-t2-build-content-pillar-management.md) | Build first-class content pillar CRUD and ordering UI. |
| [P2-T3](../tasks/phase-02/p2-t3-build-structured-editors-for-nested-strategy-objects.md) | Add structured editors for audience, proof, CTA, platform, and evidence-related strategy data. |
| [P2-T4](../tasks/phase-02/p2-t4-add-readiness-and-import-export-ux.md) | Add readiness feedback, advanced import/export, and safer save flows. |

## Dependencies

- Phase 01 must land first so the dashboard can rely on stable types and API responses.
- Shared UI primitives in the dashboard should be reused where possible instead of introducing isolated controls.

## Exit Criteria

- Content pillars are managed individually rather than through a comma-separated string field.
- Operators can edit nested strategy records without switching to raw JSON.
- The strategy page shows strategy health or missing data before save/publish decisions.
- Import/export remains available without being the primary editing path.
