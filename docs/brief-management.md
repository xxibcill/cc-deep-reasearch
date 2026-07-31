# Brief Management

Opportunity briefs are durable, versioned content-planning resources. Operators
manage them in the Content workspace or through `/api/content-gen/briefs`.

## Lifecycle

| State | Meaning |
| --- | --- |
| `DRAFT` | Editable and not yet approved for downstream use |
| `APPROVED` | Reviewed and eligible to gate downstream work |
| `SUPERSEDED` | Replaced by a newer brief |
| `ARCHIVED` | Retired but retained for audit/history |

Edits are stored as immutable revisions. Applying a revision changes the
current head without deleting older snapshots. Branches retain lineage through
their source brief; clones are independent copies.

## Operator workflow

1. Open the brief workspace in the dashboard.
2. Create a brief directly or let opportunity planning create one.
3. Edit fields or use the brief assistant to propose a revision.
4. inspect and apply the new revision.
5. Approve the brief when it is ready.
6. Generate backlog candidates from the approved planning record.
7. Select a backlog item and start its pipeline.

Approval, branching, cloning, archive, supersede, and revert operations are
explicit lifecycle transitions. They should not be implemented as direct
storage edits.

## API map

| Purpose | Endpoint |
| --- | --- |
| List/create briefs | `GET` or `POST /api/content-gen/briefs` |
| Read/update a brief | `GET` or `PATCH /api/content-gen/briefs/{brief_id}` |
| Revision history | `GET /api/content-gen/briefs/{brief_id}/revisions` |
| Save/apply a revision | `POST .../revisions`, `POST .../apply-revision` |
| Approve/archive/supersede | `POST .../approve`, `.../archive`, `.../supersede` |
| Revert to draft | `POST .../revert-to-draft` |
| Clone or branch | `POST .../clone`, `POST .../branch` |
| Audit history | `GET .../audit` |
| Assistant proposal/application | `POST .../assistant/respond`, `.../assistant/apply` |
| Generate/apply backlog | `POST .../generate-backlog`, `.../apply-backlog` |
| Compare related briefs | `GET .../siblings`, `GET .../compare/{other_brief_id}` |

Use the OpenAPI page at `http://127.0.0.1:8000/docs` for request schemas,
optimistic-concurrency fields, and response models.

## Persistence and compatibility

- New deployments use SQLite-backed brief and revision stores by default.
- YAML-backed stores remain compatibility inputs where configured.
- Legacy pipeline contexts containing inline briefs can still be interpreted
  through the migration/domain layer.
- Migrations are code-level maintenance operations covered by
  `tests/test_content_gen_storage_migration.py`; there is no supported
  operator CLI for running them.

Before changing a store backend, back up the paths reported by
`GET /api/operations/data-paths` and validate the migration in a copy.

## Code map

- API mapping: [`src/cc_deep_research/content_gen/router.py`](../src/cc_deep_research/content_gen/router.py)
- domain/API service: [`src/cc_deep_research/content_gen/brief_api_service.py`](../src/cc_deep_research/content_gen/brief_api_service.py)
- lifecycle service: [`src/cc_deep_research/content_gen/brief_service.py`](../src/cc_deep_research/content_gen/brief_service.py)
- compatibility migration: [`src/cc_deep_research/content_gen/brief_migration.py`](../src/cc_deep_research/content_gen/brief_migration.py)
- persistence: [`src/cc_deep_research/content_gen/storage/`](../src/cc_deep_research/content_gen/storage)
