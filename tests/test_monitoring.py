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
