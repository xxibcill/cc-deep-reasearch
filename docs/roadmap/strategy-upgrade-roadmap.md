# Strategy Upgrade Roadmap

This roadmap breaks the strategy-system upgrade into phased delivery slices that match the existing content pipeline and dashboard architecture.

## Phases

| Phase | Outcome |
| --- | --- |
| [Phase 01 - Strategy Schema And Foundations](./phases/phase-01-strategy-schema-and-foundations.md) | The product has a richer, validated strategy model and stable backend contracts for future UI work. |
| [Phase 02 - Strategy Dashboard And Editing UX](./phases/phase-02-strategy-dashboard-and-editing-ux.md) | Operators can manage strategy in structured UI flows instead of comma-separated text fields. |
| [Phase 03 - Strategy Integration And Learning Quality](./phases/phase-03-strategy-integration-and-learning-quality.md) | Strategy fields actively steer planning, scoring, scripting, packaging, and learning promotion. |
| [Phase 04 - Governance, Validation, And Operating Fitness](./phases/phase-04-governance-validation-and-operating-fitness.md) | The system can validate strategy health, control rule promotion, and surface operational risk before strategy quality degrades. |

## Sequencing Notes

- Phase 01 must land before the dashboard rewrite because the current UI types and API payloads do not cover the intended schema.
- Phase 02 should deliver content pillar management first because it is the highest-friction workflow today.
- Phase 03 should only integrate fields that already have clear semantics and stable validation from earlier phases.
- Phase 04 should harden promotion, retirement, and readiness checks after the richer schema and UI are in use.
