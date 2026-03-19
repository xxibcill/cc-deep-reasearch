# Task 011: Enrich Session Summaries For Management Workflows

Status: Done

## Objective

Make the dashboard session list actionable by returning enough summary metadata for operators to decide what to inspect, stop, archive, or delete without opening each session first.

## Scope

- extend merged session summaries with saved-session metadata such as query, depth, and completed timestamp where available
- expose basic artifact state such as whether a saved session payload and rendered report are available
- keep missing fields explicit for telemetry-only sessions instead of forcing frontend guesswork
- avoid loading full session detail payloads just to render the home-page list

## Target Files

- `src/cc_deep_research/session_store.py`
- `src/cc_deep_research/web_server.py`
- `dashboard/src/types/telemetry.ts`
- `dashboard/src/lib/telemetry-transformers.ts`

## Dependencies

- [010_deletion_safety_and_validation.md](010_deletion_safety_and_validation.md)

## Acceptance Criteria

- session list responses include a human-meaningful label beyond raw session id
- summary metadata is normalized consistently for live, historical, and partially persisted sessions
- frontend list rows can show richer management context without additional per-session API calls

## Suggested Verification

- run `uv run pytest tests/test_web_server.py tests/test_session_store.py`
- run `npm run lint` in `dashboard`
