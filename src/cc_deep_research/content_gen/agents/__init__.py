"""Content generation agents."""

from cc_deep_research.content_gen.agents.scripting import ScriptingAgent

CONTENT_GEN_AGENT_REGISTRY: dict[str, type] = {
    "scripting": ScriptingAgent,
}

__all__ = [
    "CONTENT_GEN_AGENT_REGISTRY",
    "ScriptingAgent",
]
