# Content Generation

Content generation is operated through the Next.js dashboard and FastAPI
routes. The former `content-gen` command tree has been removed.

## Lifecycle

The pipeline context moves through these ordered stages:

| # | Stage | Responsibility |
| ---: | --- | --- |
| 0 | `load_strategy` | load positioning, pillars, and operating rules |
| 1 | `plan_opportunity` | turn a theme into an opportunity brief |
| 2 | `build_backlog` | create candidate ideas |
| 3 | `score_ideas` | rank and select production lanes |
| 4 | `generate_angles` | build the thesis and angle |
| 5 | `build_research_pack` | collect evidence and sources |
| 6 | `build_argument_map` | structure claims and support |
| 7 | `run_scripting` | generate and revise the script |
| 8 | `visual_translation` | convert the script into visual direction |
| 9 | `production_brief` | assemble execution requirements |
| 10 | `packaging` | produce platform packaging |
| 11 | `human_qc` | enforce the human release gate |
| 12 | `publish_queue` | create or update publish readiness |
| 13 | `performance_analysis` | reserved for the performance feedback loop |

Stages 0–12 have stage orchestrators. Stage 13 currently uses a no-op
coordinator placeholder; performance learning is available through storage and
API services, but it is not yet an automated terminal pipeline stage.

## Start and observe a pipeline

Use the Content workspace in the dashboard, or call:

```bash
curl -sS http://127.0.0.1:8000/api/content-gen/pipelines \
  -H 'content-type: application/json' \
  -d '{"theme":"pricing psychology"}'
```

The response is asynchronous. Use:

- `GET /api/content-gen/pipelines/{pipeline_id}` for durable status;
- `WS /ws/content-gen/pipeline/{pipeline_id}` for live progress;
- `POST /api/content-gen/pipelines/{pipeline_id}/stop` to stop;
- `POST /api/content-gen/pipelines/{pipeline_id}/resume` to resume;
- `POST /api/content-gen/qc/{pipeline_id}/approve` for the release gate.

## API areas

| Area | Route prefix |
| --- | --- |
| Pipelines and QC | `/api/content-gen/pipelines`, `/api/content-gen/qc` |
| Scripting runs | `/api/content-gen/scripting`, `/api/content-gen/scripts` |
| Backlog | `/api/content-gen/backlog` |
| Briefs and revisions | `/api/content-gen/briefs` |
| Backlog/brief assistants | `/api/content-gen/backlog-chat`, `/api/content-gen/backlog-ai` |
| Strategy and learning | `/api/content-gen/strategy`, `/api/content-gen/learnings` |
| QC issues | `/api/content-gen/qc-issues` |
| Publish readiness | `/api/content-gen/publish` |
| Reusable assets | `/api/content-gen/assets` |
| Audit and maintenance | `/api/content-gen/audit`, `/api/content-gen/maintenance` |

The FastAPI OpenAPI document at `http://127.0.0.1:8000/docs` is the
authoritative request/response reference.

## Persistent operating records

Content-generation state defaults to the same configuration directory as the
main application. Depending on configured backends it includes:

- strategy and learning YAML records;
- SQLite or YAML backlog and brief stores;
- brief revision history;
- pipeline contexts and scripting runs;
- QC issues, audit events, publish readiness, and reusable assets.

Paths can be overridden through the typed `content_gen` configuration. Use the
operations data-path endpoint and back up the resolved files before migrations
or retention work.

## Human gates

Automation must not silently bypass:

- brief approval and revision history;
- idea selection;
- evidence/claim quality checks;
- human QC at stage 11;
- publish readiness and blocker records.

Resume operations reapply prerequisites and gate policies. They are not an
arbitrary jump to a later stage.

## Code boundaries

- route registration and transport mapping:
  [`src/cc_deep_research/content_gen/router.py`](../src/cc_deep_research/content_gen/router.py)
- asynchronous pipeline jobs:
  [`src/cc_deep_research/content_gen/pipeline_run_service.py`](../src/cc_deep_research/content_gen/pipeline_run_service.py)
- stage sequencing and gates:
  [`src/cc_deep_research/content_gen/pipeline.py`](../src/cc_deep_research/content_gen/pipeline.py)
- typed contexts:
  [`src/cc_deep_research/content_gen/models/`](../src/cc_deep_research/content_gen/models)
- stage implementations:
  [`src/cc_deep_research/content_gen/stages/`](../src/cc_deep_research/content_gen/stages)
- persistence adapters:
  [`src/cc_deep_research/content_gen/storage/`](../src/cc_deep_research/content_gen/storage)

Keep HTTP validation in the router/API services, sequencing in the pipeline,
and durable behavior in storage adapters. Do not reintroduce a second command
implementation of the workflow.

For deeper domain contracts, see [`content-gen-backlog.md`](content-gen-backlog.md),
[`brief-management.md`](brief-management.md), [`beats.md`](beats.md), and
[`content-gen-artifact.md`](content-gen-artifact.md).
