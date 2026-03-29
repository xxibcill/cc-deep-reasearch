"""Content generation workflow for short-form video creation."""

from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

__all__ = [
    "ContentGenOrchestrator",
    "register_content_gen_commands",
]


def register_content_gen_commands(cli_group):  # type: ignore[no-untyped-def]
    """Lazy wrapper to register CLI commands."""
    from cc_deep_research.content_gen.cli import (
        register_content_gen_commands as _register,
    )

    _register(cli_group)
