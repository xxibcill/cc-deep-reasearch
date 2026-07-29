# Documentation Guide

These are the maintained entry points for operators and contributors.

## Start here

- [`USAGE.md`](USAGE.md): install, configure, launch, and use the supported dashboard/API workflow
- [`PREFLIGHT.md`](PREFLIGHT.md): local validation and live-provider readiness checks
- [`DASHBOARD_GUIDE.md`](DASHBOARD_GUIDE.md): dashboard architecture, pages, and backend integration
- [`../dashboard/README.md`](../dashboard/README.md): frontend development and validation commands
- [`REALTIME_MONITORING.md`](REALTIME_MONITORING.md): live event flow, session APIs, and WebSockets
- [`TELEMETRY.md`](TELEMETRY.md): persisted telemetry, retention, and analytics

## Research and content workflows

- [`RESEARCH_WORKFLOW.md`](RESEARCH_WORKFLOW.md): research execution phases and package ownership
- [`RESEARCH_WORKFLOW_AGENT_INTERACTIONS.md`](RESEARCH_WORKFLOW_AGENT_INTERACTIONS.md): request-to-report interaction trace
- [`content-generation.md`](content-generation.md): supported content-generation lifecycle and APIs
- [`content-gen-backlog.md`](content-gen-backlog.md): backlog model and lifecycle
- [`content-gen-artifact.md`](content-gen-artifact.md): artifact and production boundaries
- [`brief-management.md`](brief-management.md): brief lifecycle and revision model
- [`beats.md`](beats.md): scripting beat structures and targeted revision
- [`opportunity-radar-prd.md`](opportunity-radar-prd.md): Opportunity Radar product requirements
- [`radar/operator-playbook.md`](radar/operator-playbook.md): Opportunity Radar operations

## Maintenance

- [`DEPENDENCY_MAINTENANCE.md`](DEPENDENCY_MAINTENANCE.md): dependency policy and audit exceptions
- [`RELEASING.md`](RELEASING.md): release checklist
- [`REFACTOR_REGRESSION_CHECKLIST.md`](REFACTOR_REGRESSION_CHECKLIST.md): focused regression checks

Files under [`tasks/`](tasks/) and [`review/`](review/) are dated engineering records.
They are historical evidence, not current operating instructions.

## Current code layout

- FastAPI composition: [`src/cc_deep_research/web_server.py`](../src/cc_deep_research/web_server.py)
- HTTP and WebSocket routes: [`src/cc_deep_research/web_server_routes/`](../src/cc_deep_research/web_server_routes)
- browser-started research runs: [`src/cc_deep_research/research_runs/`](../src/cc_deep_research/research_runs)
- research orchestration: [`src/cc_deep_research/orchestration/`](../src/cc_deep_research/orchestration)
- content generation: [`src/cc_deep_research/content_gen/`](../src/cc_deep_research/content_gen)
- Opportunity Radar: [`src/cc_deep_research/radar/`](../src/cc_deep_research/radar)
- telemetry and analytics: [`src/cc_deep_research/telemetry/`](../src/cc_deep_research/telemetry)
- Next.js dashboard: [`dashboard/src/`](../dashboard/src)

The former Click CLI and Streamlit dashboard are retired. Do not add new
operator workflows that depend on those removed entry points.
