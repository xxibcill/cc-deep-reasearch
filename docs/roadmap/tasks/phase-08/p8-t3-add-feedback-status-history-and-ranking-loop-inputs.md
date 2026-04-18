# P8-T3 - Add Feedback, Status History, And Ranking Loop Inputs

## Status

Proposed.

## Summary

Persist the user's explicit and implicit reactions to Radar opportunities so the system can distinguish acted-on items from ignored or dismissed ones.

## Scope

- Record status changes over time.
- Record explicit feedback events.
- Make feedback accessible to later ranking logic and analytics queries.

## Out Of Scope

- Full automatic reweighting of the scoring model
- Complex ML or personalization infrastructure

## Read These Files First

- `src/cc_deep_research/radar/models.py`
- `src/cc_deep_research/radar/stores.py`
- `src/cc_deep_research/radar/service.py`
- `src/cc_deep_research/telemetry/query.py`

## Suggested Files To Create Or Change

- `src/cc_deep_research/radar/models.py`
- `src/cc_deep_research/radar/stores.py`
- `src/cc_deep_research/radar/service.py`
- `src/cc_deep_research/radar/scoring.py`
- `tests/test_radar_feedback.py`

## Implementation Guide

1. Add explicit status-history records instead of only mutating the latest status field.
2. Record feedback events such as:
   - saved
   - dismissed
   - acted_on
   - converted_to_research
   - converted_to_content
3. Add service methods that expose this history to the rest of the system.
4. Feed a minimal subset of this history into scoring inputs. Example:
   - repeated dismissals reduce similar future recommendations
   - acted-on opportunities slightly raise similar opportunities
5. Keep the adjustment logic simple and bounded. This task is about capturing the inputs, not building a complex adaptive model.

## Guardrails For A Small Agent

- Do not overwrite history with only the latest state.
- Do not silently modify scores without a visible reason or stored metadata.
- Keep the learning effect modest and inspectable.

## Deliverables

- Status history persistence
- Feedback event persistence
- Minimal ranking-loop input integration
- Feedback tests

## Dependencies

- Phase 05 persistence contracts
- P6-T3 scoring implementation

## Verification

- Run `uv run pytest tests/test_radar_feedback.py -v`
- Confirm history can show multiple sequential actions on the same opportunity

## Acceptance Criteria

- The system can distinguish untouched, saved, acted-on, and dismissed opportunities.
- Feedback is stored in a way that later ranking logic and analytics can consume.
- Any score adjustments caused by feedback are limited and inspectable.
