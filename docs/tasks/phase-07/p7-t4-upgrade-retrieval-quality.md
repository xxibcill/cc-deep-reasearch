# P7-T4 - Upgrade Retrieval Quality

## Functional Feature Outcome

Research runs retrieve stronger, more explainable source sets with clearer provider status, better ranking, richer content hydration, and provenance that survives analysis and reporting.

## Why This Task Exists

The workflow is only as good as its evidence. The current retrieval layer is Tavily-centric, content hydration depends on an optional MCP reader, and provider claims can be ahead of implementation. Query provenance exists and is valuable, but source ranking and downstream evidence handling can be made more explicit. This task improves research quality at the retrieval boundary before trying to improve synthesis.

## Scope

- Clarify supported provider behavior in code, config, docs, and dashboard.
- Add or explicitly defer non-Tavily provider implementation.
- Improve source scoring and ranking with freshness, authority, source type, and provenance signals.
- Add a non-MCP HTTP content hydration fallback.
- Preserve content hydration status in source metadata.
- Improve retrieval telemetry for provider attempts, cache hits, content fetch attempts, and fallback behavior.

## Current Friction

- `build_search_provider()` only constructs Tavily providers.
- Docs note that `claude` can be selected but is not implemented as a search provider.
- Missing `web_reader` causes content enrichment to skip rather than fall back to HTTP extraction.
- Aggregation primarily deduplicates and sorts by score; richer quality signals are not first-class.

## Implementation Notes

- Provider clarity:
  - Keep `tavily`, `tavily_advanced`, and `tavily_basic` as supported provider specs.
  - If a provider is not buildable, return a clear warning and surface it in session metadata.
  - Remove unsupported providers from dashboard choices unless a real adapter exists.
- Optional second provider:
  - Add a new `SearchProvider` implementation only if credentials and stable API behavior are available.
  - Tests must use fake providers and never require live credentials.
- Source quality metadata:
  - `source_type`: government, academic, news, organization, commercial, other.
  - `freshness`: published date if available, plus age bucket.
  - `authority_score`: deterministic domain/source-type heuristic.
  - `provenance_score`: boost sources returned by multiple query families.
  - `hydration_status`: `provider_content`, `fetched`, `failed`, `skipped`, or `unavailable`.
- Ranking:
  - Keep provider score as an input, not the only ranking signal.
  - Document the score components so benchmarks can explain changes.
  - Avoid overfitting to one provider's scoring semantics.
- Content hydration fallback:
  - Try MCP `web_reader` when available.
  - If unavailable, use an internal HTTP reader with timeout, size limit, and basic HTML-to-text cleanup.
  - Respect robots/blocked/network failures by marking the source as failed/skipped, not failing the whole run.

## Test Plan

- Provider factory tests for supported, unsupported, and missing-credential providers.
- Ranking tests with deterministic source fixtures showing freshness/authority/provenance behavior.
- Hydration tests for:
  - provider content already sufficient
  - MCP unavailable with HTTP fallback success
  - HTTP timeout/failure records metadata and continues
  - cache hit avoids repeated fetch
- Telemetry tests for fetch status and provider degradation.
- Benchmark case reports include source type and domain diversity changes.

## Acceptance Criteria

- Source collection metadata clearly distinguishes configured, available, unsupported, and failed providers.
- Source ranking is deterministic and covered by tests.
- Content hydration has a local fallback path when MCP reader is unavailable.
- Each enriched source records hydration status and provenance.
- Retrieval changes improve or preserve benchmark source count, domain diversity, and validation score.

## Verification Commands

```bash
uv run pytest tests/test_providers.py tests/test_tavily_provider.py tests/test_search_cache.py -x
uv run pytest tests/test_orchestrator.py tests/test_benchmark.py tests/test_telemetry.py -x
uv run ruff check src/cc_deep_research/providers.py src/cc_deep_research/providers/ src/cc_deep_research/orchestration/
```

## Risks

- Adding an HTTP fallback can introduce flaky network behavior. Keep fallbacks timeout-bound, optional, and heavily mocked in tests.
- Ranking changes can shift benchmark outputs. Treat benchmark diffs as expected only when the source set becomes demonstrably better.
