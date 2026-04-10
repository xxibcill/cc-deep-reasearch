# Content Gen Expert Workflow Task Pack

This folder breaks the "make content generation more expert" initiative into small tasks for a smaller coding agent.

Working rules:
- Keep scope narrow. Do only the task you were assigned.
- Do not absorb adjacent refactors unless they are required to make the task work.
- Respect the current dirty worktree. Do not revert unrelated user changes.
- Prefer additive, backward-compatible changes until the pipeline wiring tasks land.
- Update tests for the files you touch when the task explicitly asks for it.

Recommended order:
1. `01-model-expert-strategy-and-evidence.md` - Done
2. `02-research-pack-structured-evidence.md` - Done
3. `03-research-provenance-and-source-retention.md` - Done
4. `04-argument-map-models-and-prompt.md` - Done
5. `05-argument-map-agent-and-parsing.md` - Done
6. `06-pipeline-wiring-for-argument-map.md` - Done
7. `07-scripting-grounding-with-proof-links.md` - Done
8. `08-quality-evaluator-expert-metrics.md` - Done
9. `09-qc-claim-safety-review.md` - Done
10. `10-search-query-families-and-freshness.md` - Done
11. `11-tests-and-contract-docs.md` - Done
12. `12-workflow-resume-and-idea-bypass.md` - Done
13. `13-multi-lane-shortlist-fanout.md` - Done
14. `14-tolerant-stage-degraded-metadata.md` - Done
15. `15-retrieval-fanout-redesign.md` - Done
16. `16-source-authority-scoring-and-evidence-ranking.md` - Done
17. `17-end-to-end-claim-traceability-ledger.md` - Planned
18. `18-targeted-revision-loop-for-weak-beats.md` - Planned
19. `19-competitive-differentiation-and-genericity-check.md` - Planned
20. `20-performance-feedback-into-strategy-memory-and-backlog.md` - Planned

Parallelization guidance:
- Tasks 02 and 03 can overlap only if one agent owns models and the other owns retrieval formatting.
- Tasks 04 and 05 are sequential.
- Tasks 08 and 09 can run in parallel after task 07.
- Tasks 12 and 13 are optional follow-up workflow tasks and do not block the core expert-quality path.
- Tasks 14 and 15 are follow-up reliability/scale tasks and can start after the current workflow hardening work is stable.
- Tasks 16 and 17 should run before task 18 because the revision loop is much stronger if source quality and claim traceability are already explicit.
- Task 19 can run in parallel with tasks 16 or 17 if one agent owns retrieval/evaluation changes and the other owns argument-map or scripting differentiation checks.
- Task 20 can start after the performance stage is stable and does not need to block tasks 16 to 19.

Definition of "more expert" for this project:
- Stronger editorial point of view
- Explicit evidence and source grounding
- Clear separation between supported claims and uncertain claims
- Better mechanism-level reasoning in scripts
- Less generic phrasing and fewer interchangeable takes

Next-wave extension themes:
- Source quality should influence which evidence survives into argument maps and scripts.
- Claims should remain traceable from retrieval through final script beats and QC.
- Revision loops should repair weak beats selectively instead of regenerating everything.
- Competitive framing should help the system avoid generic takes that sound like everyone else.
- Post-publish learning should update strategy and backlog behavior, not stay isolated in one report.
