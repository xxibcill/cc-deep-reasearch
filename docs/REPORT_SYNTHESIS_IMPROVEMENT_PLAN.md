# Report Synthesis Improvement Plan

This plan translates the human feedback on the generated research report into concrete system changes for the current pipeline.

It is based on the observed failures in [`whitetea.md`](/Users/jjae/Documents/guthib/cc-deep-research/whitetea.md) and the current implementation in the analyzer, AI analysis, reporter, and post-validation layers.

## Objective

Improve final report quality so that generated research reports:

- synthesize source meaning instead of echoing raw scrape artifacts
- separate high-level findings from detailed analysis
- output complete, self-contained sentences in safety and contradiction sections
- emit clean, canonical source URLs without tracking parameters

## Current Failure Modes

### 1. Raw scrape artifacts leak into synthesis

Observed symptoms:

- navigation text appears as findings
- markdown headers are copied into prose
- calls to action and menu fragments survive into final bullets

Current code signals:

- [`src/cc_deep_research/agents/analyzer.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/analyzer.py) already cleans source text, but the filtering is regex-heavy and shallow.
- [`src/cc_deep_research/agents/llm_analysis_client.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/llm_analysis_client.py) asks for synthesized findings, but does not explicitly forbid menus, headers, or formatting artifacts.
- [`src/cc_deep_research/agents/ai_executor.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/ai_executor.py) can fold theme key points directly into finding descriptions, which preserves noisy text if the upstream themes are noisy.

### 2. Key Findings and Detailed Analysis are structurally redundant

Observed symptoms:

- the report repeats nearly the same content under both sections
- the summary layer is not visually or semantically distinct from the analysis layer

Current code signals:

- [`src/cc_deep_research/agents/reporter.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/reporter.py) renders `analysis_result.key_findings` into `## Key Findings` and separately renders `analysis.themes_detailed` into `## Detailed Analysis`, but both are derived from the same synthesized material without a schema distinction between summary and detail.

### 3. Fragmented snippets appear in safety and contradiction output

Observed symptoms:

- bullets like "with your doctor"
- bullets like "breastfeeding should avoid"
- contradiction snippets that start or end mid-sentence

Current code signals:

- [`src/cc_deep_research/agents/ai_agent_integration.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/ai_agent_integration.py) extracts safety information with regex captures that stop at the first period and then aggressively truncate long content.
- [`src/cc_deep_research/agents/analyzer.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/analyzer.py) tries to repair truncation after cleaning, but the repair logic is heuristic and not sentence-aware.
- [`src/cc_deep_research/post_validator.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/post_validator.py) only warns on some truncation patterns; it does not enforce complete-sentence output.

### 4. Tracked URLs leak into the final references

Observed symptoms:

- source links contain `?srsltid=...`
- the final references look noisy and non-academic

Current code signals:

- [`src/cc_deep_research/aggregation.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/aggregation.py) normalizes URLs for deduplication but does not sanitize the stored source URL used in output.
- [`src/cc_deep_research/agents/reporter.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/reporter.py) prints raw `source.url` values directly in the Markdown and JSON reports.

## Target State

The report pipeline should produce three distinct output layers:

1. Clean source text
   Raw page extraction is normalized into article-like text before semantic analysis.

2. Structured synthesis
   Each theme/finding contains both:
   - a short summary for high-level findings
   - a detailed explanation with evidence points for deep analysis

3. Presentation-safe output
   Final report rendering emits complete sentences, canonical URLs, and post-validation errors when artifacts leak through.

## Proposed Changes

## Workstream 1: Add a stronger normalization layer before synthesis

### Goal

Remove menus, headers, CTA text, markdown noise, and repeated UI fragments before the LLM or heuristic synthesizer sees the content.

### Changes

1. Introduce a dedicated text normalization helper instead of expanding ad hoc regex in `AnalyzerAgent`.
2. Normalize content by line or paragraph, not only by whole-string substitution.
3. Drop low-value blocks that look like navigation or boilerplate.
4. Preserve sentence boundaries so downstream extraction can recover full context.

### Heuristics to add

- reject lines with mostly title case or all caps navigation tokens
- reject lines dominated by commerce or UI terms such as `home`, `cart`, `submit manuscript`, `newsletter`, `follow us`
- reject markdown-only headings unless they are content-like and sentence-bearing
- collapse repeated whitespace, repeated punctuation, and duplicated blocks
- keep paragraphs that contain verbs, topic keywords, and at least one complete sentence

### Primary code touchpoints

- `src/cc_deep_research/agents/analyzer.py`
- optional new helper such as `src/cc_deep_research/text_normalization.py`

## Workstream 2: Strengthen synthesis prompts and output schema

### Goal

Force the model to rewrite extracted material into clean analyst prose rather than recycling source fragments.

### Changes

1. Update synthesis prompts to explicitly prohibit:
   - navigation text
   - menus
   - headers and footers
   - calls to action
   - markdown artifacts
   - incomplete snippets
2. Require every generated sentence to be understandable out of context.
3. Separate summary fields from detailed fields in the analysis schema.

### Suggested schema change

Extend `AnalysisFinding` so it can hold both layers explicitly:

- `summary`: 1-2 sentence high-level takeaway
- `detail_points`: detailed bullets or short evidence-backed statements
- `evidence`: supporting source URLs
- `confidence`: existing field

Theme objects in `themes_detailed` should mirror this distinction:

- `description`: analytical paragraph
- `key_points`: evidence-backed details only
- optional `summary`: short thematic takeaway used by `## Key Findings`

### Prompt requirements

Prompts in both CLI-backed and heuristic-backed paths should state:

- "Rewrite the source material into clean professional prose."
- "Ignore menus, site navigation, buttons, share widgets, newsletter prompts, and article metadata."
- "Do not copy raw page headers or markdown syntax."
- "Provide complete sentences that remain understandable out of context."
- "If the source text is fragmentary, infer cautiously or omit it."

### Primary code touchpoints

- `src/cc_deep_research/agents/llm_analysis_client.py`
- `src/cc_deep_research/agents/ai_executor.py`
- `src/cc_deep_research/models.py`
- `src/cc_deep_research/agents/analyzer.py`

## Workstream 3: Refactor report rendering to remove redundancy

### Goal

Make `## Key Findings` a real executive layer and reserve bullets, nuance, and citations for `## Detailed Analysis`.

### Changes

1. Render `## Key Findings` from `finding.summary` only.
2. Limit each finding in that section to:
   - a title
   - 1-2 sentences
   - optional confidence line
3. Move supporting source lists, evidence bullets, and elaboration into `## Detailed Analysis`.
4. Make `## Detailed Analysis` the only place that shows:
   - bullet-level evidence
   - supporting source lists
   - contradiction notes per theme
   - citations tied to specific detail points

### Rendering rules

- if a finding lacks a usable summary, derive one from the detailed theme description
- never print the same text block in both sections
- keep `## Key Findings` scannable enough to read without entering the detailed section

### Primary code touchpoints

- `src/cc_deep_research/agents/reporter.py`

## Workstream 4: Replace fragment extraction with sentence-window extraction

### Goal

Stop emitting clipped phrases in safety and contradiction sections.

### Changes

1. Replace regex capture groups that return arbitrary substring fragments with sentence-aware extraction.
2. When a keyword match is found, capture the full sentence containing it and optionally one adjacent sentence for context.
3. Add a final sentence-quality filter before rendering.

### Sentence-quality rules

Drop candidate text when it:

- starts lowercase without preceding context
- ends mid-word or with dangling ellipses
- is shorter than a minimum complete-thought threshold
- lacks a verb
- starts with conjunction-only fragments such as `with`, `and`, `or`, `but`

### Safety-specific changes

- store the extracted full sentence, not just the regex match body
- stop truncating to `...` in `_clean_safety_text`
- prefer one clean sentence over multiple clipped fragments

### Contradiction-specific changes

- ensure claim disagreement records store complete rationale sentences
- avoid copying raw truncated evidence into the final report

### Primary code touchpoints

- `src/cc_deep_research/agents/ai_agent_integration.py`
- `src/cc_deep_research/agents/analyzer.py`
- `src/cc_deep_research/post_validator.py`

## Workstream 5: Add canonical URL sanitization

### Goal

Emit clean reference URLs while preserving raw source URLs for debugging if needed.

### Changes

1. Add a canonical URL sanitizer based on `urllib.parse`.
2. Strip known tracking parameters such as:
   - `srsltid`
   - `utm_*`
   - `fbclid`
   - `gclid`
   - `igshid`
   - `mc_cid`
   - `mc_eid`
3. Store both:
   - `url`: canonical output URL
   - `source_metadata.raw_url`: original retrieved URL
4. Apply sanitization before:
   - deduplication
   - report rendering
   - JSON export

### Primary code touchpoints

- `src/cc_deep_research/aggregation.py`
- `src/cc_deep_research/models.py`
- `src/cc_deep_research/agents/reporter.py`

## Implementation Phases

## Phase 1: Contract and prompt updates

Priority: P0

Tasks:

- extend the finding/theme schema to distinguish summary from detail
- update synthesis prompts in both LLM and heuristic paths
- add explicit artifact-exclusion instructions

Acceptance criteria:

- prompts explicitly instruct the model to ignore UI/navigation artifacts
- analysis objects can represent both summary and detail without overloading `description`

## Phase 2: Text normalization and sentence extraction

Priority: P0

Tasks:

- add a reusable normalization helper
- replace fragment extraction with sentence-window extraction
- stop safety text truncation that introduces `...`

Acceptance criteria:

- menu strings and CTA fragments are removed before synthesis
- safety and contradiction bullets are complete sentences

## Phase 3: Reporter refactor

Priority: P0

Tasks:

- rewrite `## Key Findings` to render summary-only content
- keep evidence bullets and citations inside `## Detailed Analysis`
- sanitize URLs at render time as a final guard

Acceptance criteria:

- `## Key Findings` is shorter and non-redundant
- `## Detailed Analysis` contains the supporting bullets and links

## Phase 4: Validation and regression coverage

Priority: P1

Tasks:

- upgrade post-report validation to fail on obvious snippet fragments
- add fixture-based regression tests using the white tea failure patterns
- add URL sanitization tests

Acceptance criteria:

- reports with tracked URLs or dangling fragments fail validation or tests
- the white tea fixture no longer reproduces the original issues

## Test Plan

Add or expand tests for the following cases:

1. Source normalization removes menu strings such as `Home`, `Submit Manuscript`, and newsletter text.
2. Synthesis output never contains markdown headers like `# White Tea: ...` inside findings.
3. `## Key Findings` does not repeat bullet lists that appear in `## Detailed Analysis`.
4. Safety extraction returns complete sentences such as `People who are pregnant should avoid...`, not clipped phrases.
5. Contradiction summaries do not contain dangling ellipses or mid-word truncations.
6. Final Markdown and JSON outputs strip `srsltid` and common `utm_*` parameters.

Suggested test files:

- `tests/test_reporter.py`
- new `tests/test_analyzer.py`
- new `tests/test_post_validator.py`
- new `tests/test_aggregation.py`

## Success Metrics

The work should be considered successful when:

- no known raw scrape artifact from `whitetea.md` survives in the regenerated report
- `## Key Findings` is materially shorter than `## Detailed Analysis`
- safety and contradiction sections contain only complete, standalone sentences
- source URLs in final output are canonical and free of known tracking parameters
- regression tests cover the failure modes from the human review

## Recommended Order of Execution

1. Land schema and prompt changes first so the intended output contract is clear.
2. Land normalization and sentence-window extraction second so the model sees better inputs.
3. Refactor reporter rendering third so summary and detail use different fields.
4. Add canonical URL sanitization and tighten post-validation before calling the work complete.

## Notes

- The current report stack already has the right extension points; this does not require a workflow rewrite.
- The biggest quality gain will come from fixing the input normalization plus summary/detail schema split together.
- URL cleanup should be implemented as a shared helper, not as ad hoc string replacement in the reporter.
