"""Tests for ResearchMonitor."""

import re
from unittest.mock import patch

import pytest

from cc_deep_research.models import QueryFamily, SearchResultItem
from cc_deep_research.monitoring import (
    STOP_REASON_DEGRADED_EXECUTION,
    MonitorEvent,
    ResearchMonitor,
)


class TestResearchMonitor:
    """Tests for ResearchMonitor."""

    def test_monitor_disabled(self):
        """Test that disabled monitor has no effect."""
        monitor = ResearchMonitor(enabled=False)
        assert not monitor.is_enabled()

        # These should not raise errors, just no output
        monitor.section("Test Section")
        monitor.log("Test message")
        monitor.log_result("tavily", 10, 1234)
        monitor.log_aggregation(10, 8)
        monitor.log_timing("test operation", 500)
        monitor.summary(5, ["tavily"], 2000)

    def test_monitor_enabled(self):
        """Test that enabled monitor produces output."""
        with patch('click.echo') as mock_echo:
            monitor = ResearchMonitor(enabled=True)
            assert monitor.is_enabled()

            monitor.section("Test Section")
            assert mock_echo.call_count == 1

    def test_section_format(self):
        """Test section formatting."""
        with patch('click.echo') as mock_echo:
            monitor = ResearchMonitor(enabled=True)
            monitor.section("Configuration")

            # Check that the call contains the expected content with timestamp prefix
            call_args = mock_echo.call_args[0][0]
            assert "=== Configuration ===" in call_args
            # Timestamp format: [HH:MM:SS]
            assert re.match(r"\[\d{2}:\d{2}:\d{2}\]", call_args)

    def test_log_format(self):
        """Test log formatting."""
        with patch('click.echo') as mock_echo:
            monitor = ResearchMonitor(enabled=True)
            monitor.log("Test message")

            # Check that the call contains the expected content with timestamp prefix
            call_args = mock_echo.call_args[0][0]
            assert "Test message" in call_args
            assert re.match(r"\[\d{2}:\d{2}:\d{2}\]", call_args)

    def test_log_with_indent(self):
        """Test log with indentation."""
        with patch('click.echo') as mock_echo:
            monitor = ResearchMonitor(enabled=True)
            monitor.log("Indented message", indent=4)

            # Check that the call contains the expected content with indentation
            call_args = mock_echo.call_args[0][0]
            assert "    Indented message" in call_args
            assert re.match(r"\[\d{2}:\d{2}:\d{2}\]", call_args)

    def test_log_result_format(self):
        """Test result logging format."""
        with patch('click.echo') as mock_echo:
            monitor = ResearchMonitor(enabled=True)
            monitor.log_result("tavily", 10, 1234)

            # Check that the call contains the expected content with timestamp prefix
            call_args = mock_echo.call_args[0][0]
            assert "[TAVILY] Response received: 10 results (1234ms)" in call_args
            assert re.match(r"\[\d{2}:\d{2}:\d{2}\]", call_args)

    def test_log_aggregation_format(self):
        """Test aggregation logging format."""
        with patch('click.echo') as mock_echo:
            monitor = ResearchMonitor(enabled=True)
            monitor.log_aggregation(10, 8)

            # Check that the call contains the expected content with timestamp prefix
            call_args = mock_echo.call_args[0][0]
            assert "[AGGREGATOR] Deduplicated: 2 duplicate(s) removed, 8 unique result(s)" in call_args
            assert re.match(r"\[\d{2}:\d{2}:\d{2}\]", call_args)

    def test_log_timing_format(self):
        """Test timing logging format."""
        with patch('click.echo') as mock_echo:
            monitor = ResearchMonitor(enabled=True)
            monitor.log_timing("Search", 500)

            # Check that the call contains the expected content with timestamp prefix
            call_args = mock_echo.call_args[0][0]
            assert "Search completed in 500ms" in call_args
            assert re.match(r"\[\d{2}:\d{2}:\d{2}\]", call_args)

    def test_summary_format(self):
        """Test summary formatting."""
        with patch('click.echo') as mock_echo:
            monitor = ResearchMonitor(enabled=True)
            monitor.summary(10, ["tavily"], 2500)

            calls = mock_echo.call_args_list
            assert len(calls) == 3
            # Check content with timestamp prefix
            assert "Total sources: 10" in str(calls[0])
            assert "Providers used: tavily" in str(calls[1])
            assert "Total execution time: 2.5s" in str(calls[2])

    def test_summary_empty_providers(self):
        """Test summary with no providers."""
        with patch('click.echo') as mock_echo:
            monitor = ResearchMonitor(enabled=True)
            monitor.summary(0, [], 0)

            calls = mock_echo.call_args_list
            assert len(calls) == 3
            assert "none" in str(calls[1])

    def test_start_operation(self):
        """Test starting an operation."""
        monitor = ResearchMonitor(enabled=True)

        event = monitor.start_operation("test", "provider", query="test query")

        assert event.name == "test"
        assert event.category == "provider"
        assert event.status == "in_progress"
        assert event.metadata == {"query": "test query"}
        assert event.duration_ms == 0  # Not ended yet

    def test_start_operation_disabled_monitor(self):
        """Test starting operation when monitor is disabled."""
        monitor = ResearchMonitor(enabled=False)

        event = monitor.start_operation("test", "provider")

        # Event is created but not stored
        assert event.name == "test"
        assert len(monitor._events) == 0

    def test_end_operation_success(self):
        """Test ending an operation successfully."""
        monitor = ResearchMonitor(enabled=True)
        event = monitor.start_operation("test", "provider")

        # Ensure some time passes before ending
        import time
        time.sleep(0.001)  # Sleep 1ms to ensure duration > 0

        monitor.end_operation(event, success=True)

        assert event.status == "completed"
        assert event.end_time is not None
        assert event.duration_ms >= 0  # Allow for 0 due to precision

    def test_end_operation_failure(self):
        """Test ending an operation with failure."""
        monitor = ResearchMonitor(enabled=True)
        event = monitor.start_operation("test", "provider")

        monitor.end_operation(event, success=False)

        assert event.status == "failed"
        assert event.end_time is not None

    def test_record_metric(self):
        """Test recording a metric."""
        monitor = ResearchMonitor(enabled=True)

        monitor.record_metric("test_metric", 42, "category")

        assert len(monitor._events) == 1
        event = monitor._events[0]
        assert event.name == "test_metric"
        assert event.category == "category"
        assert event.metadata["value"] == 42
        assert event.status == "completed"

    def test_record_metric_disabled_monitor(self):
        """Test recording metric when monitor is disabled."""
        monitor = ResearchMonitor(enabled=False)

        monitor.record_metric("test_metric", 42, "category")

        # No events recorded
        assert len(monitor._events) == 0

    def test_finalize_session_counts_parallel_and_tool_telemetry(self):
        """Test summary counters include researcher, search, and tool telemetry."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("session-123", "test query", "standard")

        monitor.log_researcher_event("spawned", "task-1")
        monitor.record_search_query(
            query="test query",
            provider="tavily",
            result_count=3,
            duration_ms=42,
            status="success",
        )
        monitor.record_tool_call(
            tool_name="mcp.web_reader",
            status="success",
            duration_ms=15,
        )
        monitor.record_llm_usage(
            operation="analysis",
            model="claude-test",
            prompt_tokens=10,
            completion_tokens=5,
            duration_ms=33,
            agent_id="analyzer",
        )

        summary = monitor.finalize_session(
            total_sources=3,
            providers=["tavily"],
            total_time_ms=250,
        )

        assert summary["instances_spawned"] == 1
        assert summary["search_queries"] == 1
        assert summary["tool_calls"] == 2
        assert summary["llm_prompt_tokens"] == 10
        assert summary["llm_completion_tokens"] == 5
        assert summary["llm_total_tokens"] == 15

    def test_record_query_variations_and_source_provenance(self):
        """Query families and provenance summaries should be emitted in telemetry."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("session-123", "test query", "standard")
        families = [
            QueryFamily(query="baseline query", family="baseline", intent_tags=["baseline"]),
            QueryFamily(query="official query", family="primary-source", intent_tags=["official"]),
        ]
        sources = [
            SearchResultItem(
                url="https://agency.gov/report",
                title="Report",
                score=1.0,
            ),
            SearchResultItem(
                url="https://example.com/analysis",
                title="Analysis",
                score=0.8,
            ),
        ]
        sources[0].add_query_provenance(query="official query", family="primary-source")
        sources[1].add_query_provenance(query="baseline query", family="baseline")

        monitor.record_query_variations(
            original_query="test query",
            query_families=families,
            strategy_intent="informational",
        )
        monitor.record_source_provenance(
            query_families=families,
            sources=sources,
            stage="initial_collection",
        )

        variation_event = next(
            event for event in monitor._telemetry_events if event["event_type"] == "query.variations"
        )
        provenance_event = next(
            event for event in monitor._telemetry_events if event["event_type"] == "source.provenance"
        )

        assert variation_event["metadata"]["variation_count"] == 2
        assert provenance_event["metadata"]["source_count"] == 2
        assert provenance_event["metadata"]["family_totals"]["baseline"] == 1
        assert provenance_event["metadata"]["family_totals"]["primary-source"] == 1

    def test_record_iteration_stop_normalizes_unknown_reason(self):
        """Unknown stop reasons should fall back to degraded_execution."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("session-123", "test query", "standard")

        stop_reason = monitor.record_iteration_stop(
            iteration=2,
            stop_reason="unexpected_reason",
            detail="something odd happened",
        )
        summary = monitor.finalize_session(
            total_sources=0,
            providers=[],
            total_time_ms=100,
            stop_reason=stop_reason,
        )

        assert stop_reason == STOP_REASON_DEGRADED_EXECUTION
        assert summary["stop_reason"] == STOP_REASON_DEGRADED_EXECUTION

    def test_record_analysis_mode_and_follow_up_decision(self):
        """Analysis mode and follow-up reason payloads should be explicit."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("session-123", "test query", "deep")

        monitor.record_analysis_mode(
            depth="deep",
            mode="deep_multi_pass",
            deep_analysis_enabled=True,
        )
        monitor.record_follow_up_decision(
            iteration=1,
            reason="validation_requested_follow_up",
            follow_up_queries=["test query official guidance"],
            failure_modes=["weak_primary_sources"],
            quality_score=0.42,
        )

        analysis_mode_event = next(
            event
            for event in monitor._telemetry_events
            if event["event_type"] == "analysis.mode_selected"
        )
        follow_up_event = next(
            event
            for event in monitor._telemetry_events
            if event["event_type"] == "follow_up.decision"
        )

        assert analysis_mode_event["metadata"]["mode"] == "deep_multi_pass"
        assert follow_up_event["metadata"]["reason"] == "validation_requested_follow_up"
        assert follow_up_event["metadata"]["follow_up_count"] == 1


class TestMonitorEvent:
    """Tests for MonitorEvent."""

    def test_duration_ms_not_ended(self):
        """Test duration when event is not ended."""
        event = MonitorEvent(
            name="test",
            category="test",
            start_time=0.0,
        )

        assert event.duration_ms == 0

    def test_duration_ms_ended(self):
        """Test duration when event is ended."""
        event = MonitorEvent(
            name="test",
            category="test",
            start_time=0.0,
            end_time=1.5,  # 1.5 seconds
        )

        assert event.duration_ms == 1500

    def test_duration_ms_fractional(self):
        """Test duration with fractional seconds."""
        event = MonitorEvent(
            name="test",
            category="test",
            start_time=0.0,
            end_time=0.5,  # 0.5 seconds
        )

        assert event.duration_ms == 500


class TestEventCorrelation:
    """Tests for event correlation and parent-child relationships."""

    def test_monitor_event_has_event_id(self):
        """Test that MonitorEvent has a unique event_id."""
        event1 = MonitorEvent(name="test1", category="test", start_time=0.0)
        event2 = MonitorEvent(name="test2", category="test", start_time=0.0)

        assert event1.event_id != event2.event_id
        assert len(event1.event_id) == 36  # UUID format

    def test_monitor_event_parent_event_id(self):
        """Test that MonitorEvent can have a parent_event_id."""
        event = MonitorEvent(
            name="child",
            category="test",
            start_time=0.0,
            parent_event_id="parent-123",
        )

        assert event.parent_event_id == "parent-123"

    def test_emit_event_returns_event_id(self):
        """Test that emit_event returns a unique event_id."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        event_id = monitor.emit_event(
            event_type="test.event",
            category="test",
            name="test",
        )

        assert event_id is not None
        assert len(event_id) == 36  # UUID format

    def test_emit_event_includes_correlation_fields(self):
        """Test that emitted events include correlation fields."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        parent_id = monitor.emit_event(
            event_type="parent.event",
            category="test",
            name="parent",
        )

        child_id = monitor.emit_event(
            event_type="child.event",
            category="test",
            name="child",
            parent_event_id=parent_id,
        )

        # Find the child event
        child_event = next(
            e for e in monitor._telemetry_events if e["event_id"] == child_id
        )

        assert child_event["parent_event_id"] == parent_id
        assert child_event["sequence_number"] > 0

    def test_sequence_numbers_increase(self):
        """Test that sequence numbers increase monotonically."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        ids = [
            monitor.emit_event(event_type=f"event.{i}", category="test", name=f"event{i}")
            for i in range(5)
        ]

        events = [e for e in monitor._telemetry_events if e["event_id"] in ids]
        events.sort(key=lambda e: e["sequence_number"])

        sequence_numbers = [e["sequence_number"] for e in events]
        assert sequence_numbers == sorted(sequence_numbers)
        assert len(set(sequence_numbers)) == 5  # All unique

    def test_parent_stack_current_parent_id(self):
        """Test the parent stack for managing current parent."""
        monitor = ResearchMonitor(enabled=False, persist=False)

        assert monitor.current_parent_id is None

        monitor.push_parent("parent-1")
        assert monitor.current_parent_id == "parent-1"

        monitor.push_parent("parent-2")
        assert monitor.current_parent_id == "parent-2"

        popped = monitor.pop_parent()
        assert popped == "parent-2"
        assert monitor.current_parent_id == "parent-1"

    def test_set_session_pushes_parent(self):
        """Test that set_session pushes the session event as parent."""
        monitor = ResearchMonitor(enabled=False, persist=False)

        session_id = monitor.set_session("test-session", "query", "standard")

        assert monitor.current_parent_id == session_id

    def test_emit_event_uses_current_parent(self):
        """Test that emit_event uses current parent from stack when not specified."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        session_event_id = monitor.set_session("test-session", "query", "standard")

        # Emit event without explicit parent_event_id
        child_id = monitor.emit_event(
            event_type="child.event",
            category="test",
            name="child",
        )

        child_event = next(
            e for e in monitor._telemetry_events if e["event_id"] == child_id
        )

        # Should have session event as parent
        assert child_event["parent_event_id"] == session_event_id

    def test_start_operation_inherits_parent(self):
        """Test that start_operation inherits parent from stack."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        session_event_id = monitor.set_session("test-session", "query", "standard")

        op_event = monitor.start_operation("test-op", "test")

        assert op_event.parent_event_id == session_event_id

    def test_start_operation_has_event_id(self):
        """Test that start_operation creates events with event_id."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        op_event = monitor.start_operation("test-op", "test")

        assert op_event.event_id is not None
        assert len(op_event.event_id) == 36  # UUID format

    def test_finalize_session_pops_parent(self):
        """Test that finalize_session pops the session parent."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        assert monitor.current_parent_id is not None

        monitor.finalize_session(total_sources=0, providers=[], total_time_ms=100)

        assert monitor.current_parent_id is None

    def test_sequence_resets_on_new_session(self):
        """Test that sequence counter resets for new sessions."""
        monitor = ResearchMonitor(enabled=False, persist=False)

        # First session
        monitor.set_session("session-1", "query", "standard")
        monitor.emit_event(event_type="event.1", category="test", name="event1")
        monitor.emit_event(event_type="event.2", category="test", name="event2")
        monitor.emit_event(event_type="event.3", category="test", name="event3")

        # Should have 4 events (1 session.started + 3 explicit events)
        first_session_count = monitor._sequence_counter
        assert first_session_count == 4

        # Second session - counter should reset
        monitor.set_session("session-2", "query", "standard")
        monitor.emit_event(event_type="event.4", category="test", name="event4")

        # Should be 2 (1 session.started + 1 explicit event)
        assert monitor._sequence_counter == 2


class TestPhaseRunnerInstrumentation:
    """Tests for phase runner lifecycle events."""

    @pytest.mark.asyncio
    async def test_run_phase_emits_started_and_completed(self):
        """PhaseRunner.run_phase should emit started and completed events."""
        from cc_deep_research.orchestration.phases import PhaseRunner

        monitor = ResearchMonitor(enabled=False, persist=False)
        runner = PhaseRunner(monitor=monitor)
        monitor.set_session("test-session", "query", "standard")

        async def operation():
            return "result"

        await runner.run_phase(
            phase_hook=None,
            phase_key="test_phase",
            description="Test phase",
            operation=operation,
        )

        # Filter for phase-specific events (phase.started, phase.completed)
        phase_events = [e for e in monitor._telemetry_events if e["event_type"].startswith("phase.")]

        started = next(e for e in phase_events if e["event_type"] == "phase.started")
        completed = next(e for e in phase_events if e["event_type"] == "phase.completed")

        assert started["name"] == "test_phase"
        assert started["status"] == "started"
        assert completed["name"] == "test_phase"
        assert completed["status"] == "completed"
        assert completed["duration_ms"] is not None

    @pytest.mark.asyncio
    async def test_run_phase_sets_parent_for_children(self):
        """PhaseRunner.run_phase should set parent for child events."""
        from cc_deep_research.orchestration.phases import PhaseRunner

        monitor = ResearchMonitor(enabled=False, persist=False)
        runner = PhaseRunner(monitor=monitor)
        monitor.set_session("test-session", "query", "standard")

        child_event_ids = []

        async def operation():
            # Emit a child event during the phase
            child_id = monitor.emit_event(
                event_type="child.event",
                category="test",
                name="child",
            )
            child_event_ids.append(child_id)
            return "result"

        await runner.run_phase(
            phase_hook=None,
            phase_key="test_phase",
            description="Test phase",
            operation=operation,
        )

        # Find the phase.started event
        phase_started = next(
            e for e in monitor._telemetry_events
            if e["event_type"] == "phase.started" and e["name"] == "test_phase"
        )

        # Find the child event
        child_event = next(
            e for e in monitor._telemetry_events
            if e["event_id"] == child_event_ids[0]
        )

        # Child should have phase as parent
        assert child_event["parent_event_id"] == phase_started["event_id"]

    @pytest.mark.asyncio
    async def test_run_phase_emits_failed_on_exception(self):
        """PhaseRunner.run_phase should emit phase.failed on exception."""
        from cc_deep_research.orchestration.phases import PhaseRunner

        monitor = ResearchMonitor(enabled=False, persist=False)
        runner = PhaseRunner(monitor=monitor)
        monitor.set_session("test-session", "query", "standard")

        async def failing_operation():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await runner.run_phase(
                phase_hook=None,
                phase_key="failing_phase",
                description="Failing phase",
                operation=failing_operation,
            )

        # Filter for phase-specific events (phase.started, phase.failed)
        phase_events = [e for e in monitor._telemetry_events if e["event_type"].startswith("phase.")]

        started = next(e for e in phase_events if e["event_type"] == "phase.started")
        failed = next(e for e in phase_events if e["event_type"] == "phase.failed")

        assert started["name"] == "failing_phase"
        assert failed["name"] == "failing_phase"
        assert failed["status"] == "failed"
        assert "error_type" in failed["metadata"]
        assert "error_message" in failed["metadata"]

    @pytest.mark.asyncio
    async def test_run_phase_pops_parent_after_completion(self):
        """PhaseRunner.run_phase should pop parent after completion."""
        from cc_deep_research.orchestration.phases import PhaseRunner

        monitor = ResearchMonitor(enabled=False, persist=False)
        runner = PhaseRunner(monitor=monitor)
        session_id = monitor.set_session("test-session", "query", "standard")

        # Parent should be session event
        assert monitor.current_parent_id == session_id

        async def operation():
            # During phase, parent should still be set
            return "result"

        await runner.run_phase(
            phase_hook=None,
            phase_key="test_phase",
            description="Test phase",
            operation=operation,
        )

        # After phase, current_parent_id should be back to session
        assert monitor.current_parent_id == session_id

    @pytest.mark.asyncio
    async def test_run_phase_tracks_current_phase_id(self):
        """PhaseRunner should track current_phase_id during execution."""
        from cc_deep_research.orchestration.phases import PhaseRunner

        monitor = ResearchMonitor(enabled=False, persist=False)
        runner = PhaseRunner(monitor=monitor)
        monitor.set_session("test-session", "query", "standard")

        captured_phase_id = None

        async def operation():
            nonlocal captured_phase_id
            captured_phase_id = runner.current_phase_id
            return "result"

        await runner.run_phase(
            phase_hook=None,
            phase_key="test_phase",
            description="Test phase",
            operation=operation,
        )

        # During operation, current_phase_id should be set
        assert captured_phase_id is not None

        # After operation, current_phase_id should be None
        assert runner.current_phase_id is None


class TestAgentLifecycleEvents:
    """Tests for agent lifecycle event emission."""

    def test_emit_agent_lifecycle_helper(self):
        """Test the agent lifecycle helper function."""
        from cc_deep_research.orchestration.source_collection import _emit_agent_lifecycle

        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        event_id = _emit_agent_lifecycle(
            monitor,
            event_type="agent.spawned",
            agent_id="researcher-1",
            agent_type="researcher",
            status="spawned",
            metadata={"query": "test query"},
        )

        assert event_id is not None

        event = next(e for e in monitor._telemetry_events if e["event_id"] == event_id)
        assert event["event_type"] == "agent.spawned"
        assert event["category"] == "agent"
        assert event["agent_id"] == "researcher-1"
        assert event["metadata"]["agent_type"] == "researcher"
        assert event["metadata"]["query"] == "test query"

    def test_emit_agent_lifecycle_with_parent(self):
        """Test agent lifecycle events with parent correlation."""
        from cc_deep_research.orchestration.source_collection import _emit_agent_lifecycle

        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        parent_id = monitor.emit_event(
            event_type="phase.started",
            category="phase",
            name="source_collection",
            status="started",
        )

        event_id = _emit_agent_lifecycle(
            monitor,
            event_type="agent.spawned",
            agent_id="researcher-1",
            agent_type="researcher",
            status="spawned",
            parent_event_id=parent_id,
        )

        event = next(e for e in monitor._telemetry_events if e["event_id"] == event_id)
        assert event["parent_event_id"] == parent_id


class TestToolLifecycleEvents:
    """Tests for tool lifecycle event emission."""

    @pytest.mark.asyncio
    async def test_tool_events_have_parent_correlation(self):
        """Tool events should be correlated with parent phase."""
        from cc_deep_research.orchestration.phases import PhaseRunner

        monitor = ResearchMonitor(enabled=False, persist=False)
        runner = PhaseRunner(monitor=monitor)
        monitor.set_session("test-session", "query", "standard")

        tool_event_ids = []

        async def operation_with_tool():
            # Simulate tool call during phase
            tool_id = monitor.emit_event(
                event_type="tool.started",
                category="tool",
                name="web_fetch",
                status="started",
            )
            tool_event_ids.append(tool_id)
            return "result"

        await runner.run_phase(
            phase_hook=None,
            phase_key="content_fetch",
            description="Fetching content",
            operation=operation_with_tool,
        )

        # Find phase event
        phase_event = next(
            e for e in monitor._telemetry_events
            if e["event_type"] == "phase.started" and e["name"] == "content_fetch"
        )

        # Find tool event
        tool_event = next(
            e for e in monitor._telemetry_events
            if e["event_id"] == tool_event_ids[0]
        )

        # Tool should have phase as parent
        assert tool_event["parent_event_id"] == phase_event["event_id"]


class TestLLMRouteTelemetry:
    """Tests for LLM route telemetry events."""

    def test_record_llm_route_selected(self):
        """Test recording LLM route selection."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        monitor.record_llm_route_selected(
            agent_id="analyzer",
            transport="openrouter_api",
            provider="openrouter",
            model="claude-sonnet-4-6",
            source="planner",
        )

        event = next(
            e for e in monitor._telemetry_events
            if e["event_type"] == "llm.route_selected"
        )

        assert event["agent_id"] == "analyzer"
        assert event["category"] == "llm"
        assert event["status"] == "selected"
        assert event["metadata"]["transport"] == "openrouter_api"
        assert event["metadata"]["provider"] == "openrouter"
        assert event["metadata"]["model"] == "claude-sonnet-4-6"
        assert event["metadata"]["source"] == "planner"

    def test_record_llm_route_fallback(self):
        """Test recording LLM route fallback."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        monitor.record_llm_route_fallback(
            agent_id="analyzer",
            original_transport="anthropic_api",
            fallback_transport="openrouter_api",
            reason="transport_unavailable",
        )

        event = next(
            e for e in monitor._telemetry_events
            if e["event_type"] == "llm.route_fallback"
        )

        assert event["agent_id"] == "analyzer"
        assert event["status"] == "fallback"
        assert event["metadata"]["original_transport"] == "anthropic_api"
        assert event["metadata"]["fallback_transport"] == "openrouter_api"
        assert event["metadata"]["reason"] == "transport_unavailable"

    def test_record_llm_route_request(self):
        """Test recording LLM route request start."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        monitor.record_llm_route_request(
            agent_id="analyzer",
            transport="openrouter_api",
            provider="openrouter",
            model="claude-sonnet-4-6",
            operation="analyze_sources",
        )

        event = next(
            e for e in monitor._telemetry_events
            if e["event_type"] == "llm.route_request"
        )

        assert event["agent_id"] == "analyzer"
        assert event["status"] == "started"
        assert event["name"] == "analyze_sources"
        assert event["metadata"]["transport"] == "openrouter_api"
        assert event["metadata"]["provider"] == "openrouter"
        assert event["metadata"]["model"] == "claude-sonnet-4-6"
        assert event["metadata"]["operation"] == "analyze_sources"

    def test_record_llm_route_completion_success(self):
        """Test recording successful LLM route completion."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        monitor.record_llm_route_completion(
            agent_id="analyzer",
            transport="openrouter_api",
            provider="openrouter",
            model="claude-sonnet-4-6",
            operation="analyze_sources",
            duration_ms=1500,
            success=True,
            prompt_tokens=1000,
            completion_tokens=500,
        )

        event = next(
            e for e in monitor._telemetry_events
            if e["event_type"] == "llm.route_completion"
        )

        assert event["agent_id"] == "analyzer"
        assert event["status"] == "completed"
        assert event["duration_ms"] == 1500
        assert event["metadata"]["transport"] == "openrouter_api"
        assert event["metadata"]["provider"] == "openrouter"
        assert event["metadata"]["model"] == "claude-sonnet-4-6"
        assert event["metadata"]["success"] is True
        assert event["metadata"]["prompt_tokens"] == 1000
        assert event["metadata"]["completion_tokens"] == 500
        assert event["metadata"]["total_tokens"] == 1500

    def test_record_llm_route_completion_failure(self):
        """Test recording failed LLM route completion."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        monitor.record_llm_route_completion(
            agent_id="analyzer",
            transport="cerebras_api",
            provider="cerebras",
            model="llama-3.3-70b",
            operation="analyze_sources",
            duration_ms=30000,
            success=False,
        )

        event = next(
            e for e in monitor._telemetry_events
            if e["event_type"] == "llm.route_completion"
        )

        assert event["status"] == "failed"
        assert event["metadata"]["success"] is False

    def test_build_llm_route_summary(self):
        """Test building LLM route summary from telemetry events."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        # Record various LLM route events
        monitor.record_llm_route_selected(
            agent_id="analyzer",
            transport="openrouter_api",
            provider="openrouter",
            model="claude-sonnet-4-6",
            source="planner",
        )

        monitor.record_llm_route_completion(
            agent_id="analyzer",
            transport="openrouter_api",
            provider="openrouter",
            model="claude-sonnet-4-6",
            operation="analyze",
            duration_ms=1500,
            success=True,
            prompt_tokens=1000,
            completion_tokens=500,
        )

        monitor.record_llm_route_completion(
            agent_id="validator",
            transport="cerebras_api",
            provider="cerebras",
            model="llama-3.3-70b",
            operation="validate",
            duration_ms=800,
            success=True,
            prompt_tokens=500,
            completion_tokens=200,
        )

        monitor.record_llm_route_fallback(
            agent_id="researcher",
            original_transport="anthropic_api",
            fallback_transport="openrouter_api",
            reason="timeout",
        )

        summary = monitor._build_llm_route_summary()

        assert summary["total_requests"] == 2
        assert summary["fallback_count"] == 1
        assert "openrouter_api" in summary["transports"]
        assert "cerebras_api" in summary["transports"]
        assert summary["transports"]["openrouter_api"]["requests"] == 1
        assert summary["transports"]["openrouter_api"]["tokens"] == 1500
        assert summary["transports"]["cerebras_api"]["requests"] == 1
        assert summary["transports"]["cerebras_api"]["tokens"] == 700
        assert "analyzer" in summary["agents"]
        assert "validator" in summary["agents"]
        assert summary["agents"]["analyzer"]["request_count"] == 1
        assert summary["agents"]["analyzer"]["total_tokens"] == 1500
        assert "analyzer" in summary["planned_routes"]
        assert summary["planned_routes"]["analyzer"]["transport"] == "openrouter_api"

    def test_finalize_session_includes_llm_route_summary(self):
        """Test that finalize_session includes LLM route summary."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        monitor.record_llm_route_completion(
            agent_id="analyzer",
            transport="openrouter_api",
            provider="openrouter",
            model="claude-sonnet-4-6",
            operation="analyze",
            duration_ms=1500,
            success=True,
            prompt_tokens=1000,
            completion_tokens=500,
        )

        summary = monitor.finalize_session(
            total_sources=10,
            providers=["tavily"],
            total_time_ms=5000,
        )

        assert "llm_route" in summary
        assert summary["llm_route"]["total_requests"] == 1
        assert "openrouter_api" in summary["llm_route"]["transports"]


class TestSemanticEvents:
    """Tests for semantic event helper methods."""

    def test_emit_decision_made_routing(self):
        """Test emitting a routing decision event."""
        from cc_deep_research.monitoring import REASON_FALLBACK, SEVERITY_INFO

        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        event_id = monitor.emit_decision_made(
            decision_type="routing",
            reason_code=REASON_FALLBACK,
            chosen_option="openrouter_api",
            inputs={"original": "anthropic_api", "reason": "unavailable"},
            rejected_options=["cerebras_api"],
            phase="initialization",
        )

        assert event_id is not None
        event = next(e for e in monitor._telemetry_events if e["event_id"] == event_id)
        assert event["event_type"] == "decision.made"
        assert event["category"] == "decision"
        assert event["status"] == "decided"
        assert event["reason_code"] == REASON_FALLBACK
        assert event["severity"] == SEVERITY_INFO
        assert event["phase"] == "initialization"
        assert event["actor_type"] == "system"  # No agent_id provided
        assert event["metadata"]["decision_type"] == "routing"
        assert event["metadata"]["chosen_option"] == "openrouter_api"
        assert event["metadata"]["rejected_options"] == ["cerebras_api"]

    def test_emit_decision_made_with_agent(self):
        """Test emitting a decision event with an agent actor."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        cause_event_id = monitor.emit_event(
            event_type="analysis.completed",
            category="analysis",
            name="quality_check",
            status="completed",
        )

        event_id = monitor.emit_decision_made(
            decision_type="follow_up",
            reason_code="validation_requested_follow_up",
            chosen_option="continue_iteration",
            inputs={"quality_score": 0.45, "threshold": 0.7},
            rejected_options=["stop_iteration"],
            cause_event_ids=[cause_event_id],
            confidence=0.65,
            phase="analysis",
            actor_id="validator-agent",
        )

        assert event_id is not None
        event = next(e for e in monitor._telemetry_events if e["event_id"] == event_id)
        assert event["actor_type"] == "agent"
        assert event["actor_id"] == "validator-agent"
        assert event["cause_event_id"] == cause_event_id
        assert event["metadata"]["confidence"] == 0.65
        assert event["metadata"]["cause_event_ids"] == [cause_event_id]

    def test_emit_state_changed_provider(self):
        """Test emitting a state change event for provider availability."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        event_id = monitor.emit_state_changed(
            state_scope="session",
            state_key="available_providers",
            before=["tavily", "anthropic_api"],
            after=["tavily"],  # anthropic_api became unavailable
            change_type="update",
            phase="initialization",
        )

        assert event_id is not None
        event = next(e for e in monitor._telemetry_events if e["event_id"] == event_id)
        assert event["event_type"] == "state.changed"
        assert event["category"] == "state"
        assert event["name"] == "session.available_providers"
        assert event["status"] == "changed"
        assert event["phase"] == "initialization"
        # Note: degraded flag depends on explicit degraded param, not inferred from state changes
        assert event["metadata"]["state_scope"] == "session"
        assert event["metadata"]["state_key"] == "available_providers"
        assert event["metadata"]["before"] == ["tavily", "anthropic_api"]
        assert event["metadata"]["after"] == ["tavily"]

    def test_emit_state_changed_with_cause(self):
        """Test emitting a state change event with a cause."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        cause_id = monitor.emit_event(
            event_type="provider.health_check_failed",
            category="provider",
            name="anthropic_api",
            status="failed",
        )

        event_id = monitor.emit_state_changed(
            state_scope="provider",
            state_key="anthropic_api_available",
            before=True,
            after=False,
            change_type="update",
            caused_by_event_id=cause_id,
            checkpoint="provider-degraded",
        )

        event = next(e for e in monitor._telemetry_events if e["event_id"] == event_id)
        assert event["cause_event_id"] == cause_id
        assert event["metadata"]["checkpoint"] == "provider-degraded"

    def test_emit_degradation_detected_transport(self):
        """Test emitting a degradation event for transport fallback."""
        from cc_deep_research.monitoring import REASON_FALLBACK, SEVERITY_WARNING

        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        cause_id = monitor.emit_event(
            event_type="llm.route_request",
            category="llm",
            name="anthropic_api",
            status="timeout",
        )

        event_id = monitor.emit_degradation_detected(
            reason_code=REASON_FALLBACK,
            severity=SEVERITY_WARNING,
            scope="transport",
            recoverable=True,
            mitigation="Using openrouter_api instead",
            impact="LLM transport degraded from anthropic_api to openrouter_api",
            caused_by_event_id=cause_id,
            phase="analysis",
            actor_id="analyzer",
        )

        assert event_id is not None
        event = next(e for e in monitor._telemetry_events if e["event_id"] == event_id)
        assert event["event_type"] == "degradation.detected"
        assert event["category"] == "degradation"
        assert event["name"] == "transport.degraded"
        assert event["status"] == "degraded"
        assert event["degraded"] is True
        assert event["reason_code"] == REASON_FALLBACK
        assert event["severity"] == SEVERITY_WARNING
        assert event["actor_type"] == "agent"
        assert event["actor_id"] == "analyzer"
        assert event["cause_event_id"] == cause_id
        assert event["metadata"]["scope"] == "transport"
        assert event["metadata"]["recoverable"] is True
        assert event["metadata"]["mitigation"] == "Using openrouter_api instead"

    def test_emit_degradation_detected_unrecoverable(self):
        """Test emitting an unrecoverable degradation event."""
        from cc_deep_research.monitoring import SEVERITY_ERROR

        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        event_id = monitor.emit_degradation_detected(
            reason_code="all_transports_failed",
            severity=SEVERITY_ERROR,
            scope="transport",
            recoverable=False,
            impact="No LLM transport available, using heuristic fallback",
        )

        event = next(e for e in monitor._telemetry_events if e["event_id"] == event_id)
        assert event["severity"] == SEVERITY_ERROR
        assert event["metadata"]["recoverable"] is False
        assert event["degraded"] is True

    def test_trace_contract_fields_present(self):
        """Test that all trace contract fields are present in emitted events."""
        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard", run_id="run-123")

        event_id = monitor.emit_event(
            event_type="test.event",
            category="test",
            name="test_operation",
            status="completed",
            agent_id="test-agent",
            phase="testing",
            operation="test_op",
            attempt=2,
            severity="info",
            reason_code="test_reason",
            degraded=False,
        )

        event = next(e for e in monitor._telemetry_events if e["event_id"] == event_id)

        # Core identity fields
        assert "event_id" in event
        assert "parent_event_id" in event
        assert "sequence_number" in event
        assert "timestamp" in event
        assert "session_id" in event

        # Trace contract fields
        assert event["trace_version"] == "1.0.0"
        assert event["run_id"] == "run-123"
        assert event["cause_event_id"] is None

        # Event classification
        assert event["event_type"] == "test.event"
        assert event["category"] == "test"
        assert event["name"] == "test_operation"
        assert event["status"] == "completed"
        assert event["severity"] == "info"
        assert event["reason_code"] == "test_reason"

        # Execution context
        assert event["phase"] == "testing"
        assert event["operation"] == "test_op"
        assert event["attempt"] == 2

        # Actor
        assert event["actor_type"] == "agent"
        assert event["actor_id"] == "test-agent"
        assert event["agent_id"] == "test-agent"  # Backward compatibility

        # Metrics
        assert event["degraded"] is False


class TestCheckpointPersistence:
    """Tests for durable checkpoint persistence."""

    def test_emit_checkpoint_returns_checkpoint_id(self, tmp_path):
        """Test that emit_checkpoint returns a unique checkpoint_id."""
        monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
        monitor.set_session("test-session", "query", "standard")

        checkpoint_id = monitor.emit_checkpoint(
            phase="strategy",
            operation="execute",
            input_ref={"query": "test query"},
        )

        assert checkpoint_id is not None
        assert checkpoint_id.startswith("cp-")

    def test_emit_checkpoint_persists_to_disk(self, tmp_path):
        """Test that checkpoints are persisted to disk."""
        monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
        monitor.set_session("test-session", "query", "standard")

        checkpoint_id = monitor.emit_checkpoint(
            phase="strategy",
            operation="execute",
            input_ref={"query": "test query"},
        )

        # Verify checkpoint directory exists
        checkpoints_dir = tmp_path / "test-session" / "checkpoints"
        assert checkpoints_dir.exists()

        # Verify manifest exists
        manifest_path = checkpoints_dir / "manifest.json"
        assert manifest_path.exists()

        # Verify checkpoint is in manifest
        manifest = monitor.get_checkpoint_manifest()
        assert len(manifest.get("checkpoints", [])) == 1
        assert manifest["checkpoints"][0]["checkpoint_id"] == checkpoint_id

    def test_emit_checkpoint_tracks_lineage(self, tmp_path):
        """Test that checkpoints track parent-child lineage."""
        monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
        monitor.set_session("test-session", "query", "standard")

        # Create first checkpoint
        cp1_id = monitor.emit_checkpoint(
            phase="session_start",
            operation="initialize",
            input_ref={"query": "test"},
        )

        # Create second checkpoint with first as parent
        cp2_id = monitor.emit_checkpoint(
            phase="strategy",
            operation="execute",
            input_ref={"query": "test"},
            parent_checkpoint_id=cp1_id,
        )

        # Verify lineage
        cp2 = monitor.get_checkpoint_by_id(cp2_id)
        assert cp2 is not None
        assert cp2["parent_checkpoint_id"] == cp1_id

    def test_finalize_checkpoint_marks_resume_safe(self, tmp_path):
        """Test that finalize_checkpoint marks checkpoint as resume_safe."""
        monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
        monitor.set_session("test-session", "query", "standard")

        checkpoint_id = monitor.emit_checkpoint(
            phase="strategy",
            operation="execute",
            input_ref={"query": "test query"},
        )

        # Initially not resume_safe
        cp = monitor.get_checkpoint_by_id(checkpoint_id)
        assert cp["resume_safe"] is False

        # Finalize with output
        monitor.finalize_checkpoint(
            checkpoint_id,
            output_ref={"strategy": "comprehensive"},
            replayable=True,
        )

        # Now should be resume_safe
        cp = monitor.get_checkpoint_by_id(checkpoint_id)
        assert cp["resume_safe"] is True
        assert cp["output_ref"] == {"strategy": "comprehensive"}

    def test_get_latest_resume_safe_checkpoint(self, tmp_path):
        """Test getting the latest resume-safe checkpoint."""
        monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
        monitor.set_session("test-session", "query", "standard")

        # Create and finalize first checkpoint
        cp1_id = monitor.emit_checkpoint(
            phase="session_start",
            operation="initialize",
            input_ref={"query": "test"},
        )
        monitor.finalize_checkpoint(cp1_id, output_ref={"status": "started"}, replayable=True)

        # Create and finalize second checkpoint
        cp2_id = monitor.emit_checkpoint(
            phase="strategy",
            operation="execute",
            input_ref={"query": "test"},
        )
        monitor.finalize_checkpoint(cp2_id, output_ref={"strategy": "comprehensive"}, replayable=True)

        # Get latest resume-safe
        latest = monitor.get_latest_resume_safe_checkpoint()
        assert latest is not None
        assert latest["checkpoint_id"] == cp2_id

    def test_get_checkpoints_by_phase(self, tmp_path):
        """Test filtering checkpoints by phase."""
        monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
        monitor.set_session("test-session", "query", "standard")

        monitor.emit_checkpoint(phase="strategy", operation="execute", input_ref={})
        monitor.emit_checkpoint(phase="source_collection", operation="execute", input_ref={})
        monitor.emit_checkpoint(phase="strategy", operation="iterate", input_ref={})

        strategy_cps = monitor.get_checkpoints_by_phase("strategy")
        assert len(strategy_cps) == 2

        collection_cps = monitor.get_checkpoints_by_phase("source_collection")
        assert len(collection_cps) == 1

    def test_checkpoint_not_replayable_on_failure(self, tmp_path):
        """Test that checkpoints can be marked not replayable."""
        monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
        monitor.set_session("test-session", "query", "standard")

        checkpoint_id = monitor.emit_checkpoint(
            phase="strategy",
            operation="execute",
            input_ref={"query": "test"},
        )

        # Finalize as not replayable
        monitor.finalize_checkpoint(
            checkpoint_id,
            output_ref=None,
            replayable=False,
            replayable_reason="External API call with non-deterministic result",
        )

        cp = monitor.get_checkpoint_by_id(checkpoint_id)
        assert cp["replayable"] is False
        assert "non-deterministic" in cp["replayable_reason"]

    def test_checkpoint_includes_telemetry_event(self, tmp_path):
        """Test that checkpoint creation emits telemetry event."""
        monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
        monitor.set_session("test-session", "query", "standard")

        checkpoint_id = monitor.emit_checkpoint(
            phase="strategy",
            operation="execute",
            input_ref={"query": "test"},
        )

        # Find checkpoint.created event
        checkpoint_events = [
            e for e in monitor._telemetry_events
            if e["event_type"] == "checkpoint.created"
        ]
        assert len(checkpoint_events) == 1

        event = checkpoint_events[0]
        assert event["metadata"]["checkpoint_id"] == checkpoint_id
        assert event["metadata"]["phase"] == "strategy"
        assert event["status"] == "committed"  # Successfully persisted


class TestPhaseRunnerCheckpoints:
    """Tests for PhaseRunner checkpoint integration."""

    @pytest.mark.asyncio
    async def test_run_phase_creates_checkpoint_with_input_ref(self, tmp_path):
        """PhaseRunner should create checkpoint with input_ref."""
        from cc_deep_research.orchestration.phases import PhaseRunner

        monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
        runner = PhaseRunner(monitor=monitor)
        monitor.set_session("test-session", "query", "standard")

        async def operation():
            return {"result": "success"}

        await runner.run_phase(
            phase_hook=None,
            phase_key="strategy",
            description="Analyzing strategy",
            operation=operation,
            input_ref={"query": "test query", "depth": "deep"},
            output_transformer=lambda r: {"result_type": type(r).__name__},
        )

        # Check that checkpoint was created
        checkpoints = monitor.get_all_checkpoints()
        assert len(checkpoints) >= 1

        # Find the strategy checkpoint
        strategy_cp = next((cp for cp in checkpoints if cp["phase"] == "strategy"), None)
        assert strategy_cp is not None
        assert strategy_cp["input_ref"] == {"query": "test query", "depth": "deep"}
        assert strategy_cp["output_ref"] == {"result_type": "dict"}
        assert strategy_cp["resume_safe"] is True

    @pytest.mark.asyncio
    async def test_run_phase_finalizes_checkpoint_on_success(self, tmp_path):
        """PhaseRunner should finalize checkpoint on successful completion."""
        from cc_deep_research.orchestration.phases import PhaseRunner

        monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
        runner = PhaseRunner(monitor=monitor)
        monitor.set_session("test-session", "query", "standard")

        async def operation():
            return {"sources": 10}

        await runner.run_phase(
            phase_hook=None,
            phase_key="source_collection",
            description="Collecting sources",
            operation=operation,
            input_ref={"query": "test"},
            output_transformer=lambda r: {"source_count": r["sources"]},
        )

        # Check that checkpoint is finalized and resume-safe
        checkpoints = monitor.get_checkpoints_by_phase("source_collection")
        assert len(checkpoints) == 1
        assert checkpoints[0]["resume_safe"] is True
        assert checkpoints[0]["output_ref"] == {"source_count": 10}

    @pytest.mark.asyncio
    async def test_run_phase_marks_checkpoint_not_replayable_on_failure(self, tmp_path):
        """PhaseRunner should mark checkpoint not replayable on failure."""
        from cc_deep_research.orchestration.phases import PhaseRunner

        monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
        runner = PhaseRunner(monitor=monitor)
        monitor.set_session("test-session", "query", "standard")

        async def failing_operation():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await runner.run_phase(
                phase_hook=None,
                phase_key="analysis",
                description="Analyzing",
                operation=failing_operation,
                input_ref={"query": "test"},
            )

        # Check that checkpoint is not replayable
        checkpoints = monitor.get_checkpoints_by_phase("analysis")
        assert len(checkpoints) == 1
        assert checkpoints[0]["replayable"] is False
        assert "ValueError" in checkpoints[0]["replayable_reason"]
