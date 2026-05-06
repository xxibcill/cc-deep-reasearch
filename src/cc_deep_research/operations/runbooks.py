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
        RunbookStep(1, "Check if backend is running", "cc-deep-research dashboard status", "PID and status returned"),
        RunbookStep(2, "Check backend port availability", "lsof -i :8000", "Process listed on port 8000"),
        RunbookStep(3, "Check frontend port availability", "lsof -i :3000", "Node process on port 3000"),
        RunbookStep(4, "Verify dashboard build exists", "ls dashboard/.next", "Build directory exists"),
        RunbookStep(5, "Check Node.js version", "node --version", "v18+"),
        RunbookStep(6, "Restart services", "cc-deep-research dashboard restart", "Services running"),
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
        RunbookStep(3, "Start backend in foreground to see errors", "cd /Users/jjae/Documents/guthib/cc-deep-research && uv run cc-deep-research dashboard", None),
        RunbookStep(4, "Verify config loads", "uv run python -c 'from cc_deep_research.config import load_config; print(\"OK\")'", "OK printed"),
        RunbookStep(5, "Check provider credentials", "cc-deep-research health check --section provider", None),
        RunbookStep(6, "Check log files for errors", "tail -100 ~/.config/cc-deep-research/telemetry/*/events.jsonl 2>/dev/null | tail -50", None),
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
        RunbookStep(2, "Test WebSocket endpoint manually", "wscat -c ws://localhost:8000/ws", "Connected"),
        RunbookStep(3, "Check browser console for CORS errors", None, "No CORS policy errors"),
        RunbookStep(4, "Verify no firewall is blocking WebSocket upgrade", "curl -v -N -H 'Connection: Upgrade' -H 'Upgrade: websocket' http://localhost:8000/ws", "101 Switching Protocols"),
        RunbookStep(5, "Restart backend to reset WebSocket handler", "cc-deep-research dashboard stop && cc-deep-research dashboard start", None),
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
        RunbookStep(5, "Run health check to confirm", "cc-deep-research health check", "Provider credentials PASS"),
        RunbookStep(6, "Test a research run", "cc-deep-research research 'test query' --depth quick", None),
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
        RunbookStep(1, "Check disk space", "df -h ~/.config/cc-deep-research/telemetry", "> 1GB free"),
        RunbookStep(2, "Check DuckDB size", "ls -lh ~/.config/cc-deep-research/telemetry/dashboard.db", "Size within limits"),
        RunbookStep(3, "Run retention policy", "cc-deep-research telemetry retention --dry-run", None),
        RunbookStep(4, "Compact old sessions", "cc-deep-research telemetry compact --older-than 30d", None),
        RunbookStep(5, "Verify analytics query performance", "cc-deep-research analytics --days 7", "Returns in < 5s"),
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
        RunbookStep(2, "Verify backup permissions", "ls -la ~/.config/cc-deep-research/", "Directories are writable"),
        RunbookStep(3, "Validate manifest manually", "python3 -c 'import json; json.load(open(\"backup.manifest.json\"))'", "No JSON parse error"),
        RunbookStep(4, "Check for conflicting processes", "lsof ~/.config/cc-deep-research/*.json", "No lock on files"),
        RunbookStep(5, "Retry with dry-run", "cc-deep-research backup plan --dry-run", None),
        RunbookStep(6, "Run backup with verbose output", "cc-deep-research backup create --verbose", None),
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
        RunbookStep(1, "Check upgrade report", "cc-deep-research upgrade report", "Review FAIL items"),
        RunbookStep(2, "Check config validity", "uv run python -c 'from cc_deep_research.config import load_config; load_config()'", "No ValidationError"),
        RunbookStep(3, "Run rollback instructions", "cc-deep-research upgrade rollback --backup <id>", None),
        RunbookStep(4, "Verify rollback succeeded", "cc-deep-research health check", "All checks PASS"),
        RunbookStep(5, "Re-run upgrade with dry-run first", "cc-deep-research upgrade validate --dry-run", None),
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
        RunbookStep(1, "List available sessions", "cc-deep-research session list", "Session ID in list"),
        RunbookStep(2, "Check session file exists", "ls ~/.config/cc-deep-research/sessions/*.json", "File exists"),
        RunbookStep(3, "Check session store integrity", "uv run python -c 'from cc_deep_research.session_store import SessionStore; print(SessionStore().get_session_count())'", "Count > 0"),
        RunbookStep(4, "Verify telemetry exists", "ls ~/.config/cc-deep-research/telemetry/", "Directory exists"),
        RunbookStep(5, "Check archived sessions", "cc-deep-research session archive list", "Session may be archived"),
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
        RunbookStep(4, "Or use a different port", "cc-deep-research dashboard --port 8001", None),
        RunbookStep(5, "Verify port is now available", "lsof -i :8000", "No output"),
        RunbookStep(6, "Restart dashboard", "cc-deep-research dashboard start", "Started successfully"),
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
        RunbookStep(1, "Check cache stats", "cc-deep-research cache stats", "Cache state reported"),
        RunbookStep(2, "Purge expired entries", "cc-deep-research cache purge-expired", None),
        RunbookStep(3, "Verify cache is enabled in config", "uv run python -c 'from cc_deep_research.config import load_config; c=load_config(); print(c.search_cache.enabled)'", "True"),
        RunbookStep(4, "Clear cache if needed", "cc-deep-research cache clear", None),
        RunbookStep(5, "Run research with fresh cache", "cc-deep-research research 'fresh query' --depth quick", "New results"),
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
        RunbookStep(1, "Check knowledge health", "cc-deep-research knowledge health", "Health report returned"),
        RunbookStep(2, "Check knowledge directory", "ls ~/.config/cc-deep-research/knowledge/", "Directory exists"),
        RunbookStep(3, "Verify DuckDB knowledge base", "ls ~/.config/cc-deep-research/knowledge/knowledge.db", "File exists"),
        RunbookStep(4, "Check ingestion logs", "tail -50 ~/.config/cc-deep-research/telemetry/*/events.jsonl | grep knowledge", None),
        RunbookStep(5, "Run knowledge cleanup", "cc-deep-research knowledge cleanup --dry-run", None),
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
                "command": "cc-deep-research debug-export",
                "description": "Collect system state, config (redacted), and logs",
            },
            {
                "item": "Config summary",
                "command": "cc-deep-research config show",
                "description": "Current configuration (secrets redacted)",
            },
            {
                "item": "Health status",
                "command": "cc-deep-research health check --json",
                "description": "Full health report as JSON",
            },
            {
                "item": "Log files",
                "command": "ls ~/.config/cc-deep-research/telemetry/*/events.jsonl | xargs tail -100",
                "description": "Recent telemetry events",
            },
            {
                "item": "Backup manifest",
                "command": "ls ~/.config/cc-deep-research/*.manifest.json",
                "description": "Available backup manifests",
            },
            {
                "item": "Session list",
                "command": "cc-deep-research session list",
                "description": "Current sessions and their status",
            },
            {
                "item": "Dashboard logs",
                "command": "tail -100 ~/.config/cc-deep-research/dashboard/*.log 2>/dev/null",
                "description": "Recent dashboard server logs",
            },
        ],
        "escalation_criteria": [
            "Incident persists after following all runbook steps",
            "Data loss or corruption suspected",
            "Provider credentials leaked or compromised",
            "Security incident detected",
        ],
        "contact": "File an issue at https://github.com/anthropics/cc-deep-research/issues with the debug export attached",
    }


__all__ = [
    "Runbook",
    "RunbookStep",
    "get_runbook",
    "get_support_checklist",
    "list_runbooks",
]
