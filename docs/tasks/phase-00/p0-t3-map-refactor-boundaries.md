# P0-T3 - Map Refactor Boundaries

## Outcome

The first refactor boundaries are documented before moving code.

## Scope

- Map content-gen pipeline execution ownership.
- Map API route ownership for `web_server.py` and `content_gen/router.py`.
- Map dashboard state and API client ownership.
- Map model/storage contract boundaries.

## Implementation Notes

- Prefer dependency and call-flow notes over a file-size inventory.
- Highlight compatibility shims and legacy paths that must stay stable temporarily.
- Identify which boundaries need mocked external dependencies.

## Acceptance Criteria

- The content-gen pipeline boundary is selected as the first implementation target.
- The map identifies service boundaries for later phases.
- The map identifies which tests should become boundary tests.

## Verification

- The map references concrete modules and entry points.

---

## Implementation Results

### 1. Content-Gen Pipeline Execution Ownership

**Entry Point**: `src/cc_deep_research/content_gen/pipeline.py` → `ContentGenPipeline`
**Orchestrator**: `src/cc_deep_research/content_gen/orchestrator.py` → `ContentGenOrchestrator`

**Pipeline Stages** (in execution order):
```
backlog → angle → research → argument_map → scripting → visual → production → packaging → qc → publish
```

**Stage Orchestrators** (`src/cc_deep_research/content_gen/stages/`):
- `backlog.py` → `BacklogStageOrchestrator`
- `angle.py` → `AngleStageOrchestrator`
- `research.py` → `ResearchStageOrchestrator`
- `argument_map.py` → `ArgumentMapStageOrchestrator`
- `scripting.py` → `ScriptingStageOrchestrator`
- `visual.py` → `VisualStageOrchestrator`
- `production.py` → `ProductionStageOrchestrator`
- `packaging.py` → `PackagingStageOrchestrator`
- `qc.py` → `QCStageOrchestrator`
- `publish.py` → `PublishStageOrchestrator`

**Pipeline Context**: `PipelineContext` (defined in `models/pipeline.py`)

**First Refactor Boundary Selected**: Content-gen pipeline execution — the `ContentGenOrchestrator` coordinates all stages and holds `PipelineContext`. This is the critical path for Phase 01 work.

---

### 2. API Route Ownership

**Main Web Server**: `src/cc_deep_research/web_server.py`
- Manages research session lifecycle (`/api/research-runs/*`)
- Manages telemetry queries (`/api/sessions/*`)
- WebSocket endpoint: `/ws/session/{session_id}`

**Content-Gen Router**: `src/cc_deep_research/content_gen/router.py` → `register_content_gen_routes()`
- Registers pipeline management routes (`/api/content-gen/pipelines/*`)
- Registers backlog routes (`/api/content-gen/backlog/*`)
- Registers brief routes (`/api/content-gen/briefs/*`)
- Registers scripting routes (`/api/content-gen/scripts/*`)
- Registers strategy routes (`/api/content-gen/strategy/*`)
- Registers maintenance routes (`/api/content-gen/maintenance/*`)
- WebSocket endpoint: `/ws/content-gen/pipeline/{pipeline_id}`

**Route Registration Flow**:
```
web_server.py → register_content_gen_routes(app, event_router, pipeline_jobs)
                ↓
router.py → registers all /api/content-gen/* routes
```

**Job Registries** (defined in `progress.py`):
- `ResearchRunJobRegistry` - manages research run jobs
- `PipelineRunJobRegistry` - manages content-gen pipeline jobs

---

### 3. Dashboard State and API Client Ownership

**Dashboard Frontend**: `dashboard/` (Next.js)
- Communicates with FastAPI backend via REST and WebSocket
- Key API client patterns: fetches from `/api/sessions/*`, `/api/content-gen/*`

**Dashboard Backend Runtime** (`web_server.py:90`):
```python
@dataclass(slots=True)
class DashboardBackendRuntime:
    event_router: EventRouter          # WebSocket broadcasting
    jobs: ResearchRunJobRegistry        # Research run job registry
    pipeline_jobs: PipelineRunJobRegistry  # Content-gen pipeline jobs
    maintenance_scheduler: MaintenanceScheduler | None
```

**Event Router** (`src/cc_deep_research/event_router.py`):
- Manages WebSocket connections and message routing
- Used for real-time updates to both research sessions and pipeline progress

**Telemetry Stores**:
- `telemetry/` - research session telemetry
- `content_gen/storage/content_gen_telemetry_store.py` - content-gen specific telemetry

---

### 4. Model/Storage Contract Boundaries

**Core Models** (`content_gen/models/`):
- `contracts.py` - Stage contracts (what each stage must produce)
- `shared.py` - Enums and shared types
- `pipeline.py` - `PipelineContext`, stage enums, lane context
- `backlog.py` - `BacklogItem`, `BacklogOutput`
- `brief.py` - `OpportunityBrief`, `ManagedBriefOutput`
- `production.py` - Production stage models
- `script.py` - Scripting models
- `research.py` - Research stage models
- `learning.py` - Performance learning models
- `angle.py` - Angle generation models

**Storage Layer** (`content_gen/storage/`):
- `backlog_store.py`, `sqlite_backlog_store.py` - Backlog persistence
- `brief_store.py`, `sqlite_brief_store.py` - Brief persistence
- `scripting_store.py` - Script storage
- `strategy_store.py` - Strategy memory
- `audit_store.py` - Audit logging
- `performance_learning_store.py` - Learning persistence
- `content_gen_telemetry_store.py` - Telemetry
- `publish_queue_store.py` - Publish queue

**Storage Path Configuration**: `storage/_paths.py` - Base paths for all storage

---

### 5. Compatibility Shims and Legacy Paths

**Legacy Orchestrator** (`content_gen/legacy_orchestrator.py`):
- Stub for backwards compatibility during transition
- Should be removed after migration complete

**Model Imports**: `models/__init__.py` re-exports all public types
- Currently has import sorting issues (I001) - pre-existing

---

### 6. Boundaries Needing Mocked External Dependencies

For isolated testing of content-gen pipeline:
- **LLM Router** (`llm/`) - needs mocked responses for agent calls
- **Tavily Search** - needs mocked search results
- **Config** - needs test config fixture

---

### 7. Recommended Boundary Tests

Based on the dependency map, these tests should become boundary tests in later phases:

1. **Pipeline execution boundary**: Test `ContentGenOrchestrator` with mocked stage orchestrators
2. **API contract boundary**: Test `router.py` routes with mocked storage
3. **Storage contract boundary**: Test each store with interface contracts
4. **WebSocket boundary**: Test event router with mocked connections
