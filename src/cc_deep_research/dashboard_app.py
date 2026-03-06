"""Streamlit dashboard for telemetry analytics."""

from __future__ import annotations

import json
from pathlib import Path

from cc_deep_research.telemetry import (
    get_default_dashboard_db_path,
    get_default_telemetry_dir,
    ingest_telemetry_to_duckdb,
    query_dashboard_data,
    query_session_detail,
)


def run_dashboard(db_path: Path | None = None, telemetry_dir: Path | None = None) -> None:
    """Render dashboard UI in Streamlit."""
    try:
        import pandas as pd
        import streamlit as st
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "streamlit and pandas are required for dashboard. "
            "Install with `pip install streamlit pandas duckdb`."
        ) from exc

    dashboard_db = db_path or get_default_dashboard_db_path()
    source_dir = telemetry_dir or get_default_telemetry_dir()

    st.set_page_config(page_title="CC Deep Research Monitoring", layout="wide")
    st.title("CC Deep Research Monitoring Dashboard")

    if st.button("Refresh Data"):
        ingest_telemetry_to_duckdb(base_dir=source_dir, db_path=dashboard_db)

    ingest_result = ingest_telemetry_to_duckdb(base_dir=source_dir, db_path=dashboard_db)
    st.caption(
        f"Telemetry source: {source_dir} | DuckDB: {dashboard_db} | "
        f"Ingested sessions: {ingest_result['sessions']}, events: {ingest_result['events']}"
    )

    data = query_dashboard_data(db_path=dashboard_db)
    kpis = data["kpis"]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Sessions", int(kpis.get("sessions", 0)))
    c2.metric("Avg Time (s)", f"{kpis.get('avg_time_ms', 0) / 1000:.1f}")
    c3.metric("Avg Tokens", f"{kpis.get('avg_tokens', 0):.0f}")
    c4.metric("Avg Searches", f"{kpis.get('avg_searches', 0):.1f}")
    c5.metric("Avg Tool Calls", f"{kpis.get('avg_tool_calls', 0):.1f}")

    sessions_df = pd.DataFrame(
        data["sessions"],
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

    if not sessions_df.empty:
        st.subheader("Session Overview")
        st.dataframe(sessions_df, use_container_width=True)

        st.subheader("Time and Token Trends")
        chart_df = sessions_df[
            ["session_id", "total_time_ms", "llm_total_tokens", "search_queries", "tool_calls"]
        ].copy()
        chart_df = chart_df.set_index("session_id")
        st.line_chart(chart_df)

    events_df = pd.DataFrame(
        data["events"],
        columns=[
            "session_id",
            "timestamp",
            "event_type",
            "category",
            "name",
            "status",
            "duration_ms",
            "agent_id",
            "metadata_json",
        ],
    )

    st.subheader("Recent Events")
    if not events_df.empty:
        events_view = events_df.copy()
        events_view["metadata"] = events_view["metadata_json"].map(
            lambda x: json.loads(x) if isinstance(x, str) and x else {}
        )
        st.dataframe(
            events_view[
                [
                    "timestamp",
                    "session_id",
                    "event_type",
                    "category",
                    "name",
                    "status",
                    "duration_ms",
                    "agent_id",
                    "metadata",
                ]
            ],
            use_container_width=True,
            height=450,
        )

    agent_df = pd.DataFrame(
        data["agent_timeline"],
        columns=[
            "session_id",
            "agent_id",
            "event_type",
            "name",
            "status",
            "duration_ms",
            "timestamp",
        ],
    )
    st.subheader("Agent Timeline")
    if not agent_df.empty:
        st.dataframe(agent_df, use_container_width=True)

    st.subheader("Session Drill-down")
    if sessions_df.empty:
        st.info("No sessions available yet.")
        return

    session_options = sessions_df["session_id"].tolist()
    selected_session = st.selectbox("Select session", session_options, index=0)
    detail = query_session_detail(selected_session, db_path=dashboard_db)
    export_payload: dict[str, object] = {"session_id": selected_session}

    detail_session = detail["session"]
    if detail_session is not None:
        d1, d2, d3, d4, d5 = st.columns(5)
        d1.metric("Duration (s)", f"{(detail_session[3] or 0) / 1000:.1f}")
        d2.metric("Sources", int(detail_session[4] or 0))
        d3.metric("Spawned", int(detail_session[5] or 0))
        d4.metric("Searches", int(detail_session[6] or 0))
        d5.metric("Tools", int(detail_session[7] or 0))
        st.caption(f"Status: {detail_session[2]} | Tokens: {int(detail_session[10] or 0)}")
        export_payload["session_summary"] = {
            "session_id": detail_session[0],
            "created_at": detail_session[1],
            "status": detail_session[2],
            "total_time_ms": detail_session[3],
            "total_sources": detail_session[4],
            "instances_spawned": detail_session[5],
            "search_queries": detail_session[6],
            "tool_calls": detail_session[7],
            "llm_prompt_tokens": detail_session[8],
            "llm_completion_tokens": detail_session[9],
            "llm_total_tokens": detail_session[10],
            "providers_json": detail_session[11],
        }

    phase_df = pd.DataFrame(
        detail["phase_durations"],
        columns=["phase", "avg_duration_ms", "samples"],
    )
    if not phase_df.empty:
        st.markdown("**Phase Duration (ms)**")
        st.bar_chart(phase_df.set_index("phase")["avg_duration_ms"])
        export_payload["phase_durations"] = phase_df.to_dict(orient="records")

    reasoning_df = pd.DataFrame(
        detail["reasoning_events"],
        columns=["timestamp", "stage", "metadata_json"],
    )
    if not reasoning_df.empty:
        reasoning_df["summary"] = reasoning_df["metadata_json"].map(
            lambda x: (json.loads(x) or {}).get("summary", "") if isinstance(x, str) and x else ""
        )
        st.markdown("**Reasoning Summaries**")
        st.dataframe(
            reasoning_df[["timestamp", "stage", "summary"]],
            use_container_width=True,
        )
        export_payload["reasoning_events"] = reasoning_df[
            ["timestamp", "stage", "summary"]
        ].to_dict(orient="records")

    tool_df = pd.DataFrame(
        detail["tool_calls"],
        columns=[
            "timestamp",
            "tool_name",
            "status",
            "duration_ms",
            "agent_id",
            "metadata_json",
        ],
    )
    if not tool_df.empty:
        st.markdown("**Tool Calls**")
        st.dataframe(
            tool_df[
                [
                    "timestamp",
                    "tool_name",
                    "status",
                    "duration_ms",
                    "agent_id",
                ]
            ],
            use_container_width=True,
            height=250,
        )
        export_payload["tool_calls"] = tool_df.to_dict(orient="records")

    llm_df = pd.DataFrame(
        detail["llm_usage"],
        columns=["timestamp", "operation", "duration_ms", "metadata_json"],
    )
    if not llm_df.empty:
        llm_df["prompt_tokens"] = llm_df["metadata_json"].map(
            lambda x: (
                int((json.loads(x) or {}).get("prompt_tokens", 0))
                if isinstance(x, str) and x
                else 0
            )
        )
        llm_df["completion_tokens"] = llm_df["metadata_json"].map(
            lambda x: (
                int((json.loads(x) or {}).get("completion_tokens", 0))
                if isinstance(x, str) and x
                else 0
            )
        )
        llm_df["total_tokens"] = llm_df["prompt_tokens"] + llm_df["completion_tokens"]
        st.markdown("**LLM Usage**")
        st.dataframe(
            llm_df[
                [
                    "timestamp",
                    "operation",
                    "duration_ms",
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                ]
            ],
            use_container_width=True,
            height=220,
        )
        export_payload["llm_usage"] = llm_df.to_dict(orient="records")

    agent_detail_df = pd.DataFrame(
        detail["agent_events"],
        columns=[
            "timestamp",
            "event_type",
            "agent_id",
            "name",
            "status",
            "duration_ms",
            "metadata_json",
        ],
    )
    if not agent_detail_df.empty:
        st.markdown("**Agent Event Timeline**")
        st.dataframe(
            agent_detail_df[
                [
                    "timestamp",
                    "event_type",
                    "agent_id",
                    "status",
                    "duration_ms",
                ]
            ],
            use_container_width=True,
            height=250,
        )
        export_payload["agent_events"] = agent_detail_df.to_dict(orient="records")

    events_df_for_export = pd.DataFrame(
        detail["events"],
        columns=[
            "timestamp",
            "event_type",
            "category",
            "name",
            "status",
            "duration_ms",
            "agent_id",
            "metadata_json",
        ],
    )
    if not events_df_for_export.empty:
        export_payload["events"] = events_df_for_export.to_dict(orient="records")

    st.markdown("**Export Selected Session**")
    col_json, col_csv = st.columns(2)
    col_json.download_button(
        "Download JSON",
        data=json.dumps(export_payload, ensure_ascii=True, indent=2, default=str),
        file_name=f"{selected_session}_telemetry.json",
        mime="application/json",
    )
    col_csv.download_button(
        "Download Events CSV",
        data=events_df_for_export.to_csv(index=False) if not events_df_for_export.empty else "",
        file_name=f"{selected_session}_events.csv",
        mime="text/csv",
    )


if __name__ == "__main__":  # pragma: no cover
    run_dashboard()
