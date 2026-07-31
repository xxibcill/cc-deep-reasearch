"""Operator runbooks for common deployment, dashboard, storage, and provider incidents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RunbookStep:
    """One step in a runbook procedure."""

    step: int
    description: str
    command: str | None = None
    expected_output: str | None = None
    escalation_criteria: str | None = None


@dataclass
class Runbook:
    """An operator runbook for a specific incident type."""

    runbook_id: str
    title: str
    summary: str
    symptoms: list[str]
    steps: list[RunbookStep]
    related_checks: list[str] | None = None
    related_runbooks: list[str] | None = None


# ---------------------------------------------------------------------------
# Runbook Definitions
# ---------------------------------------------------------------------------

RUNBOOKS: dict[str, Runbook] = {}


def _register_runbook(rb: Runbook) -> None:
    RUNBOOKS[rb.runbook_id] = rb


# --- Dashboard Unavailable ---
_register_runbook(Runbook(
    runbook_id="dashboard_unavailable",
    title="Dashboard Unavailable",
    summary="The dashboard UI is not loading or returning errors.",
    symptoms=[
        "Browser shows 'This site cannot be reached'",
        "Dashboard returns 502 Bad Gateway",
        "Frontend shows a blank page or error boundary",
    ],
    steps=[
        RunbookStep(1, "Check if backend is running", "curl -fsS http://localhost:8000/api/operations/service/status?service_name=dashboard", "Service status returned"),
        RunbookStep(2, "Check backend port availability", "lsof -i :8000", "Process listed on port 8000"),
        RunbookStep(3, "Check frontend port availability", "lsof -i :3000", "Node process on port 3000"),
        RunbookStep(4, "Verify dashboard build exists", "ls dashboard/.next", "Build directory exists"),
        RunbookStep(5, "Check Node.js version", "node --version", "v22+"),
        RunbookStep(6, "Restart services from the repository root", "./scripts/dashboard-dev", "Backend and frontend URLs printed"),
    ],
    related_checks=["backend_reachable", "port_8000", "port_3000"],
    related_runbooks=["backend_unavailable"],
))


# --- Backend Unavailable ---
_register_runbook(Runbook(
    runbook_id="backend_unavailable",
    title="Backend Unavailable",
    summary="The FastAPI backend is not responding.",
    symptoms=[
        "API requests return 'ECONNREFUSED'",
        "WebSocket connections fail",
        "Health check returns FAIL",
    ],
    steps=[
        RunbookStep(1, "Check port availability", "lsof -i :8000", None),
        RunbookStep(2, "Check Python process", "ps aux | grep web_server", None),
        RunbookStep(3, "Start backend in foreground to see errors", "uv run uvicorn cc_deep_research.web_server:create_app --factory --ws websockets-sansio --host 127.0.0.1 --port 8000", None),
        RunbookStep(4, "Verify config loads", "uv run python -c 'from cc_deep_research.config import load_config; print(\"OK\")'", "OK printed"),
        RunbookStep(5, "Check provider credentials", "curl -fsS http://localhost:8000/api/health", None),
        RunbookStep(6, "Check log files for errors", "tail -100 ~/.config/inqulume-studio/telemetry/*/events.jsonl 2>/dev/null | tail -50", None),
    ],
    related_checks=["backend_reachable", "provider_credentials"],
    related_runbooks=["dashboard_unavailable", "provider_credentials_missing"],
))


# --- WebSocket Failing ---
_register_runbook(Runbook(
    runbook_id="websocket_failing",
    title="WebSocket Failing",
    summary="Real-time updates are not arriving in the dashboard.",
    symptoms=[
        "Session list shows stale data",
        "No live event stream in session detail",
        "Console shows WebSocket connection errors",
    ],
    steps=[
        RunbookStep(1, "Verify backend is running", "lsof -i :8000", None),
        RunbookStep(2, "Test a session WebSocket endpoint manually", "npx wscat -c ws://localhost:8000/ws/session/<session-id>", "Connected"),
        RunbookStep(3, "Check browser console for CORS errors", None, "No CORS policy errors"),
        RunbookStep(4, "Verify no firewall is blocking WebSocket upgrade", "curl -v -N -H 'Connection: Upgrade' -H 'Upgrade: websocket' http://localhost:8000/ws", "101 Switching Protocols"),
        RunbookStep(5, "Restart the local stack from the repository root", "./scripts/dashboard-dev", None),
    ],
    related_checks=["websocket_route"],
    related_runbooks=["backend_unavailable"],
))


# --- Provider Credentials Missing ---
_register_runbook(Runbook(
    runbook_id="provider_credentials_missing",
    title="Provider Credentials Missing",
    summary="No API credentials are configured, causing research runs to fail.",
    symptoms=[
        "Health check shows FAIL for provider_credentials",
        "Research runs fail immediately with auth errors",
        "Tavily/OpenRouter/Anthropic keys not in config",
    ],
    steps=[
        RunbookStep(1, "Check current config", "uv run python -c 'from cc_deep_research.config import load_config; c=load_config(); print(c.tavily.api_keys)'", "List of keys"),
        RunbookStep(2, "Check environment variables", "env | grep API_KEY", "No output if not set"),
        RunbookStep(3, "Add Tavily key", "export TAVILY_API_KEYS='your-key-here'", None),
        RunbookStep(4, "Verify key is detected", "uv run python -c 'from cc_deep_research.config import load_config; print(load_config().tavily.api_keys)'", "Key appears"),
        RunbookStep(5, "Run health check to confirm", "curl -fsS http://localhost:8000/api/health", "Provider credentials PASS"),
        RunbookStep(6, "Launch a quick research run from the Research dashboard", None, "Session opens in the monitor"),
    ],
    related_checks=["provider_credentials"],
    related_runbooks=["dashboard_unavailable"],
))


# --- Telemetry Storage Slow ---
_register_runbook(Runbook(
    runbook_id="telemetry_storage_slow",
    title="Telemetry Storage Slow",
    summary="Telemetry events are slow to write or query.",
    symptoms=[
        "Dashboard analytics load slowly",
        "Session events page times out",
        "DuckDB queries take > 5 seconds",
    ],
    steps=[
        RunbookStep(1, "Check disk space", "df -h ~/.config/inqulume-studio/telemetry", "> 1GB free"),
        RunbookStep(2, "Check DuckDB size", "ls -lh ~/.config/inqulume-studio/telemetry/dashboard.db", "Size within limits"),
        RunbookStep(3, "Preview the retention policy", "curl -fsS -X POST 'http://localhost:8000/api/telemetry/retention/apply?mode=dry_run&max_age_days=30'", None),
        RunbookStep(4, "Apply retention after reviewing the preview", "curl -fsS -X POST 'http://localhost:8000/api/telemetry/retention/apply?mode=enforce&max_age_days=30'", None),
        RunbookStep(5, "Verify analytics query performance", "curl -fsS 'http://localhost:8000/api/analytics?days=7'", "Returns in < 5s"),
    ],
    related_checks=["telemetry_access", "duckdb"],
    related_runbooks=["backup_failed"],
))


# --- Backup Failed ---
_register_runbook(Runbook(
    runbook_id="backup_failed",
    title="Backup Failed",
    summary="Creating or restoring a backup failed.",
    symptoms=[
        "Backup command returns an error",
        "Backup manifest is corrupted",
        "Restore fails with 'invalid manifest'",
    ],
    steps=[
        RunbookStep(1, "Check disk space", "df -h ~/.config", "> 500MB free"),
        RunbookStep(2, "Verify backup permissions", "ls -la ~/.config/inqulume-studio/", "Directories are writable"),
        RunbookStep(3, "Validate manifest manually", "python3 -c 'import json; json.load(open(\"backup.manifest.json\"))'", "No JSON parse error"),
        RunbookStep(4, "Check for conflicting processes", "lsof ~/.config/inqulume-studio/*.json", "No lock on files"),
        RunbookStep(5, "Review the backup plan", "curl -fsS http://localhost:8000/api/operations/backup/plan", None),
        RunbookStep(6, "Create a backup to an explicit path", "curl -fsS -X POST 'http://localhost:8000/api/operations/backup/create?backup_path=./inqulume-backup.tar.gz'", None),
    ],
    related_checks=["data_paths"],
    related_runbooks=["upgrade_failed"],
))


# --- Upgrade Failed ---
_register_runbook(Runbook(
    runbook_id="upgrade_failed",
    title="Upgrade Failed",
    summary="An upgrade left the system in a broken state.",
    symptoms=[
        "Dashboard crashes on startup",
        "Health checks fail after upgrade",
        "Config fails to load",
    ],
    steps=[
        RunbookStep(1, "Check upgrade report", "curl -fsS http://localhost:8000/api/operations/upgrade/report", "Review FAIL items"),
        RunbookStep(2, "Check config validity", "uv run python -c 'from cc_deep_research.config import load_config; load_config()'", "No ValidationError"),
        RunbookStep(3, "Fetch rollback instructions", "curl -fsS 'http://localhost:8000/api/operations/upgrade/rollback?backup_id=<id>'", None),
        RunbookStep(4, "Verify rollback succeeded", "curl -fsS http://localhost:8000/api/health", "All checks PASS"),
        RunbookStep(5, "Re-run upgrade validation", "curl -fsS http://localhost:8000/api/operations/upgrade/validate", None),
        RunbookStep(6, "Escalate if rollback fails", None, "Contact maintainer with debug export",),
    ],
    related_checks=["config_file", "data_paths", "provider_credentials"],
    related_runbooks=["backup_failed"],
))


# --- Session Not Found ---
_register_runbook(Runbook(
    runbook_id="session_not_found",
    title="Session Not Found",
    summary="A research session cannot be found or loaded.",
    symptoms=[
        "Session detail page shows 404",
        "Session ID not in session store",
        "Telemetry events missing for session",
    ],
    steps=[
        RunbookStep(1, "List available sessions", "curl -fsS 'http://localhost:8000/api/sessions?limit=100'", "Session ID in list"),
        RunbookStep(2, "Check session file exists", "ls ~/.config/inqulume-studio/sessions/*.json", "File exists"),
        RunbookStep(3, "Check session store integrity", "uv run python -c 'from cc_deep_research.session_store import SessionStore; print(SessionStore().get_session_count())'", "Count > 0"),
        RunbookStep(4, "Verify telemetry exists", "ls ~/.config/inqulume-studio/telemetry/", "Directory exists"),
        RunbookStep(5, "Check archived sessions", "curl -fsS 'http://localhost:8000/api/sessions?archived_only=true&limit=100'", "Session may be archived"),
    ],
))


# --- Dashboard Build Failed ---
_register_runbook(Runbook(
    runbook_id="dashboard_build_failed",
    title="Dashboard Build Failed",
    summary="The Next.js dashboard build failed.",
    symptoms=[
        "'npm run build' returns non-zero exit",
        "TypeScript errors in build output",
        "Dashboard shows 500 error",
    ],
    steps=[
        RunbookStep(1, "Run linting", "cd dashboard && npm run lint", "Fix any lint errors"),
        RunbookStep(2, "Run type checking", "cd dashboard && npx tsc --noEmit", "Fix type errors"),
        RunbookStep(3, "Clear Next.js cache", "cd dashboard && rm -rf .next", None),
        RunbookStep(4, "Reinstall dependencies", "cd dashboard && npm ci", None),
        RunbookStep(5, "Retry build", "cd dashboard && npm run build", "Build succeeds"),
    ],
))


# --- Service Port Conflict ---
_register_runbook(Runbook(
    runbook_id="service_port_conflict",
    title="Service Port Conflict",
    summary="A required port is already in use, preventing service startup.",
    symptoms=[
        "'Port 8000 is already in use' error",
        "Service fails to bind to port",
        "lsof shows unexpected process on port",
    ],
    steps=[
        RunbookStep(1, "Find process using port", "lsof -i :8000", "PID and process name"),
        RunbookStep(2, "Identify the process", "ps aux | grep <PID>", "Expected or unexpected"),
        RunbookStep(3, "Stop conflicting service", "kill <PID>", None),
        RunbookStep(4, "Or prefer different ports", "BACKEND_PORT=8001 FRONTEND_PORT=3001 ./scripts/dashboard-dev", None),
        RunbookStep(5, "Verify port is now available", "lsof -i :8000", "No output"),
        RunbookStep(6, "Restart dashboard", "./scripts/dashboard-dev", "Started successfully"),
    ],
))


# --- Search Cache Issues ---
_register_runbook(Runbook(
    runbook_id="search_cache_issues",
    title="Search Cache Issues",
    summary="Search cache is causing stale results or errors.",
    symptoms=[
        "Research returns very old source results",
        "'Cache is disabled' errors",
        "Cache database file is missing",
    ],
    steps=[
        RunbookStep(1, "Check cache stats", "curl -fsS http://localhost:8000/api/search-cache/stats", "Cache state reported"),
        RunbookStep(2, "Purge expired entries", "curl -fsS -X POST http://localhost:8000/api/search-cache/purge-expired", None),
        RunbookStep(3, "Verify cache is enabled in config", "uv run python -c 'from cc_deep_research.config import load_config; c=load_config(); print(c.search_cache.enabled)'", "True"),
        RunbookStep(4, "Clear cache if needed", "curl -fsS -X DELETE http://localhost:8000/api/search-cache", None),
        RunbookStep(5, "Run research with fresh cache from the Research dashboard", None, "New results"),
    ],
))


# --- Knowledge Graph Issues ---
_register_runbook(Runbook(
    runbook_id="knowledge_graph_issues",
    title="Knowledge Graph Issues",
    summary="Knowledge graph has stale data or ingestion failures.",
    symptoms=[
        "Knowledge graph shows no data",
        "Ingestion errors in logs",
        "Orphan claims or duplicates reported",
    ],
    steps=[
        RunbookStep(1, "Check knowledge health", "curl -fsS http://localhost:8000/api/knowledge/health", "Health report returned"),
        RunbookStep(2, "Check knowledge directory", "ls ~/.config/inqulume-studio/knowledge/", "Directory exists"),
        RunbookStep(3, "Verify DuckDB knowledge base", "ls ~/.config/inqulume-studio/knowledge/knowledge.db", "File exists"),
        RunbookStep(4, "Check ingestion logs", "tail -50 ~/.config/inqulume-studio/telemetry/*/events.jsonl | grep knowledge", None),
        RunbookStep(5, "Review the Knowledge dashboard and rebuild only if health checks require it", None, None),
    ],
))


def get_runbook(runbook_id: str) -> Runbook | None:
    """Get a runbook by ID."""
    return RUNBOOKS.get(runbook_id)


def list_runbooks() -> list[dict[str, Any]]:
    """List all available runbooks.

    Returns:
        List of runbook summary dicts.
    """
    return [
        {
            "runbook_id": rb.runbook_id,
            "title": rb.title,
            "summary": rb.summary,
            "symptoms": rb.symptoms,
            "step_count": len(rb.steps),
        }
        for rb in RUNBOOKS.values()
    ]


def get_support_checklist() -> dict[str, Any]:
    """Get a support checklist for collecting artifacts during incident response.

    Returns:
        Dict with checklist items.
    """
    return {
        "checklist": [
            {
                "item": "Debug export",
                "command": "curl -fsS http://localhost:8000/api/operations/support/checklist",
                "description": "Collect the current incident-response checklist",
            },
            {
                "item": "Config summary",
                "command": "curl -fsS http://localhost:8000/api/operations/secrets/inventory",
                "description": "Credential inventory without secret values",
            },
            {
                "item": "Health status",
                "command": "curl -fsS http://localhost:8000/api/health",
                "description": "Full health report as JSON",
            },
            {
                "item": "Log files",
                "command": "ls ~/.config/inqulume-studio/telemetry/*/events.jsonl | xargs tail -100",
                "description": "Recent telemetry events",
            },
            {
                "item": "Backup manifest",
                "command": "ls ~/.config/inqulume-studio/*.manifest.json",
                "description": "Available backup manifests",
            },
            {
                "item": "Session list",
                "command": "curl -fsS 'http://localhost:8000/api/sessions?limit=100'",
                "description": "Current sessions and their status",
            },
            {
                "item": "Dashboard logs",
                "command": "tail -100 ~/.config/inqulume-studio/dashboard/*.log 2>/dev/null",
                "description": "Recent dashboard server logs",
            },
        ],
        "escalation_criteria": [
            "Incident persists after following all runbook steps",
            "Data loss or corruption suspected",
            "Provider credentials leaked or compromised",
            "Security incident detected",
        ],
        "contact": "File an issue at https://github.com/xxibcill/inqulume-studio/issues with the debug export attached",
    }


__all__ = [
    "Runbook",
    "RunbookStep",
    "get_runbook",
    "get_support_checklist",
    "list_runbooks",
]
