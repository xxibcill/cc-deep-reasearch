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
4. `04-argument-map-models-and-prompt.md`
5. `05-argument-map-agent-and-parsing.md`
6. `06-pipeline-wiring-for-argument-map.md`
7. `07-scripting-grounding-with-proof-links.md`
8. `08-quality-evaluator-expert-metrics.md`
9. `09-qc-claim-safety-review.md`
10. `10-search-query-families-and-freshness.md`
11. `11-tests-and-contract-docs.md`
12. `12-workflow-resume-and-idea-bypass.md`
13. `13-multi-lane-shortlist-fanout.md`

Parallelization guidance:
- Tasks 02 and 03 can overlap only if one agent owns models and the other owns retrieval formatting.
- Tasks 04 and 05 are sequential.
- Tasks 08 and 09 can run in parallel after task 07.
- Tasks 12 and 13 are optional follow-up workflow tasks and do not block the core expert-quality path.

Definition of "more expert" for this project:
- Stronger editorial point of view
- Explicit evidence and source grounding
- Clear separation between supported claims and uncertain claims
- Better mechanism-level reasoning in scripts
- Less generic phrasing and fewer interchangeable takes
