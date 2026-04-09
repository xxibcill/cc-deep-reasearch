# Task 04: Define Argument Map Contract

Goal:
Create the data contract and prompt for the missing bridge between research and script writing.

Primary files:
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/prompts/__init__.py`
- `src/cc_deep_research/content_gen/prompts/argument_map.py`

Scope:
- Add a new `ArgumentMap` model and supporting submodels.
- Include fields such as `thesis`, `audience_belief_to_challenge`, `core_mechanism`, `proof_anchors`, `counterarguments`, `safe_claims`, `unsafe_claims`, and `beat_claim_plan`.
- Add a new prompt module with a versioned contract docstring.
- Register the new contract in `CONTENT_GEN_STAGE_CONTRACTS`.

Implementation notes:
- Design the shape for downstream script grounding, not just human readability.
- Each beat plan should be able to reference proof or claim identifiers.
- Keep naming consistent with the rest of the content-gen models.

Acceptance criteria:
- The repo has a clear prompt contract for `ArgumentMap`.
- The contract is specific enough for a parser to validate later.
- Model defaults do not break pipeline context construction.

Validation:
- Add at least one lightweight contract or model test if needed.

Out of scope:
- Agent implementation
- Orchestrator wiring

