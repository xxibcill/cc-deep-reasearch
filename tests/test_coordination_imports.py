"""Regression tests for coordination imports in threads without event loops."""

from __future__ import annotations

import importlib
import threading


def _reload_in_thread(module_name: str) -> list[BaseException]:
    errors: list[BaseException] = []

    def runner() -> None:
        try:
            module = importlib.import_module(module_name)
            importlib.reload(module)
        except BaseException as exc:  # pragma: no cover - assertion captures errors
            errors.append(exc)

    thread = threading.Thread(target=runner, name="coordination-import-test")
    thread.start()
    thread.join()
    return errors


def test_coordination_modules_reload_without_event_loop() -> None:
    """Worker-thread imports should not require an asyncio event loop."""
    module_names = (
        "cc_deep_research.coordination.agent_pool",
        "cc_deep_research.coordination.message_bus",
        "cc_deep_research.dashboard_app",
    )

    for module_name in module_names:
        assert _reload_in_thread(module_name) == []
