# Task 05: Implement Argument Map Agent

Status: Done

Goal:
Add the agent that turns a selected idea, selected angle, and structured research pack into an `ArgumentMap`.

Primary files:
- `src/cc_deep_research/content_gen/agents/argument_map.py`
- `src/cc_deep_research/content_gen/agents/__init__.py`

Scope:
- Create a new agent module with an LLM call and parser.
- Parse the new prompt contract into the typed `ArgumentMap` model.
- Fail fast when the thesis, mechanism, or proof anchors are missing.

Implementation notes:
- Keep the parser explicit and deterministic.
- Reuse the same general agent style as the other content-gen agents.
- Do not wire the new agent into the pipeline in this task.

Acceptance criteria:
- The agent can be instantiated and returns a valid `ArgumentMap`.
- Malformed output fails with a useful error instead of silently degrading into an empty map.
- The parser behavior matches the prompt contract.

Validation:
- Add parser and agent unit tests using fake LLM responses.

Out of scope:
- Pipeline stage list changes
- Scripting prompt changes
