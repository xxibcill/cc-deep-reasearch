"""Direct Kimi API transport backed by Moonshot AI's OpenAI-compatible API."""

from __future__ import annotations

from typing import Any

from cc_deep_research.llm.base import (
    LLMProviderType,
    LLMRequest,
    LLMTransportType,
)
from cc_deep_research.llm.openai_compatible import (
    OpenAICompatibleProviderSpec,
    OpenAICompatibleTransport,
)


class KimiTransport(OpenAICompatibleTransport):
    """Execute non-streaming chat completions against the direct Kimi API."""

    provider_spec = OpenAICompatibleProviderSpec(
        display_name="Kimi",
        provider_type=LLMProviderType.KIMI,
        transport_type=LLMTransportType.KIMI_API,
        default_base_url="https://api.moonshot.ai/v1",
    )

    def _build_payload(self, request: LLMRequest, model: str) -> dict[str, Any]:
        """Build a Kimi request using its current completion-token field."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": self._build_messages(request),
            "max_completion_tokens": request.max_tokens,
        }
        reasoning_effort = self.route.extra.get("reasoning_effort")
        if model.startswith("kimi-k3") and isinstance(reasoning_effort, str) and reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
        return payload


__all__ = ["KimiTransport"]
