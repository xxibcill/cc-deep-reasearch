# P7-T5 - Tighten Evidence And Report Quality

## Functional Feature Outcome

Final reports become more trustworthy: key claims carry evidence, weak evidence is flagged, and refinement never inserts placeholder TODOs or unsupported sections.

## Why This Task Exists

The research workflow already validates source count, domain diversity, citation completeness, and analysis gaps. Report generation also includes quality evaluation, post-validation, and refinement. The weak point is that report refinement can add placeholder comments, and claim-level evidence is not strict enough as a product contract. A research tool should prefer explicit uncertainty and missing evidence over polished unsupported prose.

## Scope

- Make claim-level evidence links part of the canonical analysis/report contract.
- Add validation that each key finding has at least one supporting source or an explicit unsupported/uncertain marker.
- Replace placeholder report refinement behavior with deterministic fixes or no-op-with-warning behavior.
- Persist report quality and post-validation results into session/report metadata.
- Add tests that fail when reports contain TODO placeholders or invalid citations.

## Current Friction

- `ReportRefinerAgent` contains fallback methods that can append TODO comments.
- `PostReportValidator` checks required sections and citation ranges but does not enforce support for every key claim.
- Report quality results are logged but not consistently surfaced as durable metadata for dashboard and benchmark comparisons.

## Implementation Notes

- Analysis contract:
  - Prefer structured claim objects where possible:

```python
{
    "claim": "...",
    "supporting_source_ids": ["source-1", "source-3"],
    "confidence": 0.72,
    "evidence_quality": "moderate",
    "limitations": ["..."],
}
```

  - If existing `AnalysisResult` fields cannot be changed broadly in one task, add a compatible `claim_evidence` field or metadata sub-structure.
- Report validation:
  - Detect key findings without citations or source references.
  - Detect citations that point beyond available sources.
  - Detect TODO, placeholder, and empty generated sections.
  - Detect safety section false positives caused by regex fragments.
- Report refinement:
  - Never add HTML comments with TODOs.
  - If a missing section cannot be filled from session/analysis data, add a concise honest limitation section.
  - If citations cannot be added confidently, add an evidence limitation note rather than fabricating references.
- Metadata:
  - Store report quality score, critical issues, warnings, post-validation issues, refinement applied, and refinement reason.
  - Expose this metadata to benchmark reports.

## Test Plan

- Unit tests for report refiner ensuring no TODO comments are emitted.
- Unit tests for unsupported claims and citation range failures.
- Unit tests for report metadata persistence after quality evaluation.
- Integration tests through `ReportGenerator.generate_markdown_report()`.
- Benchmark tests include report quality metrics.

## Acceptance Criteria

- Generated/refined reports do not contain TODO comments or placeholder sections.
- Key findings are either evidence-linked or explicitly marked as uncertain/unsupported.
- Report quality and post-validation outcomes are durable metadata, not logs only.
- Benchmark reports can compare report quality across workflow changes.
- Existing Markdown, JSON, and HTML report formats still work.

## Verification Commands

```bash
uv run pytest tests/test_reporter.py tests/test_report_quality_evaluator.py tests/test_validator.py -x
uv run pytest tests/test_benchmark.py tests/test_session_store.py -x
uv run mypy src/cc_deep_research/post_validator.py
```

## Risks

- Tight claim validation can reduce report acceptance until analyzers produce better structured evidence. Roll out with warnings first, then fail gates once evidence structure is reliable.
- Over-aggressive citation validation can flag valid prose. Keep checks specific and add fixture coverage for accepted report shapes.
