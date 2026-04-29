# P8-T1 - Define Knowledge Vault Contracts

## Functional Feature Outcome

The project has a stable local knowledge vault contract with explicit filesystem layout, typed graph models, Markdown page frontmatter, and config paths that future ingest and dashboard work can rely on.

## Why This Task Exists

Karpathy's personal knowledge graph approach works because the durable knowledge base is readable and editable, while any graph or search index is derived. This repo already has durable sessions and reports, but it needs a clear knowledge-layer boundary before ingest code starts writing files. This task defines that boundary conservatively: raw evidence is immutable, wiki pages are synthesized and versioned by convention, and the SQLite graph is a rebuildable index.

## Scope

- Add a `cc_deep_research.knowledge` package with initial contracts and path helpers.
- Define the vault layout:
  - `raw/`
  - `wiki/index.md`
  - `wiki/log.md`
  - `wiki/concepts/`
  - `wiki/entities/`
  - `wiki/claims/`
  - `wiki/questions/`
  - `wiki/sessions/`
  - `wiki/sources/`
  - `graph/graph.sqlite`
  - `graph/exports/graph.json`
  - `schema/AGENTS.md`
- Define page frontmatter fields for ID, kind, title, status, aliases, tags, source IDs, session IDs, created/updated timestamps, and confidence.
- Define graph node kinds: `session`, `source`, `query`, `concept`, `entity`, `claim`, `finding`, `gap`, `question`, `wiki_page`.
- Define graph edge kinds: `cited`, `mentions`, `supports`, `contradicts`, `derived_from`, `used_query`, `suggests_query`, `supersedes`, `evolves`, `links_to`.
- Add config/default path resolution under the cc-deep-research config directory.

## Implementation Notes

- Keep Markdown and raw files as the source of truth.
- Treat SQLite as a materialized index that can be deleted and rebuilt.
- Prefer deterministic IDs derived from canonical URLs, session IDs, normalized claim text, or page paths.
- Avoid introducing vector databases or external graph databases in this task.
- Add `schema/AGENTS.md` with rules for future LLM wiki edits:
  - never mutate files in `raw/`
  - preserve source links for claims
  - mark unsupported claims explicitly
  - append material changes to `wiki/log.md`
  - update `wiki/index.md` after page creation or major rename

## Test Plan

- Unit tests for path resolution with default and explicit config paths.
- Model validation tests for nodes, edges, page frontmatter, and graph snapshots.
- ID stability tests for URLs, claim text, session IDs, and page paths.
- Vault initialization tests that assert all required directories and seed files exist.

## Acceptance Criteria

- Knowledge vault contracts are documented and typed.
- The vault can be initialized without live credentials.
- Required directories and seed files are created idempotently.
- Graph and page models reject invalid kinds and preserve extra metadata intentionally.
- Existing research, session, and dashboard tests are unaffected.

## Verification Commands

```bash
uv run pytest tests/test_models.py tests/test_session_store.py -x
uv run ruff check src/cc_deep_research/knowledge tests/
```

## Risks

- Over-designing the schema can slow implementation. Keep the first schema small and allow extra metadata.
- If IDs are not stable, future ingest will create duplicate pages. Cover ID normalization early.
