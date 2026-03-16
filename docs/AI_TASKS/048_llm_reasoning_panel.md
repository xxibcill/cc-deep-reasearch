# Task 048: Add The LLM Reasoning Inspection Panel

Status: Planned

## Objective

Expose prompt, response, token, and route metadata in a dedicated dashboard panel so operators can inspect LLM-backed decisions without digging through telemetry files.

## Scope

- add a reasoning panel tied to LLM events on the session detail page
- display prompt and response content with readable formatting and safe truncation
- show token counts, latency, model, provider, and transport metadata
- group related route-selection and completion events into one inspectable interaction when possible
- keep sensitive or missing fields masked or omitted according to the telemetry payload actually available

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/components/session-details.tsx`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/components/llm-reasoning-panel.tsx`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/lib/telemetry-transformers.ts`
- `/Users/jjae/Documents/guthib/cc-deep-research/dashboard/src/types/telemetry.ts`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/telemetry/live.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/docs/REALTIME_MONITORING.md`

## Dependencies

- [042_analysis_service_llm_router_integration.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/042_analysis_service_llm_router_integration.md)
- [043_llm_route_telemetry_and_session_metadata.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/AI_TASKS/043_llm_route_telemetry_and_session_metadata.md)

## Acceptance Criteria

- operators can open a dedicated LLM detail panel from relevant events
- the panel shows prompt, response, token usage, latency, model, provider, and transport when present
- related route metadata is visible without reading separate raw telemetry entries
- large prompt or response bodies are truncated or collapsible instead of overwhelming the page

## Exit Criteria

- the dashboard can answer what the model was asked, what it returned, and which route handled the call
- missing fields or redacted payloads fail gracefully without breaking the session screen

## Suggested Verification

- run `npm run lint` in `dashboard/`
- add or update telemetry tests if new live payload fields are required
- manually verify at least one Claude CLI-backed and one API-backed LLM interaction if available
