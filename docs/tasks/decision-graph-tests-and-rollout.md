# Decision Graph Tests And Rollout Tasks

## Goal

Ship decision graphs incrementally without breaking the existing telemetry explorer, and add enough tests to keep the feature trustworthy as telemetry coverage grows.

## Scope

- Add backend and API contract tests
- Add UI behavior tests
- Define rollout phases and acceptance gates

## Non-Goals

- One-shot implementation of every decision source in the repository
- A full benchmark suite for graph quality in v1

## Task Breakdown

### 1. Add backend derivation fixtures

**Why**
Decision graphs depend on structured telemetry examples more than on generic unit scaffolding.

**Work**
- Create compact event fixtures covering:
  - route selection and fallback
  - continue/stop iteration
  - degraded execution and mitigation
  - planner choice followed by state change

**Acceptance criteria**
- Tests use realistic telemetry shapes instead of overly synthetic payloads
- Fixtures are reusable across derivation and API tests

**Likely files**
- `tests/test_telemetry.py`
- `tests/fixtures/` if new JSON fixtures are needed

### 2. Add backend correctness tests

**Why**
Graph derivation must be deterministic and conservative.

**Work**
- Verify:
  - node and edge counts
  - explicit and inferred edge flags
  - cause links
  - rejected-option edges
  - empty graph output

**Acceptance criteria**
- A change in graph structure requires a test update, not silent drift

**Likely files**
- `tests/test_telemetry.py`
- `tests/test_monitoring.py`

### 3. Add API contract tests

**Why**
Session detail is consumed by the dashboard and should not regress when graph fields are added.

**Work**
- Verify `GET /api/sessions/{session_id}` returns `decision_graph`
- Verify both live and historical detail paths include it
- Verify `include_derived=false` suppresses graph derivation

**Acceptance criteria**
- API responses remain backward-compatible
- New graph field is present whenever derived outputs are enabled

**Likely files**
- `tests/test_web_server.py`

### 4. Add trace bundle export tests

**Why**
Trace export should remain a trustworthy offline artifact for review and debugging.

**Work**
- Verify exported bundles include `decision_graph`
- Verify empty graphs serialize correctly
- Verify schema-version updates if bundle shape changes

**Acceptance criteria**
- Decision graph survives trace export without field loss

**Likely files**
- trace bundle export test coverage where session export is already tested
- `src/cc_deep_research/telemetry/bundle.py` as implementation target

### 5. Add dashboard interaction tests

**Why**
The graph will introduce new UI state and selection flows.

**Work**
- Test:
  - empty state
  - render from API result
  - click node to inspect event
  - explicit/inferred styling
  - view-mode switch behavior

**Acceptance criteria**
- Graph UI remains stable while filters and detail panels evolve

**Likely files**
- frontend test files matching the dashboard setup

### 6. Roll out in phases

**Why**
This feature has a natural dependency order and should not be shipped as one large opaque change.

**Recommended rollout**

**Phase 1**
- backend graph contract
- derivation logic
- API delivery
- trace bundle export

**Phase 2**
- explicit telemetry coverage improvements
- decision graph UI
- summary-panel integration

**Phase 3**
- richer filtering
- graph export polish
- run-to-run comparison ideas

**Acceptance criteria**
- Each phase ships something independently useful
- UI work does not block graph-contract stabilization

### 7. Document limits honestly

**Why**
Operators should know when a graph is sparse because telemetry is missing versus when nothing important happened.

**Work**
- Document:
  - explicit versus inferred links
  - telemetry coverage gaps
  - current decision sources included in the graph
- Update operator-facing docs after implementation lands

**Acceptance criteria**
- The feature is documented as an observability surface, not as authoritative truth beyond its telemetry coverage

**Likely files**
- `README.md`
- `docs/TELEMETRY.md`
- `docs/DASHBOARD_GUIDE.md`

