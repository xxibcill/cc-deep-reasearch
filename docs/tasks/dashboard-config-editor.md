# Dashboard Config Editor Tasks

## Goal

Allow operators to view and update persistent application configuration from the dashboard, with clear handling for environment-variable overrides and sensitive fields.

## Scope

- Edit the same YAML-backed config used by CLI and future research runs
- Surface effective runtime config versus persisted file config
- Keep active runs unchanged after a config save
- Treat API keys and other secrets as masked values, not plain-text round trips

## Non-Goals

- Live-reconfiguring in-flight runs
- Full reset/import/export flow in v1
- Editing every config field on day one

## Task Breakdown

### 1. Create shared config mutation service

**Why**
The current config update logic is CLI-specific. The dashboard needs a reusable backend service instead of importing `click`-based helpers.

**Work**
- Add a new backend-facing config service under `src/cc_deep_research/config/`
- Move dot-path lookup into a non-CLI helper
- Add typed patch application for nested fields
- Validate all updates through `Config`
- Save changes atomically to the YAML file

**Acceptance criteria**
- Backend code can load, patch, validate, and save config without CLI dependencies
- Invalid keys and invalid values return structured errors
- Partial updates do not mutate unrelated fields

**Likely files**
- `src/cc_deep_research/config/io.py`
- `src/cc_deep_research/config/schema.py`
- `src/cc_deep_research/config/__init__.py`
- `src/cc_deep_research/cli/shared.py`
- new: `src/cc_deep_research/config/service.py`

### 2. Define dashboard config API contract

**Why**
The frontend needs a stable shape for loading current settings, showing override status, and sending partial updates.

**Work**
- Add request/response models for config read and patch operations
- Include config file path metadata
- Include `persisted_config`
- Include `effective_config`
- Include `overridden_fields`
- Include masked secret metadata for sensitive fields

**Acceptance criteria**
- Contract distinguishes persisted file values from env-overridden runtime values
- Secret fields are never returned in plain text by default
- Patch contract supports partial updates

**Likely files**
- `src/cc_deep_research/web_server.py`
- `src/cc_deep_research/research_runs/models.py` or new dedicated config API model module

### 3. Add `GET /api/config`

**Why**
The dashboard needs an initial read endpoint before rendering any settings form.

**Work**
- Add a route that loads config from the default config path
- Return persisted config, effective config, path, and override metadata
- Mask sensitive values in the response

**Acceptance criteria**
- Endpoint succeeds when the config file exists
- Endpoint still works when the config file does not exist yet
- Response clearly indicates whether the file is missing and what defaults are active

**Likely files**
- `src/cc_deep_research/web_server.py`
- `src/cc_deep_research/config/io.py`

### 4. Add `PATCH /api/config`

**Why**
The dashboard needs a write path for saving updated settings.

**Work**
- Accept partial updates
- Validate and persist changes through the shared config service
- Return the refreshed config payload after save
- Reject writes to env-overridden fields unless the UX explicitly allows “save anyway”

**Acceptance criteria**
- Valid patches persist to disk
- Invalid patches return field-specific errors
- Saving a field overridden by env vars gives a clear warning or structured conflict

**Likely files**
- `src/cc_deep_research/web_server.py`
- new: `src/cc_deep_research/config/service.py`

### 5. Add secret-field policy

**Why**
Fields like Tavily and LLM provider API keys cannot be treated like normal form values.

**Work**
- Define which fields are sensitive
- Return masked placeholders plus presence metadata
- Support explicit actions such as replace and clear
- Prevent accidental echoing of secret values in logs or API errors

**Acceptance criteria**
- API responses never expose configured secrets in plain text
- Replace and clear behavior is deterministic
- Secret handling works for list-style key fields

**Likely files**
- `src/cc_deep_research/config/schema.py`
- new: `src/cc_deep_research/config/service.py`
- `src/cc_deep_research/web_server.py`

### 6. Add backend tests for config read/write flows

**Why**
This feature is easy to regress because config combines file values, defaults, and env overrides.

**Work**
- Test missing config file behavior
- Test persisted config read behavior
- Test env override visibility
- Test invalid-key and invalid-value responses
- Test secret masking and replace flows

**Acceptance criteria**
- Tests cover both happy path and failure modes
- Tests verify that env overrides remain effective after patching file config

**Likely files**
- `tests/test_config.py`
- `tests/test_web_server.py`

### 7. Add frontend config API client

**Why**
The dashboard already centralizes HTTP calls in one place.

**Work**
- Add `getConfig()`
- Add `updateConfig()`
- Normalize API errors into user-facing messages

**Acceptance criteria**
- Frontend can fetch config and send partial updates through shared API helpers
- Error handling matches existing dashboard patterns

**Likely files**
- `dashboard/src/lib/api.ts`
- `dashboard/src/types/telemetry.ts` or new dedicated config types file

### 8. Add settings page or settings panel shell

**Why**
The feature needs a stable UI surface separate from the run-status views.

**Work**
- Add a dedicated settings route or a homepage panel
- Load config on mount
- Show loading, empty, and error states

**Acceptance criteria**
- Operators can reach config editing without interfering with session views
- The page renders cleanly on desktop and mobile

**Likely files**
- `dashboard/src/app/page.tsx` or new `dashboard/src/app/settings/page.tsx`

### 9. Implement v1 editable fields

**Why**
Start with safe, high-value fields before opening the entire schema.

**Recommended v1 fields**
- `search.providers`
- `search.depth`
- `research.enable_cross_ref`
- `search_team.team_size`
- `search_team.parallel_execution`
- `output.format`
- `output.save_dir`
- `llm.route_defaults.*`

**Work**
- Build form controls for the v1 field set
- Show helper text for each setting
- Pre-populate values from persisted or effective config

**Acceptance criteria**
- Operators can edit and save the v1 field set from the dashboard
- Field validation errors are shown inline or in a clear summary

**Likely files**
- new: `dashboard/src/components/config-editor.tsx`
- `dashboard/src/components/ui/*`

### 10. Show env override state in the UI

**Why**
Without this, saved config may appear broken when runtime env vars still win.

**Work**
- Mark fields currently overridden by env vars
- Show both persisted and effective values when they differ
- Disable edits or add warning copy for overridden fields

**Acceptance criteria**
- Users can tell why a saved value is not the effective runtime value
- Override messaging is visible without opening dev tools

**Likely files**
- new: `dashboard/src/components/config-editor.tsx`
- `dashboard/src/lib/api.ts`

### 11. Add secret editing UI

**Why**
Credentials need a separate interaction model from normal settings.

**Work**
- Show “configured” state instead of the raw value
- Add replace and clear actions
- Confirm destructive clear actions

**Acceptance criteria**
- Users can replace a key without seeing the previous value
- Clearing a key requires deliberate action

**Likely files**
- new: `dashboard/src/components/config-secrets-panel.tsx`
- `dashboard/src/components/ui/alert-dialog.tsx`

### 12. Clarify runtime behavior after save

**Why**
Config edits affect future runs, not active runs already prepared in memory.

**Work**
- Add copy in the UI explaining save semantics
- Optionally show a success note: “Applies to new runs”

**Acceptance criteria**
- The UI does not imply live mutation of in-flight runs
- Operators know when a restart is or is not required

**Relevant code**
- `src/cc_deep_research/research_runs/service.py`

### 13. Add frontend tests

**Why**
The settings UI includes stateful async behavior, masked fields, and error handling.

**Work**
- Test initial load
- Test save success
- Test validation error display
- Test env override messaging
- Test secret replace and clear flows

**Acceptance criteria**
- Core config editor flows are covered by component or page tests

**Likely files**
- new tests under `dashboard/`

### 14. Update docs

**Why**
Operators need to know what the dashboard can change and how env vars interact with saved config.

**Work**
- Update the dashboard guide
- Update usage docs for config precedence
- Document secret-handling behavior

**Acceptance criteria**
- Docs explain effective-vs-persisted config clearly
- Docs list the supported editable fields in v1

**Likely files**
- `docs/DASHBOARD_GUIDE.md`
- `docs/USAGE.md`

## Suggested Delivery Order

### Phase 1
- Task 1
- Task 2
- Task 3
- Task 4
- Task 6

### Phase 2
- Task 7
- Task 8
- Task 9
- Task 10

### Phase 3
- Task 5
- Task 11
- Task 13
- Task 14

## Risks To Watch

- Env overrides can make saved values appear ineffective
- Secret fields can leak if raw `model_dump()` output is reused in APIs
- The current CLI parsing logic is too weak for a full dashboard patch contract
- Multiple saves should use atomic writes to avoid partial config corruption
