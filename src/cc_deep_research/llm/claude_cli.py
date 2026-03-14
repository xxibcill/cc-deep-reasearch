"""Claude CLI transport adapter for LLM routing layer.

This module extracts the Claude Code CLI subprocess logic into a reusable
transport adapter that fits the new LLM routing architecture.
"""

from __future__ import annotations

import os
import queue
import re
import shutil
import subprocess
import threading
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any, Callable

from cc_deep_research.llm.base import (
    BaseLLMTransport,
    LLMAuthenticationError,
    LLMError,
    LLMProviderType,
    LLMRequest,
    LLMResponse,
    LLMRoute,
    LLMTimeoutError,
    LLMTransportType,
)

if TYPE_CHECKING:
    from cc_deep_research.monitoring import ResearchMonitor


class _StreamReaderThread(threading.Thread):
    """Read a subprocess stream and forward chunks to a queue."""

    def __init__(
        self,
        stream: Any,
        stream_name: str,
        chunk_queue: queue.Queue[tuple[str, str]],
    ) -> None:
        """Initialize the reader thread."""
        super().__init__(daemon=True)
        self._stream = stream
        self._stream_name = stream_name
        self._chunk_queue = chunk_queue

    def run(self) -> None:
        """Read the stream line by line and forward each chunk."""
        if self._stream is None:
            return
        try:
            for line in self._stream:
                self._chunk_queue.put((self._stream_name, line))
        except Exception:
            pass
        finally:
            with suppress(Exception):
                self._stream.close()


class ClaudeCLITransport(BaseLLMTransport):
    """Claude CLI transport adapter for LLM operations.

    This transport executes Claude CLI as a subprocess for prompt-based
    LLM operations. It preserves the streamed subprocess telemetry and
    nested-session protection from the original implementation.

    Attributes:
        _cli_path: Path to the Claude CLI executable.
        _timeout_seconds: Request timeout in seconds.
        _monitor: Optional research monitor for telemetry.
    """

    def __init__(
        self,
        route: LLMRoute,
        *,
        monitor: ResearchMonitor | None = None,
        telemetry_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Initialize the Claude CLI transport.

        Args:
            route: The route configuration for this transport.
            monitor: Optional research monitor for subprocess telemetry.
            telemetry_callback: Optional callback for LLM-level telemetry.
        """
        super().__init__(route, telemetry_callback=telemetry_callback)
        self._monitor = monitor

        # Get CLI path from route extra config or environment
        configured_path = route.extra.get("path") or os.environ.get("CLAUDE_CLI_PATH")
        self._cli_path = configured_path or shutil.which("claude")

        self._timeout_seconds = route.timeout_seconds
        self._model = route.model

    @property
    def transport_type(self) -> LLMTransportType:
        """Return the transport type for this adapter."""
        return LLMTransportType.CLAUDE_CLI

    @property
    def provider_type(self) -> LLMProviderType:
        """Return the provider type for this adapter."""
        return LLMProviderType.CLAUDE

    def is_available(self) -> bool:
        """Check if Claude CLI is available.

        Returns:
            True if the CLI executable exists and is not blocked by
            nested session constraints.
        """
        if not self._cli_path:
            return False

        # Check for nested session constraint
        if os.environ.get("CLAUDECODE"):
            return False

        return True

    async def execute(self, request: LLMRequest) -> LLMResponse:
        """Execute an LLM request using Claude CLI.

        Args:
            request: The normalized LLM request.

        Returns:
            The normalized LLM response.

        Raises:
            LLMTimeoutError: If the request times out.
            LLMAuthenticationError: If running in a nested Claude session.
            LLMError: On CLI failure or missing executable.
        """
        start_time = time.time()
        model = request.model or self._model
        command = self._build_command(request.prompt, model)
        prompt_preview = self._sanitize_prompt_preview(request.prompt)

        # Get parent event ID from monitor's current context
        parent_id = self._monitor.current_parent_id if self._monitor else None

        # Emit subprocess.scheduled
        scheduled_event_id = self._emit_subprocess_event(
            event_type="subprocess.scheduled",
            status="scheduled",
            parent_event_id=parent_id,
            metadata={
                "operation": request.metadata.get("operation", "unknown"),
                "executable": self._cli_path,
                "model": model,
                "timeout_seconds": self._timeout_seconds,
                "prompt_preview": prompt_preview,
            },
        )

        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        chunk_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        chunk_indexes = {"stdout": 0, "stderr": 0}
        process: subprocess.Popen[str] | None = None

        try:
            # Start the process with pipes for streaming
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            # Emit subprocess.started
            self._emit_subprocess_event(
                event_type="subprocess.started",
                status="started",
                parent_event_id=scheduled_event_id,
                metadata={
                    "operation": request.metadata.get("operation", "unknown"),
                    "pid": process.pid,
                    "executable": self._cli_path,
                },
            )

            stdout_reader = _StreamReaderThread(process.stdout, "stdout", chunk_queue)
            stderr_reader = _StreamReaderThread(process.stderr, "stderr", chunk_queue)

            stdout_reader.start()
            stderr_reader.start()

            timed_out = False
            while True:
                self._drain_stream_queue(
                    chunk_queue=chunk_queue,
                    stdout_chunks=stdout_chunks,
                    stderr_chunks=stderr_chunks,
                    chunk_indexes=chunk_indexes,
                    parent_event_id=scheduled_event_id,
                    operation=request.metadata.get("operation", "unknown"),
                )

                elapsed = time.time() - start_time
                if elapsed >= self._timeout_seconds:
                    timed_out = True
                    break

                try:
                    process.wait(timeout=0.05)
                    break
                except subprocess.TimeoutExpired:
                    continue

            if timed_out:
                process.kill()
                process.wait()

            stdout_reader.join(timeout=1.0)
            stderr_reader.join(timeout=1.0)
            self._drain_stream_queue(
                chunk_queue=chunk_queue,
                stdout_chunks=stdout_chunks,
                stderr_chunks=stderr_chunks,
                chunk_indexes=chunk_indexes,
                parent_event_id=scheduled_event_id,
                operation=request.metadata.get("operation", "unknown"),
            )

            duration_ms = int((time.time() - start_time) * 1000)
            full_stdout = "".join(stdout_chunks)
            full_stderr = "".join(stderr_chunks)

            if timed_out:
                self._emit_subprocess_event(
                    event_type="subprocess.timeout",
                    status="timeout",
                    parent_event_id=scheduled_event_id,
                    duration_ms=duration_ms,
                    metadata={
                        "operation": request.metadata.get("operation", "unknown"),
                        "timeout_seconds": self._timeout_seconds,
                        "exit_code": process.returncode,
                        "stdout_length": len(full_stdout),
                        "stderr_length": len(full_stderr),
                    },
                )
                raise LLMTimeoutError(
                    f"Claude CLI request timed out after {self._timeout_seconds} seconds",
                    timeout_seconds=self._timeout_seconds,
                    provider=LLMProviderType.CLAUDE,
                    transport=LLMTransportType.CLAUDE_CLI,
                )

            if process.returncode != 0:
                error_output = (
                    full_stderr.strip() or full_stdout.strip() or "unknown Claude CLI error"
                )

                # Check for nested session error
                if (
                    "nested session" in error_output.lower()
                    or "inside another Claude Code session" in error_output.lower()
                ):
                    self._emit_subprocess_event(
                        event_type="subprocess.failed",
                        status="failed",
                        parent_event_id=scheduled_event_id,
                        duration_ms=duration_ms,
                        metadata={
                            "operation": request.metadata.get("operation", "unknown"),
                            "exit_code": process.returncode,
                            "error_type": "nested_session",
                        },
                    )
                    raise LLMAuthenticationError(
                        "Claude CLI disabled: running inside Claude Code session",
                        provider=LLMProviderType.CLAUDE,
                        transport=LLMTransportType.CLAUDE_CLI,
                    )

                self._emit_subprocess_event(
                    event_type="subprocess.failed",
                    status="failed",
                    parent_event_id=scheduled_event_id,
                    duration_ms=duration_ms,
                    metadata={
                        "operation": request.metadata.get("operation", "unknown"),
                        "exit_code": process.returncode,
                        "stdout_length": len(full_stdout),
                        "stderr_length": len(full_stderr),
                        "error_preview": error_output[:200],
                    },
                )

                raise LLMError(
                    f"Claude CLI request failed: {error_output}",
                    provider=LLMProviderType.CLAUDE,
                    transport=LLMTransportType.CLAUDE_CLI,
                )

            self._emit_subprocess_event(
                event_type="subprocess.completed",
                status="completed",
                parent_event_id=scheduled_event_id,
                duration_ms=duration_ms,
                metadata={
                    "operation": request.metadata.get("operation", "unknown"),
                    "exit_code": 0,
                    "stdout_length": len(full_stdout),
                    "stderr_length": len(full_stderr),
                    "stdout_chunks": chunk_indexes["stdout"],
                    "stderr_chunks": chunk_indexes["stderr"],
                },
            )

            # Emit LLM-level telemetry
            self._emit_telemetry(
                "llm_request_completed",
                {
                    "operation": request.metadata.get("operation", "unknown"),
                    "model": model,
                    "latency_ms": duration_ms,
                },
            )

            return LLMResponse(
                content=full_stdout.strip(),
                model=model,
                provider=LLMProviderType.CLAUDE,
                transport=LLMTransportType.CLAUDE_CLI,
                latency_ms=duration_ms,
                finish_reason="stop",
                metadata={
                    "operation": request.metadata.get("operation", "unknown"),
                    "prompt_preview": prompt_preview,
                },
            )

        except FileNotFoundError as exc:
            duration_ms = int((time.time() - start_time) * 1000)

            # Emit subprocess.failed_to_start
            self._emit_subprocess_event(
                event_type="subprocess.failed_to_start",
                status="failed",
                parent_event_id=scheduled_event_id,
                duration_ms=duration_ms,
                metadata={
                    "operation": request.metadata.get("operation", "unknown"),
                    "error_type": "FileNotFoundError",
                    "executable": self._cli_path,
                },
            )

            raise LLMError(
                f"Claude CLI executable not found: {self._cli_path}",
                provider=LLMProviderType.CLAUDE,
                transport=LLMTransportType.CLAUDE_CLI,
                original_error=exc,
            ) from exc

    def _build_command(self, prompt: str, model: str) -> list[str]:
        """Build a Claude CLI command for a single prompt.

        Args:
            prompt: The prompt to send.
            model: The model to use.

        Returns:
            The command as a list of strings.
        """
        return [
            self._cli_path,
            "-p",
            "--model",
            model,
            "--output-format",
            "text",
            "--no-session-persistence",
            prompt,
        ]

    @staticmethod
    def _sanitize_prompt_preview(prompt: str, max_chars: int = 160) -> str:
        """Return a single-line prompt preview suitable for telemetry."""
        compact_prompt = re.sub(r"\s+", " ", prompt).strip()
        if len(compact_prompt) <= max_chars:
            return compact_prompt
        return compact_prompt[:max_chars].rstrip() + "..."

    @staticmethod
    def _truncate_stream_chunk(chunk: str, max_chars: int = 4000) -> dict[str, Any]:
        """Return a dashboard-safe chunk payload."""
        if len(chunk) <= max_chars:
            return {
                "content": chunk,
                "content_length": len(chunk),
                "content_truncated": False,
            }
        return {
            "content": chunk[:max_chars],
            "content_length": len(chunk),
            "content_truncated": True,
        }

    def _emit_subprocess_event(
        self,
        event_type: str,
        status: str,
        *,
        parent_event_id: str | None = None,
        duration_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Emit a structured subprocess telemetry event.

        Args:
            event_type: The event type (e.g., 'subprocess.started').
            status: Event status (e.g., 'started', 'completed', 'failed').
            parent_event_id: Optional parent event ID for correlation.
            duration_ms: Optional duration in milliseconds.
            metadata: Optional additional metadata.

        Returns:
            Event ID if monitor is available, None otherwise.
        """
        if self._monitor is None:
            return None
        return self._monitor.emit_event(
            event_type=event_type,
            category="llm",
            name="claude_cli",
            status=status,
            parent_event_id=parent_event_id,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

    def _emit_stream_chunk(
        self,
        *,
        stream_name: str,
        chunk: str,
        chunk_index: int,
        parent_event_id: str | None,
        operation: str,
    ) -> None:
        """Emit a single stdout or stderr chunk event."""
        if self._monitor is None or not chunk:
            return

        event_type = f"subprocess.{stream_name}_chunk"
        metadata = {
            "operation": operation,
            "stream": stream_name,
            "chunk_index": chunk_index,
            **self._truncate_stream_chunk(chunk),
        }
        self._monitor.emit_event(
            event_type=event_type,
            category="llm",
            name="claude_cli",
            status="streaming",
            parent_event_id=parent_event_id,
            metadata=metadata,
        )

    def _drain_stream_queue(
        self,
        *,
        chunk_queue: queue.Queue[tuple[str, str]],
        stdout_chunks: list[str],
        stderr_chunks: list[str],
        chunk_indexes: dict[str, int],
        parent_event_id: str | None,
        operation: str,
    ) -> None:
        """Drain any available stream chunks and emit telemetry in order."""
        while True:
            try:
                stream_name, chunk = chunk_queue.get_nowait()
            except queue.Empty:
                return

            if stream_name == "stdout":
                stdout_chunks.append(chunk)
            else:
                stderr_chunks.append(chunk)

            chunk_index = chunk_indexes[stream_name]
            chunk_indexes[stream_name] += 1
            self._emit_stream_chunk(
                stream_name=stream_name,
                chunk=chunk,
                chunk_index=chunk_index,
                parent_event_id=parent_event_id,
                operation=operation,
            )


__all__ = ["ClaudeCLITransport"]
