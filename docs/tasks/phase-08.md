# Phase 08 - Local Knowledge Graph

## Functional Feature Outcome

Research runs compound into a local, source-backed personal knowledge graph with a Markdown-first wiki, immutable raw evidence, queryable graph index, lintable claim provenance, and dashboard inspection.

## Why This Phase Exists

The current research workflow produces strong saved sessions and reports, but each run still behaves mostly like an isolated artifact. This phase upgrades the system into a cumulative local knowledge workspace following Andrej Karpathy's personal knowledge graph pattern: preserve raw inputs, let an LLM maintain a readable Markdown wiki, keep `index.md` and `log.md` as navigation and change history, derive a graph index from the wiki/evidence, and periodically lint the knowledge base for gaps, stale claims, contradictions, and unsupported synthesis. The first milestone should attach after session/report generation so the production research path remains stable; later tasks can feed prior knowledge back into planning and retrieval.

## Scope

- Create a local knowledge vault under the cc-deep-research config directory with immutable raw snapshots, Markdown wiki pages, and a rebuildable SQLite graph index.
- Convert completed `ResearchSession` payloads, reports, source metadata, query provenance, findings, claims, and gaps into source-backed wiki pages and graph nodes/edges.
- Add knowledge CLI commands for initialization, session ingest/backfill, index rebuild, graph export, linting, and inspection.
- Feed prior knowledge into research planning and query expansion once post-run ingest is stable.
- Expose a dashboard knowledge graph and inspector using existing graph visualization patterns.
- Add benchmark and lint gates that keep claims traceable to sources and keep stale or contradictory knowledge visible.

## Tasks

| Task | Summary |
| --- | --- |
| [P8-T1](../tasks/phase-08/p8-t1-define-knowledge-vault-contracts.md) | Define the Markdown-first knowledge vault, graph schema, config paths, and typed contracts. |
| [P8-T2](../tasks/phase-08/p8-t2-ingest-research-sessions.md) | Ingest completed research sessions into immutable raw snapshots, wiki pages, and graph records. |
| [P8-T3](../tasks/phase-08/p8-t3-add-knowledge-cli-and-linting.md) | Add init, ingest, backfill, rebuild, export, inspect, and lint commands for the local knowledge base. |
| [P8-T4](../tasks/phase-08/p8-t4-use-knowledge-in-research-planning.md) | Use prior knowledge to improve strategy analysis, query expansion, follow-up search, and source reuse. |
| [P8-T5](../tasks/phase-08/p8-t5-expose-knowledge-dashboard.md) | Add a dashboard knowledge graph with filters, inspectors, lint queues, and session-to-knowledge traces. |
| [P8-T6](../tasks/phase-08/p8-t6-add-knowledge-benchmark-gates.md) | Add regression gates for ingest quality, claim provenance, graph integrity, lint health, and planning impact. |

## Dependencies

- Phase 07 should keep staged and planner workflow outputs behind the same `ResearchSession.metadata` contract.
- Session persistence, markdown report caching, source provenance, claim evidence, and content hydration metadata must remain stable enough for deterministic ingest.
- The first implementation should work offline from saved sessions and cached reports without requiring live provider credentials.
- LLM-assisted wiki rewriting must be optional; deterministic extraction must be enough to build a usable graph.
- Existing dashboard graph components should be reused before adding a new visualization dependency.

## Exit Criteria

- `cc-deep-research knowledge init` creates a local vault with `raw/`, `wiki/`, `graph/`, `schema/`, `wiki/index.md`, and `wiki/log.md`.
- A completed research run can be ingested into raw snapshots, Markdown wiki pages, and SQLite graph nodes/edges.
- Claims, findings, gaps, sources, queries, and sessions have stable IDs and source-backed provenance.
- `cc-deep-research knowledge lint` reports unsupported claims, broken links, orphan pages, stale pages, contradictions, and missing source traces.
- Research planning can optionally read prior knowledge and record what prior context influenced the run.
- The dashboard can inspect the knowledge graph, open source-backed pages, and show lint findings.
- The graph index is rebuildable from raw/wiki data, so SQLite is not the only source of truth.
