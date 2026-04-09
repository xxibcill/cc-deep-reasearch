# Task 07: Ground Scripting In Argument Map And Proof Links

Goal:
Make scripting consume explicit claims and proof anchors instead of a flattened research text blob.

Primary files:
- `src/cc_deep_research/content_gen/orchestrator.py`
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/prompts/scripting.py`
- `src/cc_deep_research/content_gen/agents/scripting.py`

Scope:
- Replace or greatly reduce `_format_research_context()` usage for script generation.
- Feed `ArgumentMap` into the seeded scripting context.
- Extend beat-intent or script-related models so beats can carry claim ids or proof ids.
- Update scripting prompts so hooks, beats, and final script must stay consistent with supported claims.

Implementation notes:
- Keep the spoken output natural; the goal is grounded writing, not citation noise in the final script.
- It is fine to keep research context as a fallback, but the argument map should be the primary input.
- Try to make unsupported claims impossible by construction where practical.

Acceptance criteria:
- Script planning and drafting prompts can access beat-level claims and proof anchors.
- The final script path uses the argument map as primary grounding input.
- Existing step tracing remains readable and serializable.

Validation:
- Add focused tests around seeded scripting context and prompt-building helpers.

Out of scope:
- Evaluator scoring changes
- Search query redesign

