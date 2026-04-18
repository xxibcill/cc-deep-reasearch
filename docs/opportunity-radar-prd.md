# [DRAFT] Opportunity Radar PRD

## Document Status

- Status: Draft
- Product area: Dashboard, research workflow, content-generation workflow
- Proposed feature name: `Opportunity Radar`
- Proposed placement: top-level dashboard workspace
- Date: 2026-04-18

## Executive Summary

`cc-deep-research` is strong at execution after the user already has a topic, question, or content idea. It is materially weaker at proactive discovery. Users still need to decide what matters before they can benefit from the research pipeline, content pipeline, dashboard monitoring, or strategy layer.

`Opportunity Radar` is a new decision layer built on the app's existing infrastructure. It continuously monitors selected external and internal sources, normalizes them into structured signals, clusters those signals into opportunity candidates, scores them against the user's strategy, and presents a ranked inbox of high-value opportunities with direct action paths into research and content workflows.

This feature is intended to change the app's role in the user's life:

- from a tool the user opens after they already have an idea
- to a system that tells the user what deserves attention before competitors act on it

The core product promise is simple:

> When something important changes in my market, tell me what matters, why it matters, and what I should do next.

## 1. Background And Context

### 1.1 Current Product Strengths

Based on the current codebase and documentation, the product already has the foundations needed for a feature like Radar:

- multi-stage research orchestration
- session persistence and historical session inspection
- structured telemetry and live monitoring
- browser-based dashboard and backend API
- content-generation workflow with strategy, backlog, brief, scripting, packaging, QC, and performance stages
- a growing strategy memory model intended to act as the system's outer-layer decision boundary

Relevant implementation surfaces today include:

- research orchestration: `src/cc_deep_research/orchestrator.py`
- research run services and jobs: `src/cc_deep_research/research_runs/`
- monitoring and telemetry: `src/cc_deep_research/monitoring.py`, `src/cc_deep_research/telemetry/`
- dashboard backend: `src/cc_deep_research/web_server.py`
- live event routing: `src/cc_deep_research/event_router.py`
- content-generation orchestrator: `src/cc_deep_research/content_gen/orchestrator.py`
- dashboard frontend: `dashboard/src/`

### 1.2 Product Gap

The app currently assumes the user already knows what to research, what topic to brief, or what content direction to pursue. That means the highest-value upstream decision is still made outside the product:

- what changed
- whether it matters
- whether it is urgent
- whether it fits strategy
- whether it is worth converting into execution

This is the missing layer.

### 1.3 Why This Feature Matters

If the product remains execution-only, it competes in a crowded category of research and content assistants. If it becomes the place where users discover their next best move, it earns a much stronger habit loop and a sharper market position.

Radar turns the product into:

- a market awareness system
- a strategic prioritization layer
- a launch point for research and content execution

## 2. Problem Statement

Users of `cc-deep-research` can execute high-quality research and content workflows once they already have a topic or question. However, they still need to manually monitor fragmented sources, detect signals, interpret their significance, and decide which ones deserve action. This creates latency, inconsistency, and missed opportunities.

As a result:

- users begin with a blank page too often
- important shifts are discovered too late
- the product is used reactively instead of proactively
- valuable source material remains outside the app's operating loop
- the dashboard is a monitoring surface for active runs, not yet a daily decision surface

### 2.1 Root Cause

The system is optimized for execution after intent exists, but not for creating high-quality intent from live signals.

### 2.2 Desired Future State

The app should continuously transform fragmented changes in the user's market into a ranked set of opportunities that are:

- relevant to strategy
- recent enough to matter
- supported enough to trust
- concrete enough to act on immediately

## 3. Product Thesis

`Opportunity Radar` should make `cc-deep-research` the system that surfaces the next best opportunity before the user asks for it.

This feature should not behave like:

- a raw alert feed
- an RSS reader
- a social listening firehose
- a passive report archive

It should behave like:

- a decision inbox
- a strategic signal engine
- an execution launcher

## 4. Product Summary

`Opportunity Radar` is a proactive intelligence layer inside `cc-deep-research` that:

1. monitors selected source inputs
2. ingests and normalizes new source items as raw signals
3. clusters related signals into structured opportunities
4. scores opportunities against the user's strategy and product context
5. presents a ranked inbox of decision-ready opportunities in the dashboard
6. lets the user convert an opportunity into research or content workflows with one action
7. learns from user feedback to improve future ranking quality

## 5. Target Users

### 5.1 Primary Persona: Solo Founder / Solo Operator

Profile:

- runs a product, business, or niche personal brand
- creates research and content personally
- has limited time
- wants judgment, not dashboards full of noise

Needs:

- rapid visibility into market changes
- clear ranking of what matters now
- direct conversion into action
- minimal setup before first value

Pain points:

- checks too many sources manually
- loses time deciding what deserves research
- often notices trends only after competitors respond

### 5.2 Secondary Persona: Content Lead / Growth Marketer

Profile:

- owns editorial direction, campaign planning, or content pipeline quality
- needs a repeatable way to identify angles worth pursuing
- cares about throughput and relevance

Needs:

- source-backed market scanning
- narrative gap detection
- strategy-aware prioritization
- direct handoff into briefs and pipeline starts

Pain points:

- ideation is inconsistent
- teams chase weak topics
- monitoring and execution live in separate tools

### 5.3 Tertiary Persona: Research-Heavy Team

Profile:

- uses research for strategic decisions, not only content
- monitors sectors, competitors, customers, and public signals
- values traceability and evidence quality

Needs:

- ranked opportunities, not just alerts
- source provenance and auditability
- conversion from signals to structured research runs

Pain points:

- fragmented monitoring
- too much raw information
- weak transition from detection to decision

## 6. Jobs To Be Done

### 6.1 Core JTBD

When new information appears across my market, help me quickly understand what matters, why it matters, and what I should do next.

### 6.2 Supporting JTBDs

- When I open the app, show me the few opportunities worth my attention instead of a noisy feed.
- When a signal is important, explain its implication in plain language.
- When I choose a signal, let me turn it into research or content immediately.
- When I reject bad recommendations, learn from my behavior so the system gets better over time.

### 6.3 Emotional Job

Help the user feel ahead of the market instead of late to it.

## 7. Goals

### 7.1 Product Goals

- Help users discover high-value opportunities proactively.
- Reduce time spent manually scanning fragmented sources.
- Increase the rate at which users start research or content workflows.
- Make the dashboard the user's natural starting point.
- Turn the app into a recurring habit, not only an execution utility.

### 7.2 User Goals

- know what changed without checking multiple tools
- understand what matters now
- ignore weak or irrelevant noise
- move from detection to action with minimal friction

### 7.3 Business Goals

- increase repeat usage
- improve dashboard stickiness
- increase downstream workflow initiation
- differentiate the product from generic research assistants

## 8. Non-Goals

The V1 feature is not intended to:

- replace a full social listening platform
- become a comprehensive media monitoring suite
- automate publishing across all channels
- perform predictive revenue forecasting
- provide enterprise-grade multi-step approval workflows
- support every possible external data source in the first release
- auto-rewrite the user's strategy object based on weak feedback

## 9. Success Definition

The feature is successful if a returning user can open Radar and immediately understand:

- what changed
- what deserves attention
- what to ignore
- what to turn into research or content next

## 10. Scope

### 10.1 V1 In Scope

- source ingestion from a narrow initial set of high-signal sources
- normalization of raw signals
- clustering into opportunity candidates
- strategy-aware scoring and ranking
- Radar inbox dashboard surface
- opportunity detail view
- one-click conversion into research/content workflows
- lightweight user feedback loop
- persistence, traceability, and telemetry

### 10.2 V1 Out Of Scope

- full social network API coverage
- outbound publishing automation
- advanced collaboration and approvals
- custom scoring model editors
- forecasting and prediction systems
- enterprise alert routing as the main experience

### 10.3 Product Principle For V1

Better to show ten strong opportunities per week than two hundred weak alerts per day.

## 11. V1 Feature Set

### 11.1 Signal Ingestion

Radar ingests a deliberately limited initial source set.

Recommended initial categories:

- competitor websites and blogs
- industry news and niche publications
- product changelogs and release notes
- Reddit threads or similar public discussion sources
- internal context from strategy memory, research history, backlog themes, and saved items

Rationale:

- high signal relative to implementation cost
- easier normalization than broad social feeds
- aligned with current research and content workflows

### 11.2 Opportunity Detection

Radar should not surface raw source items directly. It should transform them into structured opportunity candidates.

Initial opportunity types:

- competitor move
- rising topic
- emerging audience question
- narrative shift
- launch/update/change event
- proof point or evidence development
- recurring problem pattern that maps to a pillar

### 11.3 Strategy-Aware Scoring

Each opportunity should be scored against the user's strategy and current app context.

Initial scoring dimensions:

- strategic relevance
- novelty
- urgency/freshness
- evidence strength
- business value
- workflow fit

### 11.4 Radar Inbox

A dedicated dashboard surface that presents ranked opportunities as a decision inbox.

Each opportunity card should include:

- title
- short summary
- why it matters snippet
- freshness indicator
- evidence count or source badge
- priority label
- direct action buttons

### 11.5 Opportunity Detail View

The detail view should provide:

- full summary
- explanation of strategic fit
- underlying evidence
- supporting sources and timestamps
- suggested angles or implications
- recommended next action

### 11.6 Workflow Conversion

Users should be able to convert an opportunity into:

- a research run
- a content brief
- a backlog item
- a content pipeline start point

### 11.7 Feedback Loop

Users should be able to:

- act on an opportunity
- save it
- dismiss it
- ignore it

That feedback should affect future ranking and suppression logic.

## 12. User Experience

### 12.1 UX Principle

Radar must answer three questions immediately:

- what changed
- why it matters
- what I should do next

### 12.2 Primary Entry Point

Radar should be a top-level dashboard destination and should become the default "start here" surface for returning users once the feature is mature enough.

### 12.3 Primary Screens

#### Radar Home

Purpose:

- provide a fast scan of what deserves attention now
- separate action-worthy items from monitoring noise

Recommended sections:

- `Top Opportunities`
- `Watchlist`
- `Saved`
- `Dismissed`

#### Opportunity Detail

Purpose:

- help the user judge whether to act
- provide enough context to start a downstream workflow confidently

#### Source Management

Purpose:

- define, activate, and maintain monitored sources
- give users confidence in what Radar is watching

### 12.4 Core Workflow

1. user opens `Radar`
2. user scans ranked opportunities
3. user opens one opportunity
4. user reviews why it matters and supporting evidence
5. user chooses an action
6. system carries context into downstream workflow
7. feedback is stored and later used to improve ranking

### 12.5 First-Run Experience

Radar should reach value quickly.

For users with no configured sources, the app should:

- reuse existing strategy memory where possible
- offer starter source presets or guided source setup
- explain what Radar watches and how it scores
- avoid showing a blank page without context

### 12.6 Empty State

When no strong opportunities exist, Radar should be truthful.

The empty state should explain:

- whether sources are configured
- whether scans have run recently
- whether only low-confidence items exist
- whether no meaningful changes were detected

### 12.7 UX Constraint

The interface must feel like a curated prioritization layer, not a generic feed reader.

## 13. Functional Requirements

### 13.1 Signal Intake

`FR-1` The system must allow Radar to monitor a defined set of source inputs.

`FR-2` The system must support source records with metadata including source type, label, URL or identifier, status, scan cadence, and last scanned timestamp.

`FR-3` The system must ingest newly discovered source items and persist them as raw signals before ranking.

`FR-4` The system must avoid duplicate raw signals when the same underlying event is detected multiple times from the same or related sources.

### 13.2 Opportunity Detection

`FR-5` The system must transform raw signals into structured opportunity candidates rather than exposing raw items directly as the default UX.

`FR-6` The system must support multiple opportunity types, including competitor move, audience question, rising topic, narrative shift, launch/update/change, and proof-point development.

`FR-7` The system must allow multiple raw signals to be clustered into a single opportunity when they refer to the same theme or event.

`FR-8` Each opportunity must store title, summary, opportunity type, supporting signals, first detected timestamp, latest detected timestamp, freshness state, and status.

### 13.3 Strategy-Aware Scoring

`FR-9` The system must score each opportunity against the user's strategy context.

`FR-10` The scoring model must support at minimum strategic relevance, novelty, urgency/freshness, evidence strength, business value, and workflow fit.

`FR-11` The system must persist both total score and component-level scoring details for each opportunity.

`FR-12` The system must generate a human-readable explanation of why an opportunity received its ranking.

### 13.4 Opportunity Lifecycle

`FR-13` The system must support opportunity statuses including `new`, `saved`, `acted_on`, `monitoring`, `dismissed`, and `archived`.

`FR-14` The user must be able to change opportunity status from the dashboard.

`FR-15` The system must retain status history so intentional dismissal can be distinguished from inactivity.

### 13.5 Radar Dashboard Experience

`FR-16` The dashboard must provide a dedicated Radar surface listing ranked opportunities.

`FR-17` The Radar list must support sorting and filtering by priority, freshness, status, source type, and opportunity type.

`FR-18` Each opportunity card must display title, short summary, priority or score label, why-it-matters snippet, freshness indicator, evidence count, and action controls.

`FR-19` The user must be able to open a detail view for each opportunity.

### 13.6 Opportunity Detail Experience

`FR-20` The detail view must display full summary, strategic fit explanation, supporting evidence, contributing sources, timestamps, and recommended actions.

`FR-21` The detail view must provide direct workflow actions including `Start Research`, `Create Brief`, `Add to Backlog`, `Save`, and `Dismiss`.

`FR-22` The detail view must preserve enough source context that a user can verify why the opportunity exists.

### 13.7 Workflow Conversion

`FR-23` A user must be able to convert an opportunity into a downstream workflow without re-entering the core context manually.

`FR-24` When converting to research, the system must prefill a research run with the opportunity summary and source context.

`FR-25` When converting to content workflow, the system must prefill the relevant brief, backlog, or pipeline entry point with the opportunity context.

`FR-26` The system must link downstream workflows back to the originating opportunity.

### 13.8 Feedback And Learning

`FR-27` The system must capture explicit feedback actions including acted on, saved, dismissed, ignored, and converted.

`FR-28` The system must store feedback at the opportunity level for later scoring improvement and analytics.

`FR-29` The system should use prior feedback to reduce repeated low-fit recommendations over time.

### 13.9 Freshness And Relevance Controls

`FR-30` The system must represent freshness explicitly so users can distinguish new signals from stale but still relevant ones.

`FR-31` The system must be able to suppress or downgrade stale opportunities based on thresholds.

`FR-32` The system must avoid repeatedly surfacing the same low-change opportunity as new unless meaningful evidence appears.

### 13.10 Auditability And Traceability

`FR-33` Every surfaced opportunity must be traceable back to its underlying source items.

`FR-34` The system must preserve timestamps and provenance for supporting signals used in ranking.

`FR-35` The dashboard must allow the user to inspect supporting evidence without losing app context.

### 13.11 First-Run And Empty-State Behavior

`FR-36` For users without configured sources, the system must provide a minimal onboarding path to define an initial watch scope.

`FR-37` If there are no strong opportunities, Radar must show a truthful empty state rather than fabricated activity.

`FR-38` The empty state should explain whether the issue is no sources, no scans, no high-confidence items, or only low-confidence items.

### 13.12 Operational Requirements

`FR-39` The system must persist Radar opportunities and their statuses across sessions.

`FR-40` The system must expose Radar data through backend APIs consumable by the existing dashboard.

`FR-41` The system should emit telemetry for major Radar lifecycle events.

`FR-42` The system must fail gracefully when source scan or opportunity-generation steps are unavailable.

## 14. Architecture Principle

Radar should be built as a new product layer on top of existing system primitives, not as a separate app with duplicate storage, orchestration, or UI conventions.

It should reuse:

- dashboard backend and frontend patterns
- existing telemetry infrastructure
- the current session and persistence model where practical
- strategy memory and content-generation state
- research run orchestration

## 15. High-Level Architecture

Radar V1 should have five core layers:

1. Source Monitoring Layer
2. Signal Normalization Layer
3. Opportunity Engine
4. Radar Application Layer
5. Dashboard/API Layer

### 15.1 Conceptual Flow

```text
configured sources
  -> fetch/scan
  -> raw signals
  -> normalization
  -> dedupe
  -> clustering
  -> opportunity candidates
  -> strategy-aware scoring
  -> ranked opportunities
  -> dashboard inbox
  -> user action / feedback
  -> research or content workflow
```

### 15.2 Recommended Integration Points In The Current Codebase

Backend and orchestration:

- `src/cc_deep_research/web_server.py`
- `src/cc_deep_research/event_router.py`
- `src/cc_deep_research/monitoring.py`
- `src/cc_deep_research/research_runs/service.py`
- `src/cc_deep_research/content_gen/orchestrator.py`
- `src/cc_deep_research/content_gen/storage/`
- `src/cc_deep_research/session_store.py`

Frontend:

- `dashboard/src/app/`
- `dashboard/src/components/`
- `dashboard/src/lib/api.ts`
- `dashboard/src/lib/websocket.ts`

## 16. Recommended Domain Model

### 16.1 `RadarSource`

Purpose:

- represents a monitored source definition

Suggested fields:

- `id`
- `source_type`
- `label`
- `url_or_identifier`
- `status`
- `scan_cadence`
- `last_scanned_at`
- `created_at`
- `updated_at`

### 16.2 `RawSignal`

Purpose:

- stores one normalized, auditable source item before clustering

Suggested fields:

- `id`
- `source_id`
- `external_id`
- `title`
- `summary`
- `url`
- `published_at`
- `discovered_at`
- `content_hash`
- `metadata`
- `normalized_type`

### 16.3 `Opportunity`

Purpose:

- stores a structured, decision-ready candidate shown to the user

Suggested fields:

- `id`
- `title`
- `summary`
- `opportunity_type`
- `status`
- `priority_label`
- `total_score`
- `first_detected_at`
- `last_detected_at`
- `freshness_state`
- `why_it_matters`
- `recommended_action`
- `created_at`
- `updated_at`

### 16.4 `OpportunitySignalLink`

Purpose:

- joins opportunities to their raw signals for many-to-many clustering and traceability

Suggested fields:

- `opportunity_id`
- `raw_signal_id`
- `link_reason`
- `created_at`

### 16.5 `OpportunityScore`

Purpose:

- stores the scoring breakdown and explanation

Suggested fields:

- `opportunity_id`
- `strategic_relevance_score`
- `novelty_score`
- `urgency_score`
- `evidence_score`
- `business_value_score`
- `workflow_fit_score`
- `explanation`
- `scored_at`

### 16.6 `OpportunityFeedback`

Purpose:

- stores user response events to opportunities

Suggested fields:

- `id`
- `opportunity_id`
- `feedback_type`
- `created_at`
- `metadata`

### 16.7 `OpportunityWorkflowLink`

Purpose:

- connects opportunities to downstream workflow objects

Suggested fields:

- `id`
- `opportunity_id`
- `workflow_type`
- `workflow_id`
- `created_at`

## 17. Service Boundaries

### 17.1 `RadarSourceService`

Responsibilities:

- CRUD for monitored sources
- source status and cadence tracking
- source activation and deactivation

### 17.2 `RadarIngestionService`

Responsibilities:

- fetch source items
- normalize them into `RawSignal`
- deduplicate repeated source items

### 17.3 `OpportunityEngine`

Responsibilities:

- cluster related signals
- create or update opportunities
- compute scores
- generate ranking explanations

### 17.4 `RadarService`

Responsibilities:

- list opportunities
- resolve detail views
- update status
- apply feedback
- return source evidence and scoring details

### 17.5 `RadarWorkflowBridge`

Responsibilities:

- convert an opportunity into research or content workflow inputs
- prefill downstream context
- persist workflow linkage metadata

## 18. API Surface

Radar should follow existing dashboard backend patterns.

Suggested endpoints:

- `GET /api/radar/opportunities`
- `GET /api/radar/opportunities/{id}`
- `POST /api/radar/opportunities/{id}/status`
- `POST /api/radar/opportunities/{id}/feedback`
- `POST /api/radar/opportunities/{id}/convert`
- `GET /api/radar/sources`
- `POST /api/radar/sources`

Optional later endpoints:

- `PATCH /api/radar/sources/{id}`
- `POST /api/radar/sources/{id}/scan`
- `GET /api/radar/stats`

## 19. Scoring Model

### 19.1 Scoring Principle

Radar should not rank opportunities by mention volume or recency alone. It should rank by decision value.

### 19.2 Scoring Dimensions

#### Strategic Relevance

Question:

- how well does this opportunity fit the user's niche, pillars, goals, boundaries, and prior wins

Inputs may include:

- pillar match
- niche match
- audience alignment
- platform fit
- forbidden topic avoidance
- prior successful theme similarity

#### Novelty

Question:

- is this genuinely new relative to what the system already knows

Inputs may include:

- similarity to recent opportunities
- overlap with prior research sessions
- overlap with backlog themes
- change magnitude relative to known coverage

#### Urgency / Freshness

Question:

- how time-sensitive is action on this opportunity

Inputs may include:

- recency of first detection
- recency of latest supporting evidence
- rate of new evidence arrival
- source type urgency

#### Evidence Strength

Question:

- how credible and well-supported is the opportunity

Inputs may include:

- number of supporting signals
- source quality
- source diversity
- cross-source agreement
- specificity of the claims or evidence

#### Business Value

Question:

- how much likely value would acting on this opportunity create

Inputs may include:

- alignment to business goal
- expected audience interest
- differentiation potential
- authority-building potential
- conversion potential

#### Workflow Fit

Question:

- can this be turned into useful execution immediately

Inputs may include:

- clarity of the opportunity
- completeness of its context
- readiness for research
- readiness for briefing or scripting

### 19.3 Initial Weighting Proposal

- Strategic Relevance: `30%`
- Business Value: `20%`
- Urgency / Freshness: `15%`
- Evidence Strength: `15%`
- Novelty: `10%`
- Workflow Fit: `10%`

This weighting is a starting calibration point and should be adjusted using real usage data.

### 19.4 User-Facing Priority Labels

Map score bands into simple labels:

- `Act Now`
- `High Potential`
- `Monitor`
- `Low Priority`

### 19.5 Why-It-Matters Explanation

Every surfaced opportunity should produce a concise explanation answering:

- what changed
- why it fits the user's strategy
- why it is ranked now
- what action is recommended

### 19.6 Freshness Decay

Scores should decay over time if no meaningful new evidence appears. Old opportunities can re-rise if new evidence materially changes relevance, urgency, or confidence.

### 19.7 Repeat Control

The system should update an existing opportunity instead of creating a new one when the underlying event or narrative has not materially changed.

## 20. Feedback And Learning Logic

### 20.1 Explicit Feedback Types

- `acted_on`
- `saved`
- `dismissed`
- `ignored`
- `converted_to_research`
- `converted_to_content`

### 20.2 Expected Ranking Effects

- acted on / converted: strengthen similar future opportunities
- saved: mild positive signal
- dismissed: lower ranking of similar future opportunities
- ignored over time: suppress low-energy repeated patterns

### 20.3 Learning Boundary

V1 should use feedback for ranking calibration and suppression only. It should not automatically rewrite strategy memory or promote weak learnings into durable strategic rules.

## 21. Workflow Conversion

### 21.1 Conversion Targets

From an opportunity, the user should be able to start:

- a research run
- a brief creation flow
- a backlog item creation flow
- a content pipeline run

### 21.2 Carry-Forward Context

The system should preserve:

- opportunity title and summary
- why-it-matters explanation
- supporting source links
- timestamps
- relevant strategy match
- detected opportunity type

### 21.3 Linkage

Every downstream workflow launched from Radar should be linked back to the originating opportunity for analytics, traceability, and future learning.

## 22. Dashboard Information Architecture

### 22.1 Top-Level Navigation

Add a top-level `Radar` destination to the dashboard.

### 22.2 Radar Home Layout

Suggested structure:

- header with summary counts and last scan freshness
- primary ranked opportunity list
- filters and sort controls
- watchlist and saved items
- source health summary

### 22.3 Opportunity Detail Layout

Suggested structure:

- title and priority block
- what changed
- why it matters
- evidence and sources
- scoring and strategic fit explanation
- recommended next actions

### 22.4 Source Management Layout

Suggested structure:

- source list
- add-source flow
- active/inactive state
- last scan and health status

## 23. Success Metrics

### 23.1 North Star Metric

`Opportunity-to-Action Rate`

Definition:

- percentage of surfaced opportunities that lead to meaningful action

Meaningful actions include:

- start research
- create brief
- add to backlog
- start content pipeline
- explicitly save for later

### 23.2 Primary Metrics

- Opportunity-to-Action Rate
- Radar Repeat Usage Rate
- Time to First Action
- Conversion to Downstream Workflow

### 23.3 Secondary Metrics

- Recommendation Acceptance Rate
- Dismissal Rate
- Ignored Opportunity Rate
- Opportunity Freshness
- Evidence Completeness Rate

### 23.4 Quality Metrics

- False Positive Rate
- Duplicate Opportunity Rate
- Explanation Usefulness
- Strategic Fit Quality

### 23.5 Operational Metrics

- Source Scan Success Rate
- Signal Ingestion Volume
- Opportunity Generation Rate
- Scoring Completion Rate
- Radar API latency
- Dashboard list/detail load time

## 24. Analytics And Telemetry

### 24.1 Product Interaction Events

- `radar_opened`
- `radar_opportunity_impression`
- `radar_opportunity_opened`
- `radar_opportunity_saved`
- `radar_opportunity_dismissed`
- `radar_opportunity_converted`
- `radar_opportunity_ignored`

### 24.2 Operational Events

- `radar.source_scan_started`
- `radar.source_scan_completed`
- `radar.signal_ingested`
- `radar.opportunity_created`
- `radar.opportunity_updated`
- `radar.opportunity_scored`
- `radar.opportunity_rescored`
- `radar.opportunity_converted`

### 24.3 Core Funnel

1. opportunity surfaced
2. opportunity viewed
3. detail opened
4. action taken
5. downstream workflow completed

## 25. Risks

### 25.1 Noise Risk

Risk:

- too many weak or obvious opportunities

Mitigation:

- narrow source scope
- aggressive ranking thresholds
- suppression of weak-confidence items

### 25.2 Relevance Risk

Risk:

- recommendations may be generic and poorly aligned to user context

Mitigation:

- use strategy memory
- provide minimal setup for better ranking
- feedback-driven tuning

### 25.3 Duplicate Risk

Risk:

- repeated surfacing of the same narrative or event

Mitigation:

- raw-signal dedupe
- opportunity clustering
- resurface only on meaningful change

### 25.4 Weak Actionability Risk

Risk:

- opportunities may be interesting but too vague to act on

Mitigation:

- require minimum context for high-priority items
- preserve source evidence
- provide recommended next actions

### 25.5 Freshness Risk

Risk:

- items surface too late to matter

Mitigation:

- practical scan cadence
- freshness-sensitive scoring
- latency monitoring

### 25.6 Black-Box Trust Risk

Risk:

- users do not trust ranking logic they cannot inspect

Mitigation:

- clear explanations
- source evidence visibility
- stored score components

### 25.7 Scope Creep Risk

Risk:

- the feature expands into a broad monitoring suite before core quality is proven

Mitigation:

- stay centered on detection, ranking, explanation, and conversion

## 26. Dependencies

- sufficient strategy memory quality for meaningful relevance scoring
- dashboard extensibility for a first-class Radar surface
- durable local persistence for new Radar entities
- smooth workflow bridges into research and content-generation paths
- telemetry instrumentation for quality tuning

## 27. Open Questions

1. What exact source set should V1 support first?
2. Should V1 rely on manual source setup, starter presets, or both?
3. What is the minimum strategy data required for useful relevance ranking?
4. Should scanning be automatic, on-demand, or both in the first release?
5. How should low-confidence opportunities appear in the UX?
6. What score threshold separates `Act Now` from `Monitor`?
7. How much scoring should be deterministic versus LLM-assisted?
8. Which downstream action should be optimized first: research, brief, backlog, or pipeline?
9. How much evidence should appear on the card versus only in detail view?
10. Should ignored opportunities decay silently or require explicit archive behavior?

## 28. Rollout Plan

### 28.1 Phase 1: Foundations

Objective:

- create the minimum backend and domain model

Scope:

- source model
- raw signal model
- opportunity model
- score model
- feedback/status model
- storage and API scaffolding
- telemetry events

Exit criteria:

- signals can be stored
- opportunities can be persisted and queried
- statuses and feedback are durable

### 28.2 Phase 2: First Opportunity Engine

Objective:

- generate useful opportunities from a narrow source set

Scope:

- initial source ingestion
- normalization and deduplication
- clustering
- first scoring heuristics
- ranking explanation generation

Exit criteria:

- ranked candidates are generated consistently
- duplicate noise is controlled
- explanations are understandable

### 28.3 Phase 3: Radar Dashboard

Objective:

- make Radar usable as a daily decision surface

Scope:

- Radar list page
- opportunity detail view
- status controls
- save/dismiss/act actions
- filtering and prioritization UI

Exit criteria:

- users can scan, inspect, and manage opportunities from the dashboard

### 28.4 Phase 4: Workflow Conversion

Objective:

- make Radar an execution launcher

Scope:

- convert to research
- convert to brief
- convert to backlog
- convert to content pipeline
- preserve context
- persist workflow links

Exit criteria:

- users can move from opportunity to execution in one step

### 28.5 Phase 5: Calibration

Objective:

- improve relevance using real telemetry and usage data

Scope:

- threshold tuning
- freshness decay tuning
- duplicate suppression improvements
- feedback-informed ranking calibration

Exit criteria:

- higher-priority items outperform lower-priority ones
- duplicate and dismissal rates are acceptable

## 29. Go / No-Go Criteria

### 29.1 Launch If

- surfaced opportunities are traceable and understandable
- action conversion works reliably
- feed quality is low-noise
- duplicate suppression is acceptable
- telemetry is sufficient for fast iteration

### 29.2 Delay If

- opportunities feel like raw alerts
- ranking explanations are weak
- workflow conversion is clumsy
- the inbox fills with stale or repetitive items

## 30. Post-MVP Expansion

After V1 proves quality, future expansions may include:

- broader source coverage
- richer watchlists
- scheduled recurring scans
- richer opportunity types
- outbound alerts
- team collaboration and approvals
- more advanced scoring controls

These should remain second-order improvements after the core decision loop is validated.

## 31. Final Product Thesis

The MVP is successful if users begin opening Radar to decide what to do next.

That is the behavioral change the feature is meant to create:

- not more alerts
- not more content for its own sake
- but a tighter loop from market change to strategic action
