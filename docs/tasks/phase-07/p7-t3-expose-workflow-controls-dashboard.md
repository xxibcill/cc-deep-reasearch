# P7-T3 - Expose Workflow Controls In Dashboard

## Functional Feature Outcome

The dashboard launch form can start staged or planner runs and configure execution controls using backend-compatible request fields.

## Why This Task Exists

The backend request model already supports `workflow`, `concurrent_source_collection`, `max_concurrent_sources`, provider selection, depth, theme, realtime mode, PDF output, and prompt overrides. The dashboard launch form only exposes a smaller subset, and the frontend type still includes older field names like `parallel_mode` and `num_researchers`. This makes the operator console less capable than the backend and increases the risk of silent request drift.

## Scope

- Update dashboard request types to match backend `ResearchRunRequest`.
- Add workflow selection to the launch form.
- Add source collection controls for concurrent collection and max concurrent sources.
- Add provider selection when provider configuration makes that meaningful.
- Keep the launch UI compact and operational rather than turning it into a setup wizard.
- Add frontend tests/e2e coverage for request payloads.

## Current Friction

- `dashboard/src/types/telemetry.ts` omits `workflow`, `concurrent_source_collection`, and `max_concurrent_sources`.
- It includes `parallel_mode` and `num_researchers`, which do not match the current backend request fields.
- `StartResearchForm` sends no workflow field, so all dashboard launches use the backend default staged workflow.

## Implementation Notes

- Update `ResearchRunRequest` in `dashboard/src/types/telemetry.ts`:

```ts
export type ResearchWorkflow = 'staged' | 'planner';

export interface ResearchRunRequest {
  query: string;
  depth?: 'quick' | 'standard' | 'deep';
  min_sources?: number | null;
  output_format?: ResearchOutputFormat;
  search_providers?: string[] | null;
  cross_reference_enabled?: boolean | null;
  team_size?: number | null;
  concurrent_source_collection?: boolean | null;
  max_concurrent_sources?: number | null;
  realtime_enabled?: boolean;
  pdf_enabled?: boolean;
  workflow?: ResearchWorkflow;
  theme?: string | null;
  agent_prompt_overrides?: Record<string, AgentPromptOverride>;
}
```

- Remove or deprecate frontend-only request fields that the backend does not consume.
- Add a compact workflow control:
  - default: `staged`
  - beta option: `planner`
  - supporting copy should be short and factual.
- Add concurrent collection controls in advanced settings:
  - toggle: `concurrent_source_collection`
  - numeric/select: `max_concurrent_sources`, constrained to backend limits.
- Provider selection should only list supported configured providers. If this cannot be fetched cleanly yet, keep provider selection out of the first slice and document that it depends on config API support.
- The request builder should omit null/undefined fields unless the operator intentionally changed them.

## Test Plan

- Unit test request construction from launch form state.
- E2E test selecting planner workflow and assert posted JSON includes `workflow: "planner"`.
- E2E test enabling/disabling concurrent source collection and assert correct backend field names.
- E2E test old dashboard launch still defaults to staged.
- Typecheck catches any use of `parallel_mode` or `num_researchers` in request payloads.

## Acceptance Criteria

- Dashboard launch can select `staged` or `planner`.
- Dashboard request payload uses backend field names exactly.
- The default dashboard path remains staged.
- Concurrent source collection controls are available without cluttering the primary launch flow.
- Tests cover staged default and planner opt-in request payloads.

## Verification Commands

```bash
cd dashboard && npm run lint
cd dashboard && npm run build
cd dashboard && npx playwright test tests/e2e/app.spec.ts tests/e2e/use-dashboard.spec.ts
uv run pytest tests/test_web_server_research_run_routes.py -x
```

## Risks

- Too many controls can make the launch form harder to use. Keep advanced controls collapsed by default.
- Provider selection can be misleading if unsupported providers are listed. Do not expose providers that `build_search_provider()` cannot construct.
