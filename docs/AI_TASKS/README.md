# AI Coding Tasks From Improvement Plan

This directory decomposes [IMPROVEMENT_PLAN.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/IMPROVEMENT_PLAN.md) into small, implementation-sized tasks that can be worked independently by AI coding agents.

## Task Format

Each task file contains:

- objective
- scope
- target files
- dependencies
- acceptance criteria
- suggested verification

## Recommended Order

Start with these tasks:

1. [001_metadata_contract.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/001_metadata_contract.md)
2. [002_phase_result_types.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/002_phase_result_types.md)
3. [003_orchestrator_contract_tests.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/003_orchestrator_contract_tests.md)
4. [004_no_team_flag_semantics.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/004_no_team_flag_semantics.md)

Then move into retrieval quality:

5. [005_query_intent_classification.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/005_query_intent_classification.md)
6. [006_query_family_expansion.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/006_query_family_expansion.md)
7. [007_source_provenance_tracking.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/007_source_provenance_tracking.md)
8. [008_provider_expansion_or_multi_strategy.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/008_provider_expansion_or_multi_strategy.md)

Then improve evidence quality and output:

9. [009_claim_evidence_model.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/009_claim_evidence_model.md)
10. [010_validator_failure_modes.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/010_validator_failure_modes.md)
11. [011_architecture_honesty_cleanup.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/011_architecture_honesty_cleanup.md)
12. [012_report_evidence_annotations.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/012_report_evidence_annotations.md)

Finally add measurement and observability:

13. [013_benchmark_corpus.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/013_benchmark_corpus.md)
14. [014_benchmark_harness.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/014_benchmark_harness.md)
15. [015_observability_and_stop_reasons.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/015_observability_and_stop_reasons.md)

## Dependency Notes

- `001` and `002` reduce ambiguity for almost every later task.
- `003` should land before major orchestrator refactors.
- `005` should land before `006`.
- `006` and `007` should land before `010`.
- `009` should land before `012`.
- `013` should land before `014`.

## Definition Of Done For This Task Pack

A task is ready for implementation when:

- it has a single primary outcome
- it points to likely code locations
- it has explicit acceptance criteria
- it can be completed in one focused PR
