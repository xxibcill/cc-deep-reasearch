# Decision Graph API And Bundle Tasks

Status: Done

## Goal

Expose `decision_graph` everywhere operators already consume derived outputs: live session detail, historical session detail, and portable trace bundles.

## Scope

- Add `decision_graph` to backend session-detail responses
- Add `decision_graph` to frontend response types
- Include `decision_graph` in trace bundle export

## Non-Goals

- Building a separate decision-graph-only endpoint in v1
- Reworking the current session detail pagination model

## Task Breakdown

### 1. Add `decision_graph` to live session detail

**Why**
The browser monitor already consumes live derived outputs from the main session-detail path.

**Work**
- Extend live session detail to return `decision_graph`
- Make empty-session responses include an empty graph payload
- Respect `include_derived=False` by returning an empty graph

**Acceptance criteria**
- Live sessions expose `decision_graph` in the same response as `decisions`
- No-derived mode avoids expensive graph derivation

**Likely files**
- `src/cc_deep_research/telemetry/live.py`

### 2. Add `decision_graph` to historical session detail

**Why**
The dashboard falls back to historical session detail when a run is no longer live.

**Work**
- Add `decision_graph` to historical query results
- Keep output shape aligned with live detail
- Make historical and live consumers interchangeable

**Acceptance criteria**
- Historical detail returns the same graph shape as live detail
- Existing detail consumers do not need special-case handling

**Likely files**
- `src/cc_deep_research/telemetry/query.py`
- `src/cc_deep_research/web_server.py`

### 3. Thread `decision_graph` through the API response

**Why**
The dashboard currently fetches all derived outputs through `GET /api/sessions/{session_id}`.

**Work**
- Add `decision_graph` to `_query_session_api_detail()`
- Add it to the JSON response returned by `GET /api/sessions/{session_id}`
- Preserve backward compatibility for clients that ignore the new field

**Acceptance criteria**
- The session detail API returns `decision_graph` for both live and historical sessions
- Missing sessions still return the same 404 behavior

**Likely files**
- `src/cc_deep_research/web_server.py`

### 4. Add `decision_graph` to frontend types and API mapping

**Why**
The dashboard TypeScript types are the contract the UI actually consumes.

**Work**
- Add `DecisionGraphNode`, `DecisionGraphEdge`, and `DecisionGraph` to dashboard types
- Extend `DerivedOutputs` and `SessionDetailResponse`
- Map `response.data.decision_graph` in the API client

**Acceptance criteria**
- Frontend type-checking passes with the new field
- Session detail fetches expose `decisionGraph` alongside existing derived outputs

**Likely files**
- `dashboard/src/types/telemetry.ts`
- `dashboard/src/lib/api.ts`

### 5. Include `decision_graph` in trace bundles

**Why**
Portable trace export should preserve the same high-level analysis operators see in the dashboard.

**Work**
- Add `decision_graph` to `derived_outputs` in trace bundle export
- Thread the field through session trace export
- Bump bundle schema version if needed

**Acceptance criteria**
- Exported trace bundles include `decision_graph`
- Older consumers can safely ignore the new field

**Likely files**
- `src/cc_deep_research/telemetry/bundle.py`
- `src/cc_deep_research/session_store.py`

### 6. Add API and export tests

**Why**
Graph derivation can be correct while serialization still regresses.

**Work**
- Add API tests for live and historical session detail including `decision_graph`
- Add export tests for trace bundle inclusion
- Add no-derived mode coverage

**Acceptance criteria**
- `tests/test_web_server.py` verifies `decision_graph` is present
- `tests/test_telemetry.py` verifies live/historical detail include it
- trace bundle tests verify the exported shape

**Likely files**
- `tests/test_web_server.py`
- `tests/test_telemetry.py`
- existing trace-bundle test coverage if present
