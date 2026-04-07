# Necessary 80% Task Set

This task set breaks the project's necessary but lower-visibility work into small implementation-ready tasks for a smaller coding agent.

Use this set when the goal is to make the project more stable, testable, operable, and easier to ship without chasing new product surface area.

## Outcome

After these tasks are complete, the project should:

- have clearer runtime contracts across research, telemetry, and content generation
- catch regressions automatically instead of relying on manual discipline
- fail more predictably under provider, parsing, and orchestration edge cases
- keep the dashboard and content pipeline safer to iterate on
- ship with docs and release workflows that match the code

## Working Rules

- Complete tasks in order unless a task is explicitly marked parallel-safe.
- Keep the scope tight to the files and acceptance criteria listed for the task.
- Do not revert unrelated local changes.
- Prefer fixture-backed and mocked tests over live provider calls.
- If a task reveals a larger architectural issue, leave a note in code or docs, but do not expand scope unless the next task requires it.

## Task 01: Snapshot the Current Session Metadata Contract

Goal:
Document the exact metadata shape produced by the research pipeline today.

Scope:
- inspect the orchestrator and session builder paths
- list required and optional metadata keys
- capture nested shapes for strategy, analysis, validation, execution, and iteration history

Primary files:
- `src/cc_deep_research/orchestrator.py`
- `src/cc_deep_research/orchestration/session_state.py`
- `src/cc_deep_research/models/session.py`
- `docs/RESEARCH_WORKFLOW.md`

Acceptance criteria:
- one doc section or inline contract note describes the current metadata shape
- required versus optional fields are called out
- no behavior change yet

Validation:
- `uv run pytest tests/test_orchestrator.py tests/test_orchestration.py -v`

## Task 02: Add Typed Metadata Models

Goal:
Replace ambiguous metadata dictionaries with typed models or `TypedDict` contracts.

Scope:
- add explicit typed contracts for strategy metadata
- add explicit typed contracts for analysis metadata
- add explicit typed contracts for validation metadata
- add explicit typed contracts for iteration history entries

Primary files:
- `src/cc_deep_research/models/`
- `src/cc_deep_research/orchestration/session_state.py`
- `src/cc_deep_research/orchestrator.py`

Acceptance criteria:
- new typed contracts exist in the models layer
- metadata assembly code uses those contracts directly
- mypy and pytest stay green for touched paths

Validation:
- `uv run pytest tests/test_models.py tests/test_orchestrator.py tests/test_orchestration.py -v`
- `uv run mypy src`

## Task 03: Add Session Metadata Contract Tests

Goal:
Pin the metadata contract with focused tests so later refactors cannot drift silently.

Scope:
- add positive tests for quick, standard, and deep runs
- assert stable keys and nested shapes
- assert degraded runs still produce the documented minimum contract

Primary files:
- `tests/test_orchestrator.py`
- `tests/test_orchestration.py`

Acceptance criteria:
- tests fail if required metadata keys disappear or change shape
- degraded execution paths are covered

Validation:
- `uv run pytest tests/test_orchestrator.py tests/test_orchestration.py -v`

## Task 04: Clarify Runtime Naming and `--no-team` Semantics

Goal:
Make code and docs tell the truth about local execution versus future multi-agent ambitions.

Scope:
- review user-facing help and docs for misleading team or agent wording
- ensure `--no-team` behavior is documented consistently
- rename only obviously misleading comments or labels if the code behavior stays local

Primary files:
- `src/cc_deep_research/cli/research.py`
- `README.md`
- `docs/USAGE.md`
- `docs/RESEARCH_WORKFLOW.md`

Acceptance criteria:
- docs and CLI help agree on what `--no-team` actually does
- no user-facing text implies a distributed runtime that does not exist

Validation:
- `uv run pytest tests/test_cli_research.py -v`

## Task 05: Add Missing Provider Failure Coverage

Goal:
Harden the system against empty, malformed, or unavailable provider responses.

Scope:
- add tests for provider auth failure
- add tests for timeout and rate-limit behavior
- add tests for empty but valid results
- verify graceful fallback or degradation metadata

Primary files:
- `tests/test_tavily_provider.py`
- `tests/test_providers.py`
- `tests/test_orchestration.py`

Acceptance criteria:
- provider failure paths are covered by fixtures
- research runs degrade predictably instead of crashing

Validation:
- `uv run pytest tests/test_tavily_provider.py tests/test_providers.py tests/test_orchestration.py -v`

## Task 06: Define Retry and Timeout Behavior in One Place

Goal:
Remove scattered or implicit retry and timeout assumptions from orchestration.

Scope:
- locate current timeout and retry logic for provider calls and parallel researchers
- centralize or document policy clearly
- ensure telemetry records timeout and retry decisions consistently

Primary files:
- `src/cc_deep_research/orchestration/`
- `src/cc_deep_research/coordination/`
- `src/cc_deep_research/telemetry/`

Acceptance criteria:
- timeout and retry behavior is owned by a small number of clear functions or config paths
- tests cover timeout and fallback behavior

Validation:
- `uv run pytest tests/test_orchestration.py tests/test_teams.py tests/test_telemetry.py -v`

## Task 07: Strengthen Orchestrator Failure-Path Tests

Goal:
Cover the boring but necessary orchestration failures that usually break release quality.

Scope:
- add tests for sequential fallback when parallel collection fails
- add tests for partial analysis results
- add tests for validation follow-up loops stopping correctly
- add tests for missing provider configuration

Primary files:
- `tests/test_orchestrator.py`
- `tests/test_orchestration.py`
- `tests/test_research_run_service.py`

Acceptance criteria:
- critical fallback paths are covered
- stop conditions are deterministic under test

Validation:
- `uv run pytest tests/test_orchestrator.py tests/test_orchestration.py tests/test_research_run_service.py -v`

## Task 08: Version the Content-Gen Stage Contracts

Goal:
Make prompt-output parsing for content generation less fragile.

Scope:
- define explicit output contract expectations for each high-value stage
- record parser assumptions near each agent or in shared models
- add a version field or contract note where useful

Primary files:
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/agents/`
- `src/cc_deep_research/content_gen/prompts/`
- `docs/content-generation.md`

Acceptance criteria:
- core stages have an explicit parsing contract
- future prompt edits have a clear place to update matching parser assumptions

Validation:
- `uv run pytest tests/test_content_gen.py tests/test_iterative_loop.py -v`

## Task 09: Add Golden Fixtures for Content-Gen Stages

Goal:
Create stable test fixtures for the most failure-prone content generation stages.

Scope:
- capture representative raw outputs for backlog, angle, research-pack, scripting, packaging, and QC
- test parser success against realistic happy-path outputs
- test parser degradation against malformed or sparse outputs

Primary files:
- `tests/fixtures/`
- `tests/test_content_gen.py`

Acceptance criteria:
- fixture-backed tests exist for the key content-gen stages
- malformed outputs are handled intentionally

Validation:
- `uv run pytest tests/test_content_gen.py -v`

## Task 10: Tighten Fail-Fast Behavior in Content-Gen Parsers

Goal:
Stop partial or blank LLM output from silently propagating through later stages.

Scope:
- identify stages that currently return sparse models too permissively
- fail fast for missing required fields on high-value stages
- preserve graceful degradation only where downstream behavior is intentionally tolerant

Primary files:
- `src/cc_deep_research/content_gen/agents/`
- `src/cc_deep_research/content_gen/orchestrator.py`
- `tests/test_content_gen.py`

Acceptance criteria:
- important missing fields cause clear errors
- tolerant stages are documented as tolerant on purpose

Validation:
- `uv run pytest tests/test_content_gen.py tests/test_iterative_loop.py -v`

## Task 11: Create a Python Preflight CI Workflow

Goal:
Automate the existing preflight checks so reliability does not depend on manual memory.

Scope:
- add a GitHub Actions workflow for Python tests and static checks
- run the preflight subsets from `docs/PREFLIGHT.md`
- keep runtime reasonable by using fixture-backed suites only

Primary files:
- `.github/workflows/`
- `docs/PREFLIGHT.md`

Acceptance criteria:
- CI runs on pull requests and pushes
- core Python preflight checks are automated

Validation:
- confirm workflow YAML is valid
- if local tools exist, run the same commands locally before finishing

## Task 12: Create a Dashboard CI Workflow

Goal:
Catch frontend regressions automatically.

Scope:
- add a GitHub Actions workflow for dashboard install, lint, build, and selected Playwright checks
- prefer mocked or fixture-backed E2E coverage
- keep the job fast enough for routine use

Primary files:
- `.github/workflows/`
- `dashboard/package.json`
- `dashboard/tests/e2e/`

Acceptance criteria:
- dashboard build is enforced in CI
- at least one smoke E2E path runs automatically

Validation:
- `cd dashboard && npm run build`
- `cd dashboard && npm run test:e2e -- --grep "app|config"`, or equivalent fast smoke subset

## Task 13: Add Mock-First Dashboard Smoke Coverage

Goal:
Make UI regression testing reliable without needing live backend state.

Scope:
- identify the minimum mocked flows for home, session, compare, and config surfaces
- stabilize fixtures and test helpers
- reduce dependence on timing-sensitive live websocket behavior in basic smoke tests

Primary files:
- `dashboard/tests/e2e/dashboard-mocks.ts`
- `dashboard/tests/e2e/app.spec.ts`
- `dashboard/tests/e2e/config-editor.spec.ts`
- `dashboard/tests/e2e/`

Acceptance criteria:
- fast smoke tests can run entirely from mocked data
- core pages render and basic interactions work

Validation:
- `cd dashboard && npm run test:e2e -- --grep "app|config|compare"`

## Task 14: Add WebSocket Resilience Tests for the Dashboard

Goal:
Verify that realtime behavior degrades safely under reconnects, dropped events, or backend absence.

Scope:
- test initial connection failure
- test reconnect handling
- test partial event streams
- assert the UI stays usable when live updates are unavailable

Primary files:
- `dashboard/src/lib/websocket.ts`
- `dashboard/src/hooks/`
- `dashboard/tests/e2e/`

Acceptance criteria:
- the dashboard remains operable during websocket failure states
- failure UI is explicit and non-blocking

Validation:
- `cd dashboard && npm run test:e2e -- --grep "realtime|content-gen|observability"`

## Task 15: Make Accessibility Checks Part of the Dashboard Baseline

Goal:
Turn accessibility and contrast from occasional cleanup into routine regression protection.

Scope:
- ensure existing accessibility and contrast specs cover the main operator surfaces
- wire them into CI or a required local preflight command

Primary files:
- `dashboard/tests/e2e/accessibility.spec.ts`
- `dashboard/tests/e2e/contrast.spec.ts`
- `dashboard/package.json`

Acceptance criteria:
- a documented command exists for accessibility regression checks
- CI or preflight runs it consistently

Validation:
- `cd dashboard && npm run test:a11y`

## Task 16: Align Operator Docs with Actual Commands and Flags

Goal:
Remove drift between docs and the current CLI or dashboard behavior.

Scope:
- compare `README.md`, `docs/USAGE.md`, and `docs/README.md` with actual command registration and flags
- fix outdated wording, examples, and environment variable guidance
- verify dashboard backend instructions still match the current command set

Primary files:
- `README.md`
- `docs/USAGE.md`
- `docs/README.md`
- `src/cc_deep_research/cli/main.py`
- `src/cc_deep_research/cli/`

Acceptance criteria:
- docs match real commands and options
- examples are current and runnable

Validation:
- `uv run pytest tests/test_cli_research.py -v`
- manually compare `cc-deep-research --help` and relevant subcommand help output

## Task 17: Tighten the Release Checklist

Goal:
Make releases repeatable and less dependent on tribal knowledge.

Scope:
- extend release docs with required validation steps
- include Python and dashboard checks
- include changelog, version bump, and tag steps

Primary files:
- `docs/RELEASING.md`
- `CHANGELOG.md`
- `scripts/bump_version.py`

Acceptance criteria:
- release docs describe a complete repeatable flow
- the flow includes verification, not only version bumping

Validation:
- manual doc review against actual repo commands and files

## Task 18: Add One Canonical Local "Necessary 80%" Preflight

Goal:
Give contributors one command sequence that covers the maintenance-critical checks before merging.

Scope:
- combine the Python preflight, dashboard build, and essential dashboard smoke tests into one documented workflow
- keep it cheap enough for regular use

Primary files:
- `docs/PREFLIGHT.md`
- optional helper script under `scripts/`

Acceptance criteria:
- contributors have one obvious maintenance-focused preflight path
- the commands avoid live API calls

Validation:
- run the documented command sequence locally

## Parallel-Safe Tasks

These can run after Task 04 is complete without blocking each other:

- Task 05
- Task 08
- Task 11
- Task 13
- Task 16

These can run after Task 12 is complete:

- Task 14
- Task 15

## Suggested Execution Waves

Wave 1:
- Task 01
- Task 02
- Task 03
- Task 04

Wave 2:
- Task 05
- Task 06
- Task 07
- Task 08
- Task 09
- Task 10

Wave 3:
- Task 11
- Task 12
- Task 13
- Task 14
- Task 15

Wave 4:
- Task 16
- Task 17
- Task 18

## Definition of Done

This task set is done when:

- core research and content-gen contracts are typed and tested
- Python and dashboard regressions are caught in CI
- dashboard smoke coverage is mock-first and reliable
- docs describe the system as it actually behaves
- release and preflight workflows are short, current, and repeatable
