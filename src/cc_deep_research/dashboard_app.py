"""Streamlit dashboard for historical and live telemetry monitoring."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, cast

from cc_deep_research.telemetry import (
    get_default_dashboard_db_path,
    get_default_telemetry_dir,
    ingest_telemetry_to_duckdb,
    query_dashboard_data,
    query_live_session_detail,
    query_live_sessions,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse dashboard script arguments passed after `streamlit run ... --`."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--telemetry-dir", type=Path, default=None)
    parser.add_argument("--refresh-seconds", type=int, default=5)
    parser.add_argument("--tail-limit", type=int, default=200)
    args, _unknown = parser.parse_known_args(argv)
    return args


def _render_refreshable_fragment(
    render_content: Callable[[], None],
    *,
    run_every: int | None,
) -> None:
    """Render dashboard content inside a refreshable Streamlit fragment."""
    import streamlit as st

    @st.fragment(run_every=run_every)
    def _fragment() -> None:
        render_content()

    _fragment()


def _flatten_tree_rows(
    events: list[dict[str, Any]],
    *,
    depth: int = 0,
) -> list[dict[str, Any]]:
    """Flatten a hierarchical event tree into rows with indentation metadata."""
    rows: list[dict[str, Any]] = []
    for event in events:
        rows.append(
            {
                "depth": depth,
                "label": ("  " * depth) + f"{event['event_type']} :: {event['name']}",
                "status": event.get("status"),
                "agent_id": event.get("agent_id"),
                "sequence_number": event.get("sequence_number"),
                "timestamp": event.get("timestamp"),
            }
        )
        rows.extend(_flatten_tree_rows(event.get("children", []), depth=depth + 1))
    return rows


def _build_session_overview_rows(
    live_sessions: list[dict[str, Any]],
    historical_sessions: list[tuple[Any, ...]],
) -> list[dict[str, Any]]:
    """Merge live and historical sessions for dashboard selection."""
    rows_by_id: dict[str, dict[str, Any]] = {}

    for session in historical_sessions:
        session_id = str(session[0])
        rows_by_id[session_id] = {
            "session_id": session_id,
            "created_at": session[1],
            "total_time_ms": session[2],
            "total_sources": session[3],
            "instances_spawned": session[4],
            "search_queries": session[5],
            "tool_calls": session[6],
            "llm_total_tokens": session[7],
            "status": session[8],
            "active": False,
            "event_count": None,
            "last_event_at": None,
        }

    for session in live_sessions:
        row = rows_by_id.get(session["session_id"], {})
        row.update(
            {
                "session_id": session["session_id"],
                "created_at": session.get("created_at") or row.get("created_at"),
                "total_time_ms": session.get("total_time_ms", row.get("total_time_ms")),
                "total_sources": session.get("total_sources", row.get("total_sources", 0)),
                "status": session.get("status", row.get("status", "unknown")),
                "active": bool(session.get("active")),
                "event_count": session.get("event_count"),
                "last_event_at": session.get("last_event_at"),
            }
        )
        rows_by_id[session["session_id"]] = row

    rows = list(rows_by_id.values())
    rows.sort(
        key=lambda row: (
            0 if row.get("active") else 1,
            row.get("last_event_at") or row.get("created_at") or "",
        )
    )
    return rows


def _format_session_label(session_id: str, overview_rows: list[dict[str, Any]]) -> str:
    """Format a session label for select boxes."""
    row = next(
        (candidate for candidate in overview_rows if candidate["session_id"] == session_id),
        None,
    )
    if row is None:
        return session_id
    return f"{session_id} {'(active)' if row.get('active') else ''}".strip()


def _sync_selectbox_state(key: str, options: list[str]) -> None:
    """Reset selectbox state when the previously selected value is unavailable."""
    import streamlit as st

    if st.session_state.get(key) not in options:
        st.session_state[key] = options[0]


def _derive_event_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute filterable event rows for tabular display."""
    rows: list[dict[str, Any]] = []
    for event in events:
        metadata = event.get("metadata", {})
        rows.append(
            {
                "sequence_number": event.get("sequence_number"),
                "timestamp": event.get("timestamp"),
                "event_type": event.get("event_type"),
                "category": event.get("category"),
                "name": event.get("name"),
                "status": event.get("status"),
                "agent_id": event.get("agent_id"),
                "duration_ms": event.get("duration_ms"),
                "phase": event.get("name") if event.get("category") == "phase" else "",
                "tool": event.get("name") if event.get("category") == "tool" else "",
                "provider": event.get("name") if event.get("event_type") == "search.query" else "",
                "model": metadata.get("model", ""),
                "metadata": metadata,
            }
        )
    return rows


def _render_subprocess_detail(subprocesses: list[dict[str, Any]]) -> None:
    """Render the Claude subprocess inspection pane."""
    import streamlit as st

    st.subheader("Claude Subprocess Detail")
    if not subprocesses:
        st.info("No Claude subprocess activity recorded for this session.")
        return

    options = {
        f"{item.get('operation') or 'unknown'} | {item.get('status')} | {item.get('started_at') or 'n/a'}": item
        for item in subprocesses
    }
    selected_label = st.selectbox("Subprocess", list(options.keys()))
    selected = options[selected_label]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Operation", selected.get("operation") or "unknown")
    c2.metric("Status", selected.get("status") or "unknown")
    c3.metric("Exit Code", selected.get("exit_code") if selected.get("exit_code") is not None else "n/a")
    c4.metric("Duration (s)", f"{(selected.get('duration_ms') or 0) / 1000:.1f}")
    st.caption(
        f"Executable: {selected.get('executable') or 'unknown'} | "
        f"Model: {selected.get('model') or 'unknown'}"
    )

    stdout_text = "".join(chunk.get("content", "") for chunk in selected["stdout_chunks"])
    stderr_text = "".join(chunk.get("content", "") for chunk in selected["stderr_chunks"])

    if selected.get("dropped_stdout_chunks"):
        st.warning(f"Showing the latest {len(selected['stdout_chunks'])} stdout chunks.")
    if selected.get("dropped_stderr_chunks"):
        st.warning(f"Showing the latest {len(selected['stderr_chunks'])} stderr chunks.")

    left, right = st.columns(2)
    left.markdown("**STDOUT**")
    left.code(stdout_text or "(no stdout)")
    right.markdown("**STDERR**")
    right.code(stderr_text or "(no stderr)")


def _render_llm_route_analytics(analytics: dict[str, Any]) -> None:
    """Render the LLM route analytics pane."""
    import streamlit as st

    st.subheader("LLM Route Analytics")
    if not analytics or analytics.get("total_requests", 0) == 0:
        st.info("No LLM route activity recorded for this session.")
        return

    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Requests", analytics.get("total_requests", 0))
    c2.metric("Fallback Events", analytics.get("fallback_count", 0))
    c3.metric("Transports Used", len(analytics.get("transport_summary", {})))
    c4.metric("Agents", len(analytics.get("agent_summary", {})))

    # Transport summary
    transport_summary = analytics.get("transport_summary", {})
    if transport_summary:
        st.markdown("**Transport Summary**")
        transport_rows = []
        for transport, stats in transport_summary.items():
            transport_rows.append(
                {
                    "transport": transport,
                    "requests": stats.get("requests", 0),
                    "tokens": stats.get("tokens", 0),
                    "errors": stats.get("errors", 0),
                    "avg_latency_ms": stats.get("avg_latency_ms", 0),
                }
            )
        if transport_rows:
            import pandas as pd

            st.dataframe(pd.DataFrame(transport_rows), width="stretch", height=120)

    # Provider summary
    provider_summary = analytics.get("provider_summary", {})
    if provider_summary:
        st.markdown("**Provider Summary**")
        provider_rows = []
        for provider, stats in provider_summary.items():
            provider_rows.append(
                {
                    "provider": provider,
                    "requests": stats.get("requests", 0),
                    "tokens": stats.get("tokens", 0),
                    "errors": stats.get("errors", 0),
                }
            )
        if provider_rows:
            import pandas as pd

            st.dataframe(pd.DataFrame(provider_rows), width="stretch", height=120)

    # Agent summary
    agent_summary = analytics.get("agent_summary", {})
    if agent_summary:
        st.markdown("**Agent Route Usage**")
        agent_rows = []
        for agent_id, stats in agent_summary.items():
            agent_rows.append(
                {
                    "agent_id": agent_id,
                    "requests": stats.get("requests", 0),
                    "tokens": stats.get("tokens", 0),
                    "errors": stats.get("errors", 0),
                    "transports": ", ".join(stats.get("transports", [])),
                    "providers": ", ".join(stats.get("providers", [])),
                }
            )
        if agent_rows:
            import pandas as pd

            st.dataframe(pd.DataFrame(agent_rows), width="stretch", height=150)

    # Planned routes
    planned_routes = analytics.get("planned_routes", {})
    if planned_routes:
        st.markdown("**Planned Routes**")
        planned_rows = []
        for agent_id, route in planned_routes.items():
            planned_rows.append(
                {
                    "agent_id": agent_id,
                    "transport": route.get("transport", "unknown"),
                    "provider": route.get("provider", "unknown"),
                    "model": route.get("model", "unknown"),
                    "source": route.get("source", "unknown"),
                }
            )
        if planned_rows:
            import pandas as pd

            st.dataframe(pd.DataFrame(planned_rows), width="stretch", height=100)

    # Fallback events
    fallbacks = analytics.get("route_fallbacks", [])
    if fallbacks:
        with st.expander(f"Fallback Events ({len(fallbacks)})", expanded=False):
            for fb in fallbacks:
                metadata = fb.get("metadata", {})
                st.caption(
                    f"Agent: {fb.get('agent_id', 'unknown')} | "
                    f"{metadata.get('original_transport', 'unknown')} -> "
                    f"{metadata.get('fallback_transport', 'unknown')} | "
                    f"Reason: {metadata.get('reason', 'unknown')}"
                )


def run_dashboard(
    db_path: Path | None = None,
    telemetry_dir: Path | None = None,
    refresh_seconds: int = 5,
    tail_limit: int = 200,
) -> None:
    """Render the dashboard UI."""
    try:
        import pandas as pd
        import streamlit as st
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "Dashboard UI requires optional dashboard dependencies. "
            "Install with `pip install \"cc-deep-research[dashboard]\"`."
        ) from exc

    dashboard_db = db_path or get_default_dashboard_db_path()
    source_dir = telemetry_dir or get_default_telemetry_dir()

    st.set_page_config(page_title="CC Deep Research Monitoring", layout="wide")
    st.title("CC Deep Research Monitoring Dashboard")

    with st.sidebar:
        st.header("Live Controls")
        auto_refresh = st.checkbox("Auto refresh", value=refresh_seconds > 0)
        refresh_options = [0, 2, 5, 10, 30]
        refresh_index = (
            refresh_options.index(refresh_seconds)
            if refresh_seconds in refresh_options
            else refresh_options.index(5)
        )
        refresh_interval = st.selectbox(
            "Refresh interval (s)",
            refresh_options,
            index=refresh_index,
        )
        if not auto_refresh:
            refresh_interval = 0
        if st.button("Refresh Now"):
            st.rerun()
        active_only = st.checkbox("Active sessions only", value=False)

    initial_live_sessions = query_live_sessions(base_dir=source_dir)
    initial_ingest_result = ingest_telemetry_to_duckdb(base_dir=source_dir, db_path=dashboard_db)
    initial_historical = query_dashboard_data(db_path=dashboard_db)
    overview_rows = _build_session_overview_rows(initial_live_sessions, initial_historical["sessions"])
    if active_only:
        overview_rows = [row for row in overview_rows if row.get("active")]

    if not overview_rows:
        st.caption(
            f"Telemetry source: {source_dir} | DuckDB: {dashboard_db} | "
            f"Live sessions: {len(initial_live_sessions)} | "
            f"Ingested sessions: {initial_ingest_result['sessions']}, events: {initial_ingest_result['events']}"
        )
        st.info("No telemetry sessions available yet.")
        return

    overview_df = pd.DataFrame(overview_rows)
    st.subheader("Session Overview")
    st.dataframe(overview_df, width="stretch", height=220)

    session_ids = [row["session_id"] for row in overview_rows]
    current_session_id = st.session_state.get("dashboard_selected_session_id")
    if current_session_id not in session_ids:
        st.session_state["dashboard_selected_session_id"] = session_ids[0]

    selected_session_id = st.selectbox(
        "Session",
        session_ids,
        format_func=lambda session_id: _format_session_label(session_id, overview_rows),
        key="dashboard_selected_session_id",
    )

    initial_detail = query_live_session_detail(
        selected_session_id,
        base_dir=source_dir,
        tail_limit=tail_limit,
        subprocess_chunk_limit=tail_limit,
    )
    initial_events = initial_detail["events"] if initial_detail["session"] else []
    initial_event_rows = _derive_event_rows(initial_events)

    phase_options = ["All"] + sorted({row["phase"] for row in initial_event_rows if row["phase"]})
    agent_options = ["All"] + sorted({row["agent_id"] for row in initial_event_rows if row["agent_id"]})
    status_options = ["All"] + sorted({row["status"] for row in initial_event_rows if row["status"]})
    tool_options = ["All"] + sorted({row["tool"] for row in initial_event_rows if row["tool"]})
    provider_options = ["All"] + sorted({row["provider"] for row in initial_event_rows if row["provider"]})
    event_type_options = ["All"] + sorted(
        {row["event_type"] for row in initial_event_rows if row["event_type"]}
    )

    _sync_selectbox_state("dashboard_phase_filter", phase_options)
    _sync_selectbox_state("dashboard_agent_filter", agent_options)
    _sync_selectbox_state("dashboard_status_filter", status_options)
    _sync_selectbox_state("dashboard_tool_filter", tool_options)
    _sync_selectbox_state("dashboard_provider_filter", provider_options)
    _sync_selectbox_state("dashboard_event_type_filter", event_type_options)

    filter_col1, filter_col2, filter_col3 = st.columns(3)
    filter_col4, filter_col5, filter_col6 = st.columns(3)
    filter_col1.selectbox(
        "Phase Filter",
        phase_options,
        key="dashboard_phase_filter",
    )
    filter_col2.selectbox(
        "Agent Filter",
        agent_options,
        key="dashboard_agent_filter",
    )
    filter_col3.selectbox(
        "Status Filter",
        status_options,
        key="dashboard_status_filter",
    )
    filter_col4.selectbox(
        "Tool Filter",
        tool_options,
        key="dashboard_tool_filter",
    )
    filter_col5.selectbox(
        "Provider Filter",
        provider_options,
        key="dashboard_provider_filter",
    )
    filter_col6.selectbox(
        "Event Type Filter",
        event_type_options,
        key="dashboard_event_type_filter",
    )

    live_content = st.empty()

    def render_dashboard_content() -> None:
        live_sessions = query_live_sessions(base_dir=source_dir)
        ingest_result = ingest_telemetry_to_duckdb(base_dir=source_dir, db_path=dashboard_db)
        historical = query_dashboard_data(db_path=dashboard_db)
        fresh_overview_rows = _build_session_overview_rows(live_sessions, historical["sessions"])
        if active_only:
            fresh_overview_rows = [row for row in fresh_overview_rows if row.get("active")]

        selected_session_id = st.session_state["dashboard_selected_session_id"]
        detail = query_live_session_detail(
            selected_session_id,
            base_dir=source_dir,
            tail_limit=tail_limit,
            subprocess_chunk_limit=tail_limit,
        )
        session = detail["session"]
        tail_rows = _derive_event_rows(detail["event_tail"]) if session else []

        phase_filter = st.session_state.get("dashboard_phase_filter", "All")
        agent_filter = st.session_state.get("dashboard_agent_filter", "All")
        status_filter = st.session_state.get("dashboard_status_filter", "All")
        tool_filter = st.session_state.get("dashboard_tool_filter", "All")
        provider_filter = st.session_state.get("dashboard_provider_filter", "All")
        event_type_filter = st.session_state.get("dashboard_event_type_filter", "All")

        def include_row(row: dict[str, Any]) -> bool:
            if phase_filter != "All" and row["phase"] != phase_filter:
                return False
            if agent_filter != "All" and row["agent_id"] != agent_filter:
                return False
            if status_filter != "All" and row["status"] != status_filter:
                return False
            if tool_filter != "All" and row["tool"] != tool_filter:
                return False
            if provider_filter != "All" and row["provider"] != provider_filter:
                return False
            return cast(bool, event_type_filter == "All" or row["event_type"] == event_type_filter)

        filtered_tail_rows = [row for row in tail_rows if include_row(row)]
        tail_df = pd.DataFrame(filtered_tail_rows)

        live_content.empty()
        with live_content.container():
            st.caption(
                f"Telemetry source: {source_dir} | DuckDB: {dashboard_db} | "
                f"Live sessions: {len(live_sessions)} | "
                f"Ingested sessions: {ingest_result['sessions']}, events: {ingest_result['events']}"
            )

            kpis = historical["kpis"]
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("Historical Sessions", int(kpis.get("sessions", 0)))
            k2.metric("Active Sessions", sum(1 for candidate in live_sessions if candidate.get("active")))
            k3.metric("Avg Time (s)", f"{kpis.get('avg_time_ms', 0) / 1000:.1f}")
            k4.metric("Avg Searches", f"{kpis.get('avg_searches', 0):.1f}")
            k5.metric("Avg Tool Calls", f"{kpis.get('avg_tool_calls', 0):.1f}")

            if session is None:
                st.warning("Selected session could not be loaded from telemetry files.")
            else:
                st.subheader("Live Operator View")
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("Session Status", session.get("status", "unknown"))
                s2.metric("Current Phase", detail.get("active_phase") or "idle")
                s3.metric("Events", int(session.get("event_count") or 0))
                s4.metric("Sources", int(session.get("total_sources") or 0))
                st.caption(
                    f"Created: {session.get('created_at') or 'n/a'} | "
                    f"Last event: {session.get('last_event_at') or 'n/a'}"
                )

                left, right = st.columns([1.2, 1])
                left.subheader("Recent Event Tail")
                if tail_df.empty:
                    left.info("No recent events matched the current filters.")
                else:
                    left.dataframe(
                        tail_df[
                            [
                                "sequence_number",
                                "timestamp",
                                "event_type",
                                "category",
                                "name",
                                "status",
                                "agent_id",
                                "duration_ms",
                            ]
                        ],
                        width="stretch",
                        height=360,
                    )

                right.subheader("Agent Timeline")
                agent_df = pd.DataFrame(detail["agent_timeline"])
                if agent_df.empty:
                    right.info("No agent activity recorded.")
                else:
                    right.dataframe(
                        agent_df[
                            [
                                "sequence_number",
                                "timestamp",
                                "event_type",
                                "agent_id",
                                "status",
                                "duration_ms",
                            ]
                        ],
                        width="stretch",
                        height=360,
                    )

                st.subheader("Event Tree")
                tree_rows = _flatten_tree_rows(detail["event_tree"]["root_events"])
                tree_df = pd.DataFrame(tree_rows)
                if tree_df.empty:
                    st.info("No hierarchical events available for this session.")
                else:
                    st.dataframe(tree_df, width="stretch", height=240)

            if historical["sessions"]:
                st.subheader("Historical Trends")
                trend_df = pd.DataFrame(
                    historical["sessions"],
                    columns=[
                        "session_id",
                        "created_at",
                        "total_time_ms",
                        "total_sources",
                        "instances_spawned",
                        "search_queries",
                        "tool_calls",
                        "llm_total_tokens",
                        "status",
                    ],
                )
                if not trend_df.empty:
                    st.line_chart(
                        trend_df.set_index("session_id")[
                            ["total_time_ms", "search_queries", "tool_calls", "llm_total_tokens"]
                        ]
                    )

        st.session_state["dashboard_latest_detail"] = detail
        st.session_state["dashboard_latest_overview_rows"] = fresh_overview_rows

    _render_refreshable_fragment(
        render_dashboard_content,
        run_every=refresh_interval if auto_refresh and refresh_interval > 0 else None,
    )

    latest_detail = st.session_state.get("dashboard_latest_detail", initial_detail)
    latest_session = latest_detail["session"]
    if latest_session is not None:
        _render_subprocess_detail(latest_detail["subprocess_streams"])
        _render_llm_route_analytics(latest_detail.get("llm_route_analytics", {}))
        export_payload = {
            "session": latest_session,
            "summary": latest_detail["summary"],
            "event_tail": latest_detail["event_tail"],
            "active_phase": latest_detail["active_phase"],
            "subprocess_streams": latest_detail["subprocess_streams"],
            "llm_route_analytics": latest_detail.get("llm_route_analytics", {}),
        }
        st.download_button(
            "Download Live Session JSON",
            data=json.dumps(export_payload, ensure_ascii=True, indent=2, default=str),
            file_name=f"{selected_session_id}_live_monitoring.json",
            mime="application/json",
        )


def main() -> None:
    """Entry point used by Streamlit."""
    args = _parse_args(sys.argv[1:])
    run_dashboard(
        db_path=args.db_path,
        telemetry_dir=args.telemetry_dir,
        refresh_seconds=args.refresh_seconds,
        tail_limit=args.tail_limit,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
