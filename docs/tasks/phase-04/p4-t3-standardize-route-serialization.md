# P4-T3 - Standardize Route Serialization

## Outcome

Route serialization uses shared helpers instead of repeated ad hoc JSON conversion.

## Scope

- Add model-to-JSON response helpers.
- Replace repeated `json.loads(model_dump_json())` patterns where safe.
- Keep response payloads identical.
- Add tests for helper behavior.

## Implementation Notes

- Keep helpers small and boring.
- Do not introduce a new response framework.
- Verify datetimes, enums, and nested Pydantic models serialize consistently.

## Acceptance Criteria

- Route code has less repeated serialization boilerplate.
- Payload shapes remain unchanged.
- Helper tests cover common model and list response cases.

## Verification

- Run route tests and contract tests.
