# Task 004: Clarify `--no-team` Behavior

## Objective

Make `--no-team` mean one precise thing in code, docs, and tests.

## Scope

- decide whether the flag disables only parallel coordination or selects a simpler pipeline mode
- update CLI help text
- align orchestrator branching with the documented behavior
- add tests that prove the chosen semantics

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/cli.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestrator.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/docs/USAGE.md`
- `/Users/jjae/Documents/guthib/cc-deep-research/tests/test_orchestrator.py`

## Dependencies

- [003_orchestrator_contract_tests.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/003_orchestrator_contract_tests.md)

## Acceptance Criteria

- help text, docs, and implementation all say the same thing
- tests verify the selected behavior path
- no ambiguous references to “team mode” remain around this flag

## Suggested Verification

- run `pytest tests/test_orchestrator.py`
- manually inspect `--help` output
