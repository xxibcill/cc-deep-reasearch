# P6-T1 - Implement Source Scanning Entry Points

## Status

Proposed.

## Summary

Implement the first scanning path for Radar sources so the system can fetch input data from a narrow set of supported source types.

## Scope

- Support a small initial source set.
- Add the backend entry points that trigger scans.
- Persist fetched results before normalization and ranking.

## Recommended Initial Source Set

- competitor websites or blogs
- changelog or release-note pages
- one discussion-source pattern such as Reddit feed URLs if the existing providers make that practical

## Out Of Scope

- Broad social API coverage
- Fully automatic background scheduling if no scheduler pattern exists yet

## Read These Files First

- `src/cc_deep_research/providers/`
- `src/cc_deep_research/research_runs/service.py`
- `src/cc_deep_research/content_gen/maintenance_workflow.py`
- `src/cc_deep_research/radar/service.py`

## Suggested Files To Create Or Change

- `src/cc_deep_research/radar/scanners.py`
- `src/cc_deep_research/radar/scan_service.py`
- `src/cc_deep_research/radar/router.py`
- `tests/test_radar_scanners.py`

## Implementation Guide

1. Start by defining a scanner interface or protocol that all source-specific scanners follow.
2. Implement only the smallest set of scanners needed for V1.
3. Make the scan output a typed intermediate record that can be normalized in the next task.
4. Add a route or service entry point that scans one source on demand first.
5. If you find an existing scheduler pattern that fits cleanly, expose a service hook for scheduled scans, but do not build a full scheduler if one is not already used by the app.
6. Persist scan timing metadata back onto the source record:
   - last scanned at
   - last scan status
   - last scan error if available

## Guardrails For A Small Agent

- Do not couple scanner code directly to scoring or opportunity creation yet.
- Do not fetch everything from the internet in one task. Keep the source set narrow and deterministic.
- Use the provider abstractions that already exist if they fit. Avoid one-off HTTP code unless necessary.

## Deliverables

- Source scanner interface
- Initial scanner implementations
- Scan service or route entry point
- Scanner tests

## Dependencies

- Phase 05 backend contracts

## Verification

- Run `uv run pytest tests/test_radar_scanners.py -v`
- Confirm a scan updates source metadata and returns typed scan results

## Acceptance Criteria

- At least one supported source type can be scanned end-to-end.
- Scan failures do not crash the app and are stored as source health metadata.
- The output of scanning is ready for normalization in the next task.
