"""Planner agent that decomposes research queries into structured subtasks."""

from __future__ import annotations

import re
import uuid
from typing import Any

from cc_deep_research.models import (
    AnalysisResult,
    IterationHistoryRecord,
    PlannerIterationDecision,
    PlannerResult,
    QueryProfile,
    ResearchDepth,
    ResearchPlan,
    ResearchSubtask,
    SearchResultItem,
    StrategyResult,
    ValidationResult,
)
from cc_deep_research.monitoring import (
    STOP_REASON_LIMIT_REACHED,
    STOP_REASON_LOW_QUALITY,
    STOP_REASON_SUCCESS,
)
from cc_deep_research.orchestration.helpers import build_follow_up_queries


class PlannerAgent:
    """Agent that plans research by decomposing queries into subtasks.

    This agent analyzes research queries and creates structured plans with:
    - Discrete subtasks that can be executed by specialized agents
    - Dependencies between subtasks for proper execution ordering
    - Parallel execution groups for independent subtasks
    - Success criteria and fallback strategies
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the planner agent.

        Args:
            config: Agent configuration dictionary.
        """
        self._config = config

    def create_plan(
        self,
        query: str,
        depth: ResearchDepth,
        context: dict[str, Any] | None = None,
    ) -> PlannerResult:
        """Create a research plan with subtasks.

        Args:
            query: The research query string.
            depth: Research depth mode (quick/standard/deep).
            context: Optional context information (e.g., previous results).

        Returns:
            PlannerResult containing the research plan and reasoning.
        """
        # Analyze the query
        complexity = self._assess_complexity(query)
        profile = self._build_query_profile(query)

        # Generate subtasks based on query analysis
        subtasks = self._generate_subtasks(query, depth, profile, context)

        # Determine execution order and dependencies
        subtasks = self._assign_dependencies(subtasks, query, profile)
        execution_order = self._compute_execution_order(subtasks)

        # Create the plan
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        plan = ResearchPlan(
            plan_id=plan_id,
            query=query,
            summary=self._generate_summary(query, subtasks, profile),
            subtasks=subtasks,
            execution_order=execution_order,
            success_criteria=self._generate_success_criteria(query, depth),
            fallback_strategies=self._generate_fallback_strategies(query, profile),
            estimated_total_sources=self._estimate_total_sources(subtasks, depth),
            depth=depth,
        )

        # Generate reasoning and alternatives
        reasoning = self._generate_reasoning(query, subtasks, profile, complexity)
        alternatives = self._generate_alternatives(query, depth, profile)

        return PlannerResult(
            plan=plan,
            reasoning=reasoning,
            alternative_approaches=alternatives,
            complexity_assessment=complexity,
            confidence=self._calculate_confidence(query, subtasks),
            estimated_time_minutes=self._estimate_time(subtasks, depth),
        )

    def decide_research_iteration(
        self,
        *,
        query: str,
        strategy: StrategyResult,
        analysis: AnalysisResult | dict[str, Any],
        validation: ValidationResult | dict[str, Any] | None,
        sources: list[SearchResultItem],
        iteration: int,
        max_iterations: int,
        min_sources: int | None,
        iteration_history: list[IterationHistoryRecord] | None = None,
        enable_iterative_search: bool = True,
    ) -> PlannerIterationDecision:
        """Decide whether the staged workflow should continue the research loop."""
        del iteration_history  # Reserved for future planner strategies.

        analysis_result = AnalysisResult.model_validate(analysis)
        validation_result = (
            ValidationResult.model_validate(validation) if validation is not None else None
        )
        missing_information = self._collect_missing_information(
            analysis=analysis_result,
            validation=validation_result,
        )
        current_hypothesis = self._build_current_hypothesis(
            query=query,
            analysis=analysis_result,
            validation=validation_result,
            missing_information=missing_information,
        )
        next_queries = build_follow_up_queries(
            query=query,
            analysis=analysis_result,
            validation=validation_result,
            enable_iterative_search=enable_iterative_search,
        )
        if not next_queries:
            next_queries = self._queries_from_gaps(query, analysis_result)
        next_queries = self._apply_follow_up_bias(
            query=query,
            strategy=strategy,
            queries=next_queries,
        )

        if not enable_iterative_search:
            return PlannerIterationDecision(
                should_continue=False,
                reason_code="planner_loop_disabled",
                stop_reason=STOP_REASON_SUCCESS,
                rationale="Iterative search is disabled, so the planner ends after the current pass.",
                current_hypothesis=current_hypothesis,
                missing_information=missing_information,
                next_queries=[],
                confidence=0.9,
            )

        if iteration >= max_iterations:
            return PlannerIterationDecision(
                should_continue=False,
                reason_code="planner_iteration_limit_reached",
                stop_reason=STOP_REASON_LIMIT_REACHED,
                rationale=f"Reached the planner safety limit of {max_iterations} iterations.",
                current_hypothesis=current_hypothesis,
                missing_information=missing_information,
                next_queries=[],
                confidence=0.95,
            )

        target_source_count = max(
            min_sources or 0,
            validation_result.target_source_count if validation_result else 0,
        )
        has_findings = bool(
            analysis_result.key_findings
            or analysis_result.themes
            or analysis_result.comprehensive_synthesis.strip()
        )
        has_enough_sources = (
            len(sources) >= target_source_count if target_source_count else len(sources) > 0
        )
        validation_requires_follow_up = bool(
            validation_result is not None and validation_result.needs_follow_up
        )
        has_open_gaps = bool(analysis_result.normalized_gaps())

        should_continue = False
        reason_code = "goal_satisfied"
        rationale = "The planner believes the current evidence is sufficient for the research goal."
        stop_reason: str | None = STOP_REASON_SUCCESS

        if validation_requires_follow_up and next_queries:
            should_continue = True
            reason_code = "planner_requested_more_evidence"
            rationale = "Validation and planner review indicate the goal still needs more evidence."
            stop_reason = None
        elif not has_findings and next_queries:
            should_continue = True
            reason_code = "planner_requested_initial_evidence"
            rationale = "The planner does not yet have enough synthesized findings, so it schedules another search pass."
            stop_reason = None
        elif not has_enough_sources and next_queries:
            should_continue = True
            reason_code = "planner_requested_source_coverage"
            rationale = "The planner wants broader source coverage before treating the goal as complete."
            stop_reason = None
        elif has_open_gaps and next_queries:
            should_continue = True
            reason_code = "planner_requested_gap_closure"
            rationale = "The planner identified unresolved gaps and generated focused follow-up queries."
            stop_reason = None
        elif validation_requires_follow_up or not has_findings:
            reason_code = "planner_insufficient_without_query"
            rationale = "The planner sees unresolved quality issues but could not generate a productive next search step."
            stop_reason = STOP_REASON_LOW_QUALITY

        confidence = self._decision_confidence(
            should_continue=should_continue,
            validation=validation_result,
            has_findings=has_findings,
            has_enough_sources=has_enough_sources,
        )
        return PlannerIterationDecision(
            should_continue=should_continue,
            reason_code=reason_code,
            stop_reason=stop_reason,
            rationale=rationale,
            current_hypothesis=current_hypothesis,
            missing_information=missing_information,
            next_queries=next_queries if should_continue else [],
            confidence=confidence,
        )

    def _assess_complexity(self, query: str) -> str:
        """Assess the complexity of a research query.

        Args:
            query: The research query.

        Returns:
            Complexity level: "simple", "moderate", or "complex".
        """
        words = query.split()
        word_count = len(words)

        # Check for complexity indicators
        has_multiple_aspects = any(
            indicator in query.lower()
            for indicator in [" and ", " vs ", " versus ", " or ", " compared to ", " difference between "]
        )
        has_temporal = any(
            term in query.lower()
            for term in ["history", "evolution", "timeline", "trend", "changes", "over time"]
        )
        has_comparison = any(
            term in query.lower()
            for term in ["compare", "contrast", "better", "worse", "best", "pros and cons"]
        )
        has_quantitative = bool(re.search(r"\d+|how many|how much|statistics|data|percentage", query.lower()))

        # Count question words (more questions = more complex)
        question_words = sum(1 for w in ["what", "how", "why", "when", "where", "which", "who"] if w in query.lower())

        # Calculate complexity score
        score = 0
        if word_count > 20:
            score += 2
        elif word_count > 10:
            score += 1

        if has_multiple_aspects:
            score += 2
        if has_temporal:
            score += 1
        if has_comparison:
            score += 2
        if has_quantitative:
            score += 1
        if question_words > 1:
            score += 1

        if score >= 5:
            return "complex"
        elif score >= 2:
            return "moderate"
        return "simple"

    def _build_query_profile(self, query: str) -> QueryProfile:
        """Build a profile for the query to guide planning."""
        words = self._tokenize(query)
        key_terms = self._extract_key_terms(words)
        intent = self._classify_intent(query, words)
        is_time_sensitive = self._detect_time_sensitivity(query, words)
        target_source_classes = self._infer_source_classes(query, words, intent, is_time_sensitive)

        return QueryProfile(
            intent=intent,
            is_time_sensitive=is_time_sensitive,
            key_terms=key_terms,
            target_source_classes=target_source_classes,
        )

    def _generate_subtasks(
        self,
        query: str,
        depth: ResearchDepth,
        profile: QueryProfile,
        context: dict[str, Any] | None,
    ) -> list[ResearchSubtask]:
        """Generate subtasks based on query analysis."""
        subtasks: list[ResearchSubtask] = []
        complexity = self._assess_complexity(query)

        # Determine base number of search subtasks based on depth
        search_task_counts = {
            ResearchDepth.QUICK: 1,
            ResearchDepth.STANDARD: 2,
            ResearchDepth.DEEP: 3,
        }
        base_search_count = search_task_counts.get(depth, 2)

        # Adjust for complexity
        if complexity == "complex":
            base_search_count += 1
        elif complexity == "simple" and depth != ResearchDepth.QUICK:
            base_search_count = max(1, base_search_count - 1)

        # Generate search subtasks
        search_aspects = self._identify_search_aspects(query, profile, base_search_count)

        for i, aspect in enumerate(search_aspects):
            task_id = f"search-{i + 1}"
            subtasks.append(
                ResearchSubtask(
                    id=task_id,
                    title=f"Search: {aspect['title']}",
                    description=aspect["description"],
                    task_type="search",
                    assigned_agent="source_collector",
                    priority=1,
                    query_variations=aspect.get("queries", [aspect["title"]]),
                    estimated_sources=self._estimate_sources_for_aspect(aspect, depth),
                    inputs={"aspect": aspect["title"], "queries": aspect.get("queries", [])},
                )
            )

        # Add analysis subtasks if depth is not quick
        if depth != ResearchDepth.QUICK:
            # Analysis depends on search results
            search_ids = [t.id for t in subtasks if t.task_type == "search"]

            subtasks.append(
                ResearchSubtask(
                    id="analyze-main",
                    title="Analyze collected sources",
                    description=f"Perform comprehensive analysis of sources collected for: {query}",
                    task_type="analyze",
                    assigned_agent="analyzer",
                    dependencies=search_ids,
                    priority=2,
                    estimated_sources=0,  # Uses sources from dependencies
                    inputs={"query": query},
                )
            )

        # Add validation subtask for deep mode
        if depth == ResearchDepth.DEEP:
            subtasks.append(
                ResearchSubtask(
                    id="validate",
                    title="Validate research quality",
                    description="Validate the quality and completeness of the research findings",
                    task_type="validate",
                    assigned_agent="validator",
                    dependencies=["analyze-main"],
                    priority=3,
                    estimated_sources=0,
                    inputs={"query": query},
                )
            )

        # Add synthesis subtask (always needed)
        analysis_deps = [t.id for t in subtasks if t.task_type == "analyze"]
        if not analysis_deps:
            analysis_deps = [t.id for t in subtasks if t.task_type == "search"]

        subtasks.append(
            ResearchSubtask(
                id="synthesize",
                title="Synthesize final report",
                description="Combine all findings into a comprehensive research report",
                task_type="synthesize",
                assigned_agent="reporter",
                dependencies=analysis_deps,
                priority=4,
                estimated_sources=0,
                inputs={"query": query},
            )
        )

        return subtasks

    def _identify_search_aspects(
        self,
        query: str,
        profile: QueryProfile,
        count: int,
    ) -> list[dict[str, Any]]:
        """Identify different aspects to search for."""
        aspects: list[dict[str, Any]] = []
        query_lower = query.lower()

        # Check for comparison patterns
        if any(term in query_lower for term in [" vs ", " versus ", " compared to ", " difference between "]):
            # Split comparison query into two aspects
            parts = re.split(r"\s+(?:vs|versus|compared to)\s+", query, flags=re.IGNORECASE)
            if len(parts) >= 2:
                aspects.append({
                    "title": f"Research: {parts[0].strip()}",
                    "description": f"Search for information about {parts[0].strip()}",
                    "queries": [parts[0].strip(), f"what is {parts[0].strip()}"],
                })
                aspects.append({
                    "title": f"Research: {parts[1].strip()}",
                    "description": f"Search for information about {parts[1].strip()}",
                    "queries": [parts[1].strip(), f"what is {parts[1].strip()}"],
                })
                # Add comparison aspect if more aspects needed
                if count > 2:
                    aspects.append({
                        "title": f"Comparison: {parts[0].strip()} vs {parts[1].strip()}",
                        "description": f"Search for direct comparisons between {parts[0].strip()} and {parts[1].strip()}",
                        "queries": [f"{parts[0].strip()} vs {parts[1].strip()}", f"compare {parts[0].strip()} and {parts[1].strip()}"],
                    })

        # Check for "and" patterns (multiple aspects)
        elif " and " in query_lower and len(aspects) < count:
            and_parts = re.split(r"\s+and\s+", query, flags=re.IGNORECASE)
            for part in and_parts[:count]:
                part = part.strip()
                if part and not any(part.lower() in a.get("title", "").lower() for a in aspects):
                    aspects.append({
                        "title": f"Research: {part}",
                        "description": f"Search for information about {part}",
                        "queries": [part],
                    })

        # Default: create aspects based on key terms
        if not aspects:
            # Primary aspect: the full query
            aspects.append({
                "title": query,
                "description": f"Search for information about: {query}",
                "queries": [query],
            })

            # Additional aspects based on key terms and intent
            if count > 1 and profile.key_terms:
                # Create aspect for key terms
                key_terms_query = " ".join(profile.key_terms[:3])
                if key_terms_query.lower() not in query_lower:
                    aspects.append({
                        "title": f"Key concepts: {key_terms_query}",
                        "description": f"Search for information about key concepts: {key_terms_query}",
                        "queries": [key_terms_query],
                    })

            if count > 2:
                # Create aspect for intent-specific search
                if profile.intent == "evidence-seeking":
                    aspects.append({
                        "title": f"Evidence and research: {query}",
                        "description": "Search for scientific evidence and research studies",
                        "queries": [f"{query} research evidence", f"{query} studies"],
                    })
                elif profile.intent == "comparative":
                    aspects.append({
                        "title": f"Comparison analysis: {query}",
                        "description": "Search for comparative analysis and reviews",
                        "queries": [f"{query} comparison review", f"{query} analysis"],
                    })
                elif profile.is_time_sensitive:
                    aspects.append({
                        "title": f"Latest updates: {query}",
                        "description": "Search for recent news and updates",
                        "queries": [f"{query} latest news", f"{query} recent updates"],
                    })

        # Ensure we have at least 'count' aspects
        while len(aspects) < count:
            base_query = aspects[0]["queries"][0] if aspects else query
            variations = [
                f"overview of {base_query}",
                f"guide to {base_query}",
                f"what is {base_query}",
                f"{base_query} explained",
            ]
            next_variation = variations[len(aspects) % len(variations)]
            aspects.append({
                "title": next_variation.capitalize(),
                "description": f"Search for: {next_variation}",
                "queries": [next_variation],
            })

        return aspects[:count]

    def _assign_dependencies(
        self,
        subtasks: list[ResearchSubtask],
        query: str,
        profile: QueryProfile,
    ) -> list[ResearchSubtask]:
        """Assign dependencies between subtasks based on their types."""
        # Group tasks by type
        search_tasks = [t for t in subtasks if t.task_type == "search"]
        analyze_tasks = [t for t in subtasks if t.task_type == "analyze"]
        validate_tasks = [t for t in subtasks if t.task_type == "validate"]
        synthesize_tasks = [t for t in subtasks if t.task_type == "synthesize"]

        # Search tasks have no dependencies (they run first)
        # Already set in _generate_subtasks

        # Analyze tasks depend on all search tasks
        for task in analyze_tasks:
            if not task.dependencies:
                task.dependencies = [t.id for t in search_tasks]

        # Validate tasks depend on analyze tasks
        for task in validate_tasks:
            if not task.dependencies:
                task.dependencies = [t.id for t in analyze_tasks]

        # Synthesize depends on analyze (or validate if present)
        for task in synthesize_tasks:
            if not task.dependencies:
                if validate_tasks:
                    task.dependencies = [t.id for t in validate_tasks]
                elif analyze_tasks:
                    task.dependencies = [t.id for t in analyze_tasks]
                else:
                    task.dependencies = [t.id for t in search_tasks]

        return subtasks

    def _compute_execution_order(self, subtasks: list[ResearchSubtask]) -> list[list[str]]:
        """Compute the order of execution with parallel groups."""
        # Topological sort with parallel grouping
        task_map = {t.id: t for t in subtasks}
        completed: set[str] = set()
        order: list[list[str]] = []

        while len(completed) < len(subtasks):
            # Find tasks whose dependencies are all satisfied
            ready = []
            for task in subtasks:
                if task.id in completed:
                    continue
                if all(dep in completed for dep in task.dependencies):
                    ready.append(task.id)

            if not ready:
                # Circular dependency or error - just add remaining
                remaining = [t.id for t in subtasks if t.id not in completed]
                if remaining:
                    order.append(remaining)
                break

            # Group ready tasks by priority (same priority can run in parallel)
            ready_tasks = [task_map[tid] for tid in ready]
            priority_groups: dict[int, list[str]] = {}
            for task in ready_tasks:
                if task.priority not in priority_groups:
                    priority_groups[task.priority] = []
                priority_groups[task.priority].append(task.id)

            # Add groups in priority order
            for priority in sorted(priority_groups.keys()):
                order.append(priority_groups[priority])

            completed.update(ready)

        return order

    def _estimate_sources_for_aspect(self, aspect: dict[str, Any], depth: ResearchDepth) -> int:
        """Estimate sources needed for a search aspect."""
        base = {
            ResearchDepth.QUICK: 3,
            ResearchDepth.STANDARD: 7,
            ResearchDepth.DEEP: 12,
        }
        return base.get(depth, 5)

    def _generate_summary(
        self,
        query: str,
        subtasks: list[ResearchSubtask],
        profile: QueryProfile,
    ) -> str:
        """Generate a summary of the research plan."""
        search_count = len([t for t in subtasks if t.task_type == "search"])
        has_analysis = any(t.task_type == "analyze" for t in subtasks)
        has_validation = any(t.task_type == "validate" for t in subtasks)

        parts = [f"Research plan with {search_count} search task(s)"]
        if has_analysis:
            parts.append("analysis")
        if has_validation:
            parts.append("validation")
        parts.append("synthesis")

        return f"{', '.join(parts)} for: {query[:100]}"

    def _generate_success_criteria(self, query: str, depth: ResearchDepth) -> list[str]:
        """Generate success criteria for the research."""
        min_sources = {
            ResearchDepth.QUICK: 3,
            ResearchDepth.STANDARD: 10,
            ResearchDepth.DEEP: 20,
        }

        return [
            f"Collect at least {min_sources.get(depth, 10)} relevant sources",
            "All key findings are supported by citations",
            "No critical gaps remain in the research",
            "Report provides clear answer to the query",
        ]

    def _generate_fallback_strategies(self, query: str, profile: QueryProfile) -> list[str]:
        """Generate fallback strategies if primary approach fails."""
        strategies = [
            "Expand search queries with broader terms if initial results are sparse",
            "Use alternative search providers if primary provider fails",
            "Reduce depth requirements if time constraints apply",
        ]

        if profile.intent == "evidence-seeking":
            strategies.append("Include secondary sources if primary research is unavailable")

        if profile.is_time_sensitive:
            strategies.append("Prioritize recent sources over comprehensive coverage")

        return strategies

    def _estimate_total_sources(self, subtasks: list[ResearchSubtask], depth: ResearchDepth) -> int:
        """Estimate total sources to be collected."""
        search_tasks = [t for t in subtasks if t.task_type == "search"]
        return sum(t.estimated_sources for t in search_tasks)

    def _generate_reasoning(
        self,
        query: str,
        subtasks: list[ResearchSubtask],
        profile: QueryProfile,
        complexity: str,
    ) -> str:
        """Generate reasoning for the plan."""
        search_count = len([t for t in subtasks if t.task_type == "search"])
        has_analysis = any(t.task_type == "analyze" for t in subtasks)

        reasoning_parts = [
            f"Query assessed as {complexity} complexity with {profile.intent} intent.",
            f"Created {search_count} search task(s) to cover different aspects.",
        ]

        if has_analysis:
            reasoning_parts.append("Added analysis task to synthesize findings from search results.")

        if any(t.task_type == "validate" for t in subtasks):
            reasoning_parts.append("Added validation task to ensure research quality.")

        reasoning_parts.append("Final synthesis will combine all findings into a coherent report.")

        return " ".join(reasoning_parts)

    def _generate_alternatives(
        self,
        query: str,
        depth: ResearchDepth,
        profile: QueryProfile,
    ) -> list[str]:
        """Generate alternative approaches considered."""
        alternatives = []

        if depth != ResearchDepth.QUICK:
            alternatives.append("Quick mode: Skip analysis and validation for faster results")

        if depth != ResearchDepth.DEEP:
            alternatives.append("Deep mode: Add validation and more search aspects for thoroughness")

        if profile.intent == "comparative":
            alternatives.append("Sequential search: Search one aspect at a time for more focused results")

        return alternatives

    def _calculate_confidence(self, query: str, subtasks: list[ResearchSubtask]) -> float:
        """Calculate confidence in the plan."""
        # Base confidence
        confidence = 0.8

        # Adjust based on plan completeness
        has_search = any(t.task_type == "search" for t in subtasks)
        has_analyze = any(t.task_type == "analyze" for t in subtasks)
        has_synthesize = any(t.task_type == "synthesize" for t in subtasks)

        if has_search and has_analyze and has_synthesize:
            confidence += 0.1

        # Reduce confidence for very short or very long queries
        word_count = len(query.split())
        if word_count < 3:
            confidence -= 0.1
        elif word_count > 30:
            confidence -= 0.05

        return min(1.0, max(0.5, confidence))

    def _estimate_time(self, subtasks: list[ResearchSubtask], depth: ResearchDepth) -> int:
        """Estimate time in minutes for the research."""
        base_time = {
            ResearchDepth.QUICK: 2,
            ResearchDepth.STANDARD: 5,
            ResearchDepth.DEEP: 10,
        }

        # Add time per search task
        search_count = len([t for t in subtasks if t.task_type == "search"])
        time_per_search = 1  # minute

        total = base_time.get(depth, 5) + (search_count * time_per_search)

        # Add time for analysis and validation
        if any(t.task_type == "analyze" for t in subtasks):
            total += 2
        if any(t.task_type == "validate" for t in subtasks):
            total += 1

        return total

    # Helper methods from ResearchLeadAgent
    @staticmethod
    def _tokenize(query: str) -> list[str]:
        """Tokenize a query into normalized lowercase terms."""
        return re.findall(r"[a-z0-9]+", query.lower())

    @staticmethod
    def _extract_key_terms(words: list[str]) -> list[str]:
        """Return stable keywords with duplicates removed."""
        stop_words = {
            "a", "an", "and", "are", "best", "can", "for", "from", "how",
            "in", "is", "of", "or", "the", "to", "what", "which", "who", "why",
        }
        key_terms: list[str] = []
        seen: set[str] = set()
        for word in words:
            if len(word) <= 2 or word in stop_words or word in seen:
                continue
            seen.add(word)
            key_terms.append(word)
            if len(key_terms) >= 8:
                break
        return key_terms

    def _classify_intent(self, query: str, words: list[str]) -> str:
        """Classify the primary research intent."""
        comparative_terms = {"better", "compare", "comparison", "versus", "vs", "difference", "differences"}
        evidence_terms = {"citation", "citations", "data", "dataset", "datasets", "evidence", "evidence-based", "proof", "prove", "research", "source", "sources", "study", "studies", "supporting"}

        if any(term in words for term in comparative_terms):
            return "comparative"
        if any(term in words for term in evidence_terms):
            return "evidence-seeking"
        if self._detect_time_sensitivity(query, words):
            return "time-sensitive"
        return "informational"

    def _detect_time_sensitivity(self, query: str, words: list[str]) -> bool:
        """Detect whether a query depends on recent or dated information."""
        lowered = query.lower()
        time_terms = {"breaking", "current", "currently", "forecast", "latest", "newest", "now", "recent", "recently", "today", "tonight", "trending", "update", "updates", "upcoming", "yesterday"}
        month_names = {"january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"}

        if any(term in words for term in time_terms):
            return True
        if "as of" in lowered or "this week" in lowered or "this month" in lowered:
            return True
        if any(month in words for month in month_names):
            return True
        return re.search(r"\b(19|20)\d{2}\b", query) is not None

    def _infer_source_classes(
        self,
        query: str,
        words: list[str],
        intent: str,
        is_time_sensitive: bool,
    ) -> list[str]:
        """Infer likely source classes needed."""
        lowered = query.lower()
        academic_terms = {"academic", "clinical", "journal", "meta-analysis", "paper", "papers", "peer", "peer-reviewed", "research", "scholar", "science", "scientific", "study", "studies", "trial"}
        official_terms = {"agency", "compliance", "court", "fda", "filing", "filings", "government", "guidance", "law", "legal", "official", "policy", "regulation", "regulations", "regulator", "rule", "rules", "sec", "standard", "standards"}
        market_terms = {"earnings", "equity", "finance", "financial", "forecast", "industry", "investment", "investor", "market", "pricing", "revenue", "stock", "trade", "valuation"}

        target_source_classes: list[str] = []

        if is_time_sensitive:
            target_source_classes.append("news")
        if intent == "evidence-seeking" or any(term in lowered for term in academic_terms):
            target_source_classes.append("academic")
        if any(term in lowered for term in official_terms):
            target_source_classes.append("official_docs")
        if any(term in lowered for term in market_terms):
            target_source_classes.append("market_analysis")
        if intent == "comparative":
            target_source_classes.append("official_docs")
            target_source_classes.append("market_analysis")
        if not target_source_classes:
            target_source_classes.append("official_docs" if len(words) <= 4 else "news")

        return target_source_classes

    def _collect_missing_information(
        self,
        *,
        analysis: AnalysisResult,
        validation: ValidationResult | None,
    ) -> list[str]:
        """Summarize the most important unresolved evidence gaps."""
        missing_information: list[str] = []
        for gap in analysis.normalized_gaps():
            description = gap.gap_description.strip()
            if description:
                missing_information.append(description)
        if validation is not None:
            missing_information.extend(issue.strip() for issue in validation.issues if issue.strip())
            if not missing_information:
                missing_information.extend(
                    self._describe_failure_mode(mode) for mode in validation.failure_modes
                )
        deduplicated: list[str] = []
        seen: set[str] = set()
        for item in missing_information:
            normalized = item.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            deduplicated.append(item)
        return deduplicated[:4]

    def _build_current_hypothesis(
        self,
        *,
        query: str,
        analysis: AnalysisResult,
        validation: ValidationResult | None,
        missing_information: list[str],
    ) -> str:
        """Build a compact working hypothesis from the current evidence."""
        signals: list[str] = []
        findings: list[str] = []
        for finding in analysis.key_findings[:2]:
            title = finding.title if hasattr(finding, "title") else str(finding)
            if isinstance(title, str) and title:
                findings.append(title.strip())
        if findings:
            signals.append("Current evidence points to " + "; ".join(findings) + ".")
        elif analysis.themes:
            signals.append(
                "Current evidence clusters around " + ", ".join(analysis.themes[:3]) + "."
            )
        else:
            signals.append(f"The current evidence for '{query}' is still thin.")
        if validation is not None and validation.quality_score > 0:
            signals.append(f"Observed quality score is {validation.quality_score:.2f}.")
        if missing_information:
            signals.append("Open questions remain around " + "; ".join(missing_information[:2]) + ".")
        return " ".join(signals).strip()

    def _apply_follow_up_bias(
        self,
        *,
        query: str,
        strategy: StrategyResult,
        queries: list[str],
    ) -> list[str]:
        """Bias follow-up searches toward the strategy's preferred evidence type."""
        candidates = list(queries)
        bias = strategy.strategy.follow_up_bias
        if bias == "recent_updates":
            candidates.insert(0, f"{query} latest updates current developments")
        elif bias == "primary_evidence":
            candidates.insert(0, f"{query} primary sources official documents")
        elif bias == "comparison_evidence":
            candidates.insert(0, f"{query} comparison evidence methodology rebuttal")
        return self._deduplicate_queries(candidates)[:8]

    def _queries_from_gaps(self, query: str, analysis: AnalysisResult) -> list[str]:
        """Generate follow-up queries directly from analysis gaps."""
        queries: list[str] = []
        for gap in analysis.normalized_gaps():
            queries.extend(gap.suggested_queries)
            if gap.gap_description.strip():
                queries.append(f"{query} {gap.gap_description}")
        return self._deduplicate_queries(queries)[:8]

    def _deduplicate_queries(self, queries: list[str]) -> list[str]:
        """Return queries in first-seen order with case-insensitive deduplication."""
        deduplicated: list[str] = []
        seen: set[str] = set()
        for candidate in queries:
            normalized = candidate.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduplicated.append(candidate.strip())
        return deduplicated

    def _describe_failure_mode(self, failure_mode: str) -> str:
        """Translate validator failure modes into planner-friendly gap labels."""
        descriptions = {
            "weak_primary_source_coverage": "primary-source coverage is still weak",
            "stale_evidence_for_time_sensitive_query": "the evidence is not current enough",
            "thin_claim_support": "important claims still lack direct support",
            "high_contradiction_pressure": "conflicting evidence still needs reconciliation",
            "narrow_source_type_diversity": "source-type diversity is too narrow",
            "limited_domain_diversity": "domain diversity is too narrow",
            "limited_content_depth": "source depth is too shallow",
            "missing_citation_links": "citation coverage is incomplete",
        }
        return descriptions.get(failure_mode, failure_mode.replace("_", " "))

    def _decision_confidence(
        self,
        *,
        should_continue: bool,
        validation: ValidationResult | None,
        has_findings: bool,
        has_enough_sources: bool,
    ) -> float:
        """Estimate planner confidence in the continue/stop decision."""
        base = 0.55
        if validation is not None:
            base = max(base, min(0.95, validation.quality_score))
        if has_findings:
            base += 0.1
        if has_enough_sources:
            base += 0.05
        if should_continue:
            base -= 0.05
        return max(0.0, min(1.0, base))


__all__ = ["PlannerAgent"]
