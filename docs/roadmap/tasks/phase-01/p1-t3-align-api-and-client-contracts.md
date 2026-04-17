# P1-T3 - Align API And Client Contracts

## Summary

Expose the upgraded strategy schema consistently through the content-gen API and dashboard type system.

## Scope

- Update request and response typing for strategy endpoints.
- Expand dashboard `StrategyMemory` types to match the backend contract.
- Ensure route payloads and frontend callers can handle nested strategy objects.

## Deliverables

- Updated strategy API request and response contracts
- Updated TypeScript interfaces and client helpers
- Contract tests or frontend type tests for the upgraded shape

## Dependencies

- P1-T1 schema definitions
- P1-T2 compatibility approach

## Acceptance Criteria

- Strategy API responses match the backend schema.
- The dashboard can type-check against the full strategy shape without casting or dropping fields.
