"""Tests for ResearchMonitor."""

import re
from unittest.mock import patch

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
