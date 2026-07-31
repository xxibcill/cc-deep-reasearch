"""Provider-neutral runtime context for LLM-backed workflows."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cc_deep_research.llm.codex_runtime import CodexRuntime


_request_scope: ContextVar[str | None] = ContextVar("llm_request_scope", default=None)


@dataclass(frozen=True, slots=True)
class LLMRuntimeContext:
    """Optional provider runtimes available to the shared LLM router."""

    codex_runtime: CodexRuntime | None = None

    def request_cancel(self, scope_id: str) -> None:
        """Interrupt provider work associated with one workflow scope."""
        if self.codex_runtime is not None:
            self.codex_runtime.request_cancel_scope(scope_id)


@contextmanager
def llm_request_scope(scope_id: str) -> Iterator[None]:
    """Associate downstream LLM calls with one cancellable workflow."""
    token = _request_scope.set(scope_id)
    try:
        yield
    finally:
        _request_scope.reset(token)


def get_llm_request_scope() -> str | None:
    """Return the workflow scope associated with the current request context."""
    return _request_scope.get()
