# Research Workflow Improvement Plan

This document turns the current workflow design into a concrete improvement roadmap. It focuses on correctness, research quality, architectural clarity, operability, and extensibility.

It is written against the current implementation described in [RESEARCH_WORKFLOW.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/RESEARCH_WORKFLOW.md).

## Executive Summary

The current workflow has a solid shape:

- clear stage boundaries
- iterative follow-up search
- source aggregation and enrichment
- AI-assisted synthesis
- validation before reporting
- telemetry and persistence

The main weaknesses are structural rather than conceptual:

- the public architecture implies a richer multi-agent runtime than actually exists
- planning and query expansion are still heuristic and shallow
- provider support is narrow
- validation is useful but still coarse
- parallel mode is practical but not a true coordination layer
- workflow guarantees are under-tested

The recommended plan is to improve the system in six phases:

1. stabilize workflow contracts and observability
2. improve retrieval quality
3. improve analysis and validation quality
4. resolve the architecture mismatch around agent teams
5. harden reporting and output quality
6. improve evaluation, benchmarking, and developer ergonomics

## Goals

The workflow should evolve toward these outcomes:

- higher quality source sets on the first pass
- more precise and less repetitive follow-up search
- more trustworthy synthesis with stronger evidence attribution
- explicit and testable workflow contracts
- truthful architecture boundaries between local pipeline logic and future agent runtime plans
- measurable quality and latency improvements across depth modes

## Non-Goals

This plan does not assume:

- immediate replacement of the current orchestrator
- full distributed multi-agent execution in one step
- provider expansion at the cost of losing reliability
- a rewrite of reporting before retrieval and validation improve

## Current State Assessment

## Strengths

- The orchestrator already enforces a sensible stage order.
- Iterative search is present and connected to validation output.
- Result aggregation and deduplication are centralized.
- Content enrichment exists and is cached.
- Deep analysis is treated as a distinct mode rather than just a larger source count.
- Monitor and telemetry infrastructure are already integrated into the runtime.

## Main Gaps

### 1. Architecture naming does not match execution reality

`ResearchTeam`, `AgentPool`, and `MessageBus` suggest a real team runtime, but the work is currently executed by local Python objects coordinated directly by the orchestrator.

Impact:

- contributors can make incorrect assumptions
- future changes risk layering more abstraction on top of placeholders
- tests may validate the wrong mental model

### 2. Planning and query expansion are too shallow

The lead agent and expander use lightweight heuristics. That keeps the system cheap and deterministic, but it limits retrieval quality for:

- ambiguous topics
- comparison prompts
- time-sensitive queries
- domain-heavy topics needing primary sources

### 3. Provider diversity is low

Tavily is the only implemented provider. This narrows coverage and makes retrieval quality depend heavily on one backend.

### 4. Validation signals are broad, not evidence-aware enough

The validator checks source count, diversity, content depth, and citation completeness. That is useful, but it does not yet score:

- source type quality
- primary vs secondary evidence
- freshness fit for time-sensitive topics
- claim support density
- contradiction severity

### 5. Parallel mode is underspecified

Parallel retrieval works, but:

- task decomposition is simple
- the coordination layer is mostly unused
- no explicit scheduling policy exists
- no clear retry or backpressure behavior is documented

### 6. Workflow behavior is under-evaluated

There are unit tests around pieces of the workflow, but there is no strong evaluation harness for:

- end-to-end run quality
- iteration effectiveness
- latency by depth mode
- provider performance
- regression detection for report quality

## Guiding Principles

All improvements should follow these principles:

### Tell the truth in the architecture

The code and docs should clearly distinguish:

- current local pipeline behavior
- future agent runtime ambitions

### Improve retrieval before adding more synthesis complexity

Weak retrieval cannot be rescued by better prose.

### Make quality loops more intelligent, not just longer

The goal is better follow-up search, not just more iterations.

### Keep graceful degradation

Missing providers, sparse content, and unavailable LLM APIs should still produce usable results.

### Measure changes

Each phase should have success metrics, not just implementation tasks.

## Roadmap

## Phase 1: Stabilize Workflow Contracts

Priority: P0

Objective:

- make workflow behavior explicit, testable, and easier to change safely

Why first:

- later improvements will be harder and riskier unless the orchestrator contract is pinned down

Deliverables:

- define a clear contract for `session.metadata`
- document phase inputs and outputs in code comments or typed structures
- add workflow-focused tests for:
  - quick, standard, deep mode differences
  - iteration stop conditions
  - follow-up query deduplication
  - parallel fallback to sequential mode
  - missing provider behavior
- add a small fixture-based end-to-end test path with mocked providers and mocked content fetching
- tighten the meaning of flags like `--no-team`

Recommended implementation work:

1. Introduce typed result objects or `TypedDict` models for:
   - strategy output
   - analysis output
   - validation output
   - iteration history records
2. Reduce dictionary shape ambiguity in the orchestrator.
3. Add tests around `execute_research()` that validate metadata structure.
4. Decide whether `--no-team` should:
   - mean "disable parallel coordination only", or
   - switch to a simpler pipeline mode
5. Rename or document misleading abstractions if behavior will stay local for now.

Acceptance criteria:

- workflow metadata has a stable documented shape
- phase transitions are covered by tests
- CLI flags have behavior that matches documentation

Success metrics:

- lower regression rate in orchestrator changes
- new contributors can understand runtime ownership without reading all source files

## Phase 2: Improve Retrieval Quality

Priority: P0

Objective:

- improve the source set before analysis starts

Deliverables:

- stronger planning and query expansion
- better follow-up query generation
- source targeting by query intent and freshness
- support for at least one additional provider or one richer retrieval mode

Recommended implementation work:

1. Upgrade `ResearchLeadAgent.analyze_query()` to classify:
   - informational vs comparative vs time-sensitive vs evidence-seeking queries
   - likely source classes needed, such as news, academic, official docs, market analysis
2. Upgrade `QueryExpanderAgent` to generate query families instead of ad hoc strings:
   - baseline query
   - primary source query
   - expert analysis query
   - current updates query
   - opposing-view or risk query
3. Add scoring tags to expanded queries so the collector can understand intent.
4. Add freshness-aware expansion for time-sensitive queries.
5. Implement source-type targeting where possible.
6. Add at least one additional provider behind the normalized provider interface, or support multiple Tavily search strategies if a new provider is not ready.
7. Persist which query variation produced each source.

Acceptance criteria:

- fewer repetitive query variants
- better domain diversity on first pass
- improved follow-up precision
- retrieval metadata records source provenance by query variant

Success metrics:

- increase in unique high-quality domains per run
- reduction in average number of iterations needed for acceptable quality
- better source diversity for comparison and time-sensitive prompts

## Phase 3: Improve Analysis and Validation Quality

Priority: P0

Objective:

- make synthesis more evidence-aware and make validation better at deciding when research is actually sufficient

Deliverables:

- richer claim extraction and attribution
- evidence strength scoring
- stronger contradiction handling
- better validation recommendations

Recommended implementation work:

1. Add a claim-centered intermediate representation:
   - claim text
   - supporting sources
   - contradicting sources
   - confidence
   - freshness
   - evidence type
2. Refactor analyzer output to preserve claim provenance more explicitly.
3. Extend validation with scores for:
   - freshness fitness
   - primary-source coverage
   - claim support density
   - contradiction pressure
   - source-type diversity
4. Make follow-up queries respond to validation failure modes more precisely.
5. Distinguish "needs more sources" from "needs better sources".
6. Introduce a report-level warning model for unresolved contradictions or weak evidence.

Acceptance criteria:

- analysis can explain why each key finding exists
- validator recommendations are specific to failure modes
- reports can surface weak-evidence findings explicitly

Success metrics:

- fewer unsupported findings in sampled reports
- higher agreement between validation score and human assessment

## Phase 4: Resolve the Agent Architecture Mismatch

Priority: P1

Objective:

- make the architecture honest and extensible

There are two viable directions. Pick one explicitly.

### Option A: Formalize the local pipeline

Use this if the near-term goal is a strong single-process workflow.

Actions:

- rename placeholder "team" abstractions that are not doing real orchestration
- keep the orchestrator as the center of truth
- model phases as composable pipeline steps rather than pretending they are remote agents

Benefits:

- simpler codebase
- less conceptual drift
- easier testing

### Option B: Build a real coordination layer

Use this only if true agent-runtime behavior is a near-term product goal.

Actions:

- make `AgentPool` responsible for actual task scheduling and lifecycle
- route task messages through `MessageBus`
- define task envelopes and result envelopes
- implement retries, timeouts, cancellation, and backpressure
- separate orchestration logic from task execution workers

Benefits:

- real parallelism architecture
- cleaner path to remote or external workers

Recommendation:

- default to Option A unless there is a concrete commitment to true multi-agent execution

Acceptance criteria:

- architecture docs and code match
- no major abstraction layer remains misleading
- contributor onboarding becomes simpler

Success metrics:

- reduced code duplication in parallel and sequential paths
- lower maintenance cost for orchestrator changes

## Phase 5: Strengthen Reporting

Priority: P1

Objective:

- make final outputs more trustworthy and easier to consume

Deliverables:

- stronger evidence traceability in reports
- explicit uncertainty handling
- more useful metadata for downstream tooling

Recommended implementation work:

1. Add report sections or inline markers for:
   - evidence strength
   - contradiction notes
   - freshness notes
   - primary source coverage
2. Ensure every key finding retains source provenance cleanly.
3. Include iteration summary in reports when follow-up search materially changed results.
4. Add structured JSON fields for:
   - claims
   - evidence strength
   - unresolved gaps
   - validation rationale
5. Add tests that validate report structure and critical fields.

Acceptance criteria:

- readers can tell which findings are strong, weak, or contested
- JSON output is more useful for downstream automation

Success metrics:

- lower manual effort to inspect report trustworthiness
- improved utility of JSON output for tooling

## Phase 6: Build an Evaluation Harness

Priority: P1

Objective:

- make workflow improvements measurable

Deliverables:

- benchmark query set
- repeatable run harness
- quality scorecard
- regression reporting

Recommended implementation work:

1. Create a benchmark corpus covering:
   - simple factual queries
   - comparison queries
   - time-sensitive queries
   - evidence-heavy health or science queries
   - market or policy queries
2. Add a script to run the workflow across the corpus with fixed config.
3. Persist benchmark outputs for comparison across commits.
4. Score runs on:
   - source count
   - unique domains
   - source-type diversity
   - iteration count
   - latency
   - claim support density
   - validation score
5. Add a manual review rubric for a smaller gold set.

Acceptance criteria:

- workflow changes can be compared quantitatively
- regressions are detectable before release

Success metrics:

- stable benchmark history over time
- easier prioritization of workflow improvements

## Cross-Cutting Work

These improvements should happen throughout the roadmap rather than in one phase.

### Observability Upgrades

Add telemetry for:

- query variation generation
- source provenance by variation
- content fetch success rate
- analysis mode selection
- follow-up query reasons
- iteration stop reasons

### Error Taxonomy

Standardize error classes and surfaced warnings for:

- provider unavailable
- provider degraded
- content fetch unavailable
- LLM analysis fallback triggered
- report generation degraded

### Caching Strategy

Improve cache design for:

- fetched page content
- repeated provider searches within one session
- identical follow-up queries

### Performance Controls

Add configurable limits for:

- per-query source caps
- per-phase timeout budgets
- content fetch concurrency
- analysis token budgets by depth mode

## Recommended Sequencing

Implement in this order:

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4
5. Phase 5
6. Phase 6

Reasoning:

- Phase 1 reduces risk.
- Phase 2 improves the biggest quality bottleneck.
- Phase 3 makes the loop smarter once retrieval improves.
- Phase 4 should be informed by how much the improved workflow still needs an agent abstraction.
- Phase 5 becomes more valuable after stronger evidence and validation signals exist.
- Phase 6 should begin early in light form, but full evaluation is most useful once the preceding contracts stabilize.

## Concrete Backlog

## Immediate Backlog

- document and type the strategy, analysis, and validation payloads
- add orchestrator end-to-end tests with mocked providers
- record query-variation provenance on each source
- improve follow-up query generation to target missing evidence types
- log iteration stop reasons explicitly
- clarify or change `--no-team` behavior

## Near-Term Backlog

- add a second provider or retrieval mode
- add evidence-strength scoring
- add primary-source coverage checks
- add contradiction severity scoring
- add report annotations for uncertainty

## Longer-Term Backlog

- decide local pipeline vs real agent-runtime direction
- remove or complete placeholder coordination abstractions
- add full benchmark harness and release gates

## Risks

### Risk: More complexity without better quality

Mitigation:

- benchmark every phase
- refuse changes that increase complexity without measurable quality wins

### Risk: Stronger planning adds latency and cost

Mitigation:

- preserve heuristic mode
- use depth-based gating
- make richer planning optional or hybrid

### Risk: Additional providers increase fragility

Mitigation:

- keep provider interface narrow
- preserve partial-failure tolerance
- add provider-level telemetry

### Risk: Attempting true agent runtime too early

Mitigation:

- choose architecture direction explicitly
- do not build more scaffolding without executing workloads through it

## Decision Log Recommendations

Capture explicit engineering decisions for:

- what "team mode" means
- whether agent abstractions are conceptual or operational
- what quality score is expected to represent
- which provider classes the workflow should optimize for
- when iterative search should stop

## Suggested Ownership

- Orchestrator contracts and phase typing: platform/core workflow
- Retrieval planning and query expansion: search/retrieval
- Analysis and validation: research intelligence
- Reporting and output schemas: output/UX
- Evaluation harness and metrics: developer productivity or QA

## Definition of Done for the Workflow

The workflow should be considered materially improved when:

- architecture descriptions and actual runtime behavior match
- first-pass retrieval quality is measurably better
- validation is claim-aware rather than mostly count-aware
- iteration produces targeted improvements instead of generic query inflation
- reports clearly express evidence quality and uncertainty
- regressions are caught by an automated evaluation harness

## Related Files

- [RESEARCH_WORKFLOW.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/RESEARCH_WORKFLOW.md)
- [`src/cc_deep_research/orchestrator.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/orchestrator.py)
- [`src/cc_deep_research/agents/research_lead.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/research_lead.py)
- [`src/cc_deep_research/agents/query_expander.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/query_expander.py)
- [`src/cc_deep_research/agents/source_collector.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/source_collector.py)
- [`src/cc_deep_research/agents/analyzer.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/analyzer.py)
- [`src/cc_deep_research/agents/deep_analyzer.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/deep_analyzer.py)
- [`src/cc_deep_research/agents/validator.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/validator.py)
- [`src/cc_deep_research/agents/reporter.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/agents/reporter.py)
- [`src/cc_deep_research/coordination/agent_pool.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/coordination/agent_pool.py)
- [`src/cc_deep_research/coordination/message_bus.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/coordination/message_bus.py)
- [`src/cc_deep_research/monitoring.py`](/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/monitoring.py)
