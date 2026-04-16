# Brief Management Guide

This document describes how to use the persistent brief management system for content generation workflows.

## Overview

The brief management system provides durable, version-aware persistence for opportunity briefs. Rather than being embedded inline in pipeline contexts, briefs are now stored as independent resources with:

- **Lifecycle states**: DRAFT → APPROVED → ARCHIVED/SUPERSEDED
- **Immutable revisions**: Each edit creates a new revision snapshot, preserving full history
- **Lineage tracking**: Branches and clones preserve their ancestry
- **Approval gates**: Approved briefs can gate downstream pipeline stages

## Lifecycle States

| State | Meaning |
|-------|---------|
| `DRAFT` | Brief is being developed; not yet approved |
| `APPROVED` | Brief has been reviewed and is locked for pipeline use |
| `SUPERSEDED` | Brief has been replaced by a newer version |
| `ARCHIVED` | Brief is retired but preserved for historical reference |

Only `APPROVED` briefs can be used to gate pipeline execution (when the brief gate is enabled).

## CLI Commands

### List all briefs

```bash
cc-deep-research content-gen briefs briefs_list
```

### View a specific brief

```bash
cc-deep-research content-gen briefs briefs_show --brief-id mbrief_abc123
```

### Migrate YAML briefs to SQLite

If you have existing briefs in YAML format, migrate them to the SQLite store:

```bash
cc-deep-research content-gen briefs briefs_migrate
```

This performs a one-time import from the YAML store to SQLite. Existing SQLite records are preserved; only new briefs are added.

### Check store health

Verify consistency between YAML and SQLite stores:

```bash
cc-deep-research content-gen briefs briefs_health
```

This reports any briefs that exist only in one store or the other.

## Operator Workflows

### Creating a Brief

Briefs are typically created during pipeline stage 1 (plan_opportunity). The pipeline automatically creates a managed brief when you run:

```bash
cc-deep-research content-gen pipeline --theme "pricing psychology"
```

This creates a managed brief in `DRAFT` state with the initial opportunity brief content.

### Editing a Brief

1. Open the brief in the dashboard at `/content-gen/briefs/[id]`
2. Use the AI Brief Assistant to refine content, or edit fields directly
3. Each save creates a new revision (immutable snapshot)
4. Use "Apply" to promote a revision to the current head

### Approving a Brief

Once a brief is ready for production use:

1. Navigate to the brief in the dashboard
2. Review the current revision content
3. Click **Approve** to transition to `APPROVED` state

Approval is required for the brief to gate pipeline execution.

### Reusing a Brief for a New Run

To start a new pipeline run from an existing brief:

```bash
cc-deep-research content-gen pipeline --brief-id mbrief_abc123 --from-stage 2
```

This resumes from stage 2 (ideation) using the approved brief as the planning anchor.

### Branching a Brief

Create a derivative brief for a different theme or channel:

```bash
# Via dashboard: click "Branch" on any brief
# Or via API: POST /briefs/{id}/branch
```

Branches start in `DRAFT` state and track their lineage via `source_brief_id`.

### Cloning a Brief

Create an independent copy for experimentation:

```bash
# Via dashboard: click "Clone" on any brief
# Or via API: POST /briefs/{id}/clone
```

Clones start in `DRAFT` state but do not track lineage.

## Rollout and Backward Compatibility

### Legacy Data

- Old pipeline context files with inline briefs continue to work
- The system falls back to `inline_fallback` reference type when no managed brief exists
- Resume validation warns when brief state has changed but allows override with `--allow-stale-brief`

### Storage Transition

- YAML storage remains fully readable
- SQLite is the default for new brief operations
- Run `briefs_migrate` to copy YAML data into SQLite

### Feature Flags

| Feature | Default | Description |
|---------|---------|-------------|
| `use_sqlite` | `false` | Use SQLite store instead of YAML |
| Brief gate | enabled | Block pipeline stages without approved brief |

## Invariants (Do Not Break)

These constraints should be preserved by future feature work:

1. **Revisions are immutable**: Once created, a revision's content never changes
2. **Head pointer**: `current_revision_id` always points to the active revision for pipeline use
3. **Approval is explicit**: Only operator action transitions to `APPROVED`; the system never auto-approves
4. ** lineage is traceable**: Cloned and branched briefs preserve `source_brief_id`
5. **Concurrency safety**: Optimistic locking via `updated_at` prevents silent overwrites

## Data Storage

| Data | Location |
|------|----------|
| Briefs (SQLite) | `~/.config/cc-deep-research/content-gen/briefs.db` |
| Revisions (SQLite) | `~/.config/cc-deep-research/content-gen/briefs_revisions.db` |
| Briefs (YAML, legacy) | `~/.config/cc-deep-research/content-gen/briefs.yaml` |
| Audit log | `~/.config/cc-deep-research/content-gen/audit_log.yaml` |

## Key Files

| File | Purpose |
|------|---------|
| `src/cc_deep_research/content_gen/brief_service.py` | Brief lifecycle operations |
| `src/cc_deep_research/content_gen/storage/sqlite_brief_store.py` | SQLite persistence |
| `src/cc_deep_research/content_gen/storage/revision_store.py` | Revision storage |
| `src/cc_deep_research/content_gen/brief_migration.py` | Legacy migration utilities |
| `src/cc_deep_research/content_gen/models.py` | `ManagedOpportunityBrief`, `BriefRevision`, `PipelineBriefReference` models |
