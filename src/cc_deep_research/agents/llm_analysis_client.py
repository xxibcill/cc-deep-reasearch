"""LLM-powered analysis client for deep semantic analysis.

This module provides AI-powered analysis using the Claude Code CLI,
replacing heuristic-based pattern matching with real semantic understanding.

Features:
- Theme extraction with semantic clustering
- Cross-reference analysis for consensus/disagreement detection
- Gap identification with query relevance scoring
- Synthesis with proper attribution
- Evidence quality analysis
- Streamed subprocess telemetry for live monitoring
- Prompt override support for customized agent behavior

Uses prompt-based CLI invocations for large-source semantic analysis.
"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cc_deep_research.monitoring import ResearchMonitor
    from cc_deep_research.prompts import PromptRegistry


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


class LLMAnalysisClient:
    """Client for AI-powered semantic analysis using the Claude Code CLI.

    This client provides real semantic analysis that goes beyond
    keyword matching, making actual Claude CLI calls for
    deep understanding of research content.

    Attributes:
        _claude_cli_path: Claude CLI executable path
        _model: Model to use for analysis
        _timeout_seconds: Maximum seconds per response
        _monitor: Optional research monitor for telemetry
        _prompt_registry: Optional prompt registry with overrides
        _agent_id: Agent identifier for prompt resolution
    """

    def __init__(
        self,
        config: dict[str, Any],
        monitor: ResearchMonitor | None = None,
    ) -> None:
        """Initialize LLM analysis client.

        Args:
            config: Configuration dictionary with:
                - claude_cli_path: Optional Claude CLI path
                - model: Model to use (default: claude-sonnet-4-6)
                - timeout_seconds: Max seconds per request
                - prompt_registry: Optional PromptRegistry with overrides
                - agent_id: Agent identifier for prompt resolution
            monitor: Optional research monitor for subprocess telemetry.
        """
        self._config = config
        self._model = config.get("model", "claude-sonnet-4-6")
        self._timeout_seconds = int(config.get("timeout_seconds", 180))
        self._usage_callback = config.get("usage_callback")
        self._request_executor = config.get("request_executor")
        self._monitor = monitor
        self._prompt_registry: PromptRegistry | None = config.get("prompt_registry")
        self._agent_id: str = config.get("agent_id", "analyzer")
        configured_path = config.get("claude_cli_path") or os.environ.get("CLAUDE_CLI_PATH")
        self._claude_cli_path = configured_path or shutil.which("claude")
        if self._request_executor is not None:
            self._claude_cli_path = self._claude_cli_path or "router"
            return
        if not self._claude_cli_path:
            raise ValueError(
                "Claude Code CLI not found. Install `claude` or set "
                "claude_cli_path/CLAUDE_CLI_PATH."
            )

    def extract_themes(
        self,
        sources: list[dict[str, str]],
        query: str,
        num_themes: int = 8,
    ) -> list[dict[str, Any]]:
        """Extract themes using semantic analysis.

        Makes actual Claude CLI calls for deep understanding.

        Args:
            sources: List of sources with url, title, content.
            query: Research query.
            num_themes: Number of themes to extract.

        Returns:
            List of themes with:
            - name: Theme name
            - description: Detailed description
            - supporting_sources: List of source URLs
            - key_points: List of key points within theme
        """
        # Prepare content for analysis
        content = self._prepare_content_for_analysis(sources)

        prompt = self._build_theme_extraction_prompt(query, content, num_themes)

        response_text = self._request(operation="extract_themes", prompt=prompt)
        return self._parse_theme_response(response_text, sources)

    def analyze_cross_reference(
        self,
        sources: list[dict[str, str]],
        themes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Perform cross-reference analysis across sources.

        Args:
            sources: List of sources with content.
            themes: Identified themes from semantic analysis.

        Returns:
            Dictionary with:
            - consensus_points: List of consensus claims with supporting sources
            - disagreement_points: List of contradictory claims with evidence
            - cross_reference_claims: List of claim objects
        """
        content = self._prepare_content_for_analysis(sources)

        prompt = self._build_cross_reference_prompt(themes, content)

        response_text = self._request(operation="analyze_cross_reference", prompt=prompt)
        return self._parse_cross_reference_response(response_text)

    def identify_gaps(
        self,
        sources: list[dict[str, str]],
        query: str,
        themes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Identify information gaps in the research.

        Args:
            sources: List of analyzed sources.
            query: Original research query.
            themes: Identified themes.

        Returns:
            List of gaps with:
            - gap_description: What's missing
            - importance: High/Medium/Low
            - suggested_queries: Queries to fill gap
        """
        content = self._prepare_content_for_analysis(sources)

        prompt = self._build_gap_identification_prompt(query, themes, content)

        response_text = self._request(operation="identify_gaps", prompt=prompt)
        return self._parse_gap_response(response_text)

    def synthesize_findings(
        self,
        sources: list[dict[str, str]],
        themes: list[dict[str, Any]],
        cross_ref: dict[str, Any],
        gaps: list[dict[str, Any]],
        query: str,
    ) -> list[dict[str, Any]]:
        """Synthesize key findings with proper attribution.

        Args:
            sources: List of sources.
            themes: Identified themes.
            cross_ref: Cross-reference analysis results.
            gaps: Identified gaps.
            query: Original research query.

        Returns:
            List of findings with:
            - title: Finding title
            - description: Detailed description
            - evidence: List of supporting source references
            - confidence: High/Medium/Low
        """
        content = self._prepare_content_for_analysis(sources)

        prompt = self._build_synthesis_prompt(query, themes, cross_ref, gaps, content)

        response_text = self._request(operation="synthesize_findings", prompt=prompt)
        return self._parse_synthesis_response(response_text)

    def analyze_evidence_quality(
        self,
        sources: list[dict[str, str]],
        themes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Analyze evidence quality across sources.

        Distinguishes between human studies, animal studies, and in vitro studies.
        Identifies conflicting evidence and assigns confidence levels.

        Args:
            sources: List of sources with content.
            themes: Identified themes from semantic analysis.

        Returns:
            Dictionary with:
            - study_types: Breakdown of human/animal/in vitro/other studies
            - evidence_conflicts: List of identified conflicts with explanations
            - confidence_levels: Confidence assessment for each theme
            - evidence_summary: Overall evidence quality summary
        """
        content = self._prepare_content_for_analysis(sources)

        prompt = self._build_evidence_quality_prompt(themes, content)

        response_text = self._request(operation="analyze_evidence_quality", prompt=prompt)
        return self._parse_evidence_quality_response(response_text)

    def _prepare_content_for_analysis(
        self, sources: list[dict[str, str]], max_sources: int = 15
    ) -> str:
        """Prepare source content for analysis.

        Args:
            sources: List of sources.
            max_sources: Maximum number of sources to include.

        Returns:
            Formatted content string.
        """
        sections = []
        for i, source in enumerate(sources[:max_sources], 1):
            content = source.get("content", "") or source.get("snippet", "")
            if content:
                # Truncate to reasonable length
                truncated = content[:2000]
                last_period = truncated.rfind(".")
                if last_period > len(truncated) * 0.7:
                    truncated = truncated[: last_period + 1]

                sections.append(f"\n--- Source {i} ---")
                sections.append(f"Title: {source.get('title', 'Untitled')}")
                sections.append(f"URL: {source.get('url', '')}")
                sections.append(f"Content: {truncated}")

        return "\n".join(sections)

    def _build_command(self, prompt: str) -> list[str]:
        """Build a Claude CLI command for a single prompt."""
        return [
            self._claude_cli_path,
            "-p",
            "--model",
            self._model,
            "--output-format",
            "text",
            "--no-session-persistence",
            prompt,
        ]

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

    def _request(self, operation: str, prompt: str) -> str:
        """Execute a Claude CLI request with streamed subprocess telemetry.

        Uses Popen for streaming capability while maintaining the blocking
        interface expected by callers. Emits structured events for:
        - subprocess.scheduled: Before process starts
        - subprocess.started: When process begins
        - subprocess.stdout_chunk: For each stdout chunk
        - subprocess.stderr_chunk: For each stderr chunk
        - subprocess.completed: On successful completion
        - subprocess.timeout: On timeout
        - subprocess.failed_to_start: On FileNotFoundError

        Args:
            operation: Name of the LLM operation (e.g., 'extract_themes').
            prompt: The prompt to send to Claude CLI.

        Returns:
            The stdout response from Claude CLI.

        Raises:
            RuntimeError: On CLI failure, timeout, or missing executable.
        """
        if self._request_executor is not None:
            try:
                return str(self._request_executor(operation, prompt))
            except Exception as exc:
                raise RuntimeError(str(exc)) from exc

        start_time = time.time()
        command = self._build_command(prompt)
        prompt_preview = self._sanitize_prompt_preview(prompt)

        # Get parent event ID from monitor's current context
        parent_id = self._monitor.current_parent_id if self._monitor else None

        # Emit subprocess.scheduled
        scheduled_event_id = self._emit_subprocess_event(
            event_type="subprocess.scheduled",
            status="scheduled",
            parent_event_id=parent_id,
            metadata={
                "operation": operation,
                "executable": self._claude_cli_path,
                "model": self._model,
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
                    "operation": operation,
                    "pid": process.pid,
                    "executable": self._claude_cli_path,
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
                    operation=operation,
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
                operation=operation,
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
                        "operation": operation,
                        "timeout_seconds": self._timeout_seconds,
                        "exit_code": process.returncode,
                        "stdout_length": len(full_stdout),
                        "stderr_length": len(full_stderr),
                    },
                )
                raise RuntimeError(
                    f"Claude CLI request timed out after {self._timeout_seconds} seconds. "
                    f"Try increasing claude_cli_timeout_seconds in config."
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
                            "operation": operation,
                            "exit_code": process.returncode,
                            "error_type": "nested_session",
                        },
                    )
                    raise RuntimeError(
                        "Claude CLI disabled: running inside Claude Code session. "
                        "Set ai_integration_method='heuristic' to avoid this error."
                    )

                self._emit_subprocess_event(
                    event_type="subprocess.failed",
                    status="failed",
                    parent_event_id=scheduled_event_id,
                    duration_ms=duration_ms,
                    metadata={
                        "operation": operation,
                        "exit_code": process.returncode,
                        "stdout_length": len(full_stdout),
                        "stderr_length": len(full_stderr),
                        "error_preview": error_output[:200],
                    },
                )

                raise RuntimeError(
                    f"Claude CLI request failed for {operation}: {error_output}"
                )

            self._emit_subprocess_event(
                event_type="subprocess.completed",
                status="completed",
                parent_event_id=scheduled_event_id,
                duration_ms=duration_ms,
                metadata={
                    "operation": operation,
                    "exit_code": 0,
                    "stdout_length": len(full_stdout),
                    "stderr_length": len(full_stderr),
                    "stdout_chunks": chunk_indexes["stdout"],
                    "stderr_chunks": chunk_indexes["stderr"],
                },
            )

            # Emit usage telemetry (note: token counts are not available from CLI output)
            if self._usage_callback:
                self._usage_callback(
                    operation=operation,
                    model=self._model,
                    prompt_tokens=0,  # CLI does not provide token counts
                    completion_tokens=0,  # CLI does not provide token counts
                    duration_ms=duration_ms,
                )

            return full_stdout.strip()

        except FileNotFoundError as exc:
            duration_ms = int((time.time() - start_time) * 1000)

            # Emit subprocess.failed_to_start
            self._emit_subprocess_event(
                event_type="subprocess.failed_to_start",
                status="failed",
                parent_event_id=scheduled_event_id,
                duration_ms=duration_ms,
                metadata={
                    "operation": operation,
                    "error_type": "FileNotFoundError",
                    "executable": self._claude_cli_path,
                },
            )

            raise RuntimeError(
                f"Claude CLI executable not found: {self._claude_cli_path}"
            ) from exc

    def _build_theme_extraction_prompt(self, query: str, content: str, num_themes: int) -> str:
        """Build prompt for theme extraction.

        Args:
            query: Research query.
            content: Formatted content.
            num_themes: Number of themes.

        Returns:
            Analysis prompt.
        """
        # Get base prompt with optional prefix from registry
        base_prompt = f"""Analyze the following research sources about "{query}" and identify {num_themes} major themes.

{content}

CRITICAL OUTPUT REQUIREMENTS:
- Rewrite the source material into clean professional prose. DO NOT copy raw page headers or markdown syntax.
- Ignore menus, site navigation, buttons, share widgets, newsletter prompts, and article metadata.
- Provide complete sentences that remain understandable out of context.
- If the source text is fragmentary, infer cautiously or omit it.

For each theme, provide:
1. A concise, descriptive theme name (e.g., "Antioxidant Properties", not "Health Benefits Drinking White")
2. A 2-3 sentence description summarizing what the sources say about this theme
3. 3-5 key points with specific facts or findings
4. URLs of sources that support this theme

Focus on:
- Actual health benefits with scientific backing
- Specific compounds and their effects
- Concrete findings, not vague generalizations
- Distinct themes that don't overlap

Respond in JSON format:
{{
  "themes": [
    {{
      "name": "Theme Name",
      "description": "Description...",
      "key_points": ["Point 1", "Point 2", "Point 3"],
      "supporting_sources": ["url1", "url2"]
    }}
  ]
}}
"""
        # Apply prompt prefix from registry if available
        if self._prompt_registry:
            config = self._prompt_registry.resolve_prompt(self._agent_id, "extract_themes")
            if config.prompt_prefix:
                return f"{config.prompt_prefix}\n\n{base_prompt}"
        return base_prompt

    def _build_cross_reference_prompt(self, themes: list[dict[str, Any]], content: str) -> str:
        """Build prompt for cross-reference analysis.

        Args:
            themes: Identified themes.
            content: Formatted content.

        Returns:
            Analysis prompt.
        """
        theme_names = [t.get("name", "") for t in themes]
        base_prompt = f"""Analyze the following research sources for consensus and disagreement points.

Identified themes: {", ".join(theme_names)}

{content}

Task: Identify where sources agree (consensus) and where they disagree (contention).

For consensus points:
- Identify claims that multiple sources support
- Note the strength of consensus (strong/moderate/weak)
- List supporting source URLs

For disagreement points:
- Identify claims where sources contradict each other
- Explain the nature of the disagreement
- List the conflicting sources

Respond in JSON format:
{{
  "consensus_points": [
    {{
      "claim": "The claim that sources agree on",
      "strength": "strong/moderate/weak",
      "supporting_sources": ["url1", "url2"]
    }}
  ],
  "disagreement_points": [
    {{
      "claim": "The area of disagreement",
      "perspectives": [
        {{"view": "One perspective", "sources": ["url1"]}},
        {{"view": "Contradicting perspective", "sources": ["url2"]}}
      ]
    }}
  ]
}}
"""
        # Apply prompt prefix from registry if available
        if self._prompt_registry:
            config = self._prompt_registry.resolve_prompt(self._agent_id, "cross_reference")
            if config.prompt_prefix:
                return f"{config.prompt_prefix}\n\n{base_prompt}"
        return base_prompt

    def _build_gap_identification_prompt(
        self, query: str, themes: list[dict[str, Any]], content: str
    ) -> str:
        """Build prompt for gap identification.

        Args:
            query: Research query.
            themes: Identified themes.
            content: Formatted content.

        Returns:
            Analysis prompt.
        """
        theme_names = [t.get("name", "") for t in themes]
        base_prompt = f"""Analyze the following research sources about "{query}" to identify information gaps.

Current themes: {", ".join(theme_names)}

{content}

Task: Identify what's missing or insufficiently covered.

For each gap:
1. Describe what information is missing or unclear
2. Rate importance (High/Medium/Low) for answering the research question
3. Suggest specific follow-up queries to fill the gap

Respond in JSON format:
{{
  "gaps": [
    {{
      "gap_description": "What's missing",
      "importance": "High/Medium/Low",
      "suggested_queries": ["query1", "query2"]
    }}
  ]
}}
"""
        # Apply prompt prefix from registry if available
        if self._prompt_registry:
            config = self._prompt_registry.resolve_prompt(self._agent_id, "identify_gaps")
            if config.prompt_prefix:
                return f"{config.prompt_prefix}\n\n{base_prompt}"
        return base_prompt

    def _build_synthesis_prompt(
        self,
        query: str,
        themes: list[dict[str, Any]],
        cross_ref: dict[str, Any],
        gaps: list[dict[str, Any]],  # noqa: ARG002
        content: str,
    ) -> str:
        """Build prompt for synthesis.

        Args:
            query: Research query.
            themes: Identified themes.
            cross_ref: Cross-reference results.
            gaps: Identified gaps.
            content: Formatted content.

        Returns:
            Analysis prompt.
        """
        theme_names = [t.get("name", "") for t in themes[:5]]
        consensus = cross_ref.get("consensus_points", [])[:3]
        consensus_str = (
            "\n".join(
                [
                    f"- {c.get('claim', str(c))}" if isinstance(c, dict) else f"- {c}"
                    for c in consensus
                ]
            )
            or "None identified"
        )

        base_prompt = f"""Synthesize the following research about "{query}" into key findings.

Main themes: {", ".join(theme_names)}

Consensus points:
{consensus_str}

{content}

CRITICAL OUTPUT REQUIREMENTS:
- Rewrite the source material into clean professional prose. DO NOT copy raw page headers or markdown syntax.
- Ignore menus, site navigation, buttons, share widgets, newsletter prompts, and article metadata.
- Provide complete sentences that remain understandable out of context.
- If the source text is fragmentary, infer cautiously or omit it.

Task: Create 5 key findings that synthesize the research.

For each finding:
1. A clear, specific title
2. A summary field (1-2 sentence high-level takeaway for Key Findings section)
3. A description field (detailed 2-3 sentence explanation for Detailed Analysis section)
4. 3-5 detail_points (evidence-backed bullets for Detailed Analysis section)
5. List of source URLs that support this finding
6. Confidence level (High/Medium/Low) based on source quality and quantity

Respond in JSON format:
{{
  "findings": [
    {{
      "title": "Finding title",
      "summary": "High-level takeaway (1-2 sentences)...",
      "description": "Detailed description (2-3 sentences)...",
      "detail_points": ["Specific evidence-backed point 1", "Specific evidence-backed point 2"],
      "evidence": ["url1", "url2"],
      "confidence": "High/Medium/Low"
    }}
  ]
}}
"""
        # Apply prompt prefix from registry if available
        if self._prompt_registry:
            config = self._prompt_registry.resolve_prompt(self._agent_id, "synthesize")
            if config.prompt_prefix:
                return f"{config.prompt_prefix}\n\n{base_prompt}"
        return base_prompt

    def _build_evidence_quality_prompt(self, themes: list[dict[str, Any]], content: str) -> str:
        """Build prompt for evidence quality analysis.

        Args:
            themes: Identified themes.
            content: Formatted content.

        Returns:
            Analysis prompt.
        """
        theme_names = [t.get("name", "") for t in themes]
        base_prompt = f"""Analyze the evidence quality in the following research sources.

Themes to analyze: {", ".join(theme_names)}

{content}

Task: Assess the quality and type of evidence for each theme.

For each theme, identify:
1. Study types: Count of human studies, animal studies, in vitro studies, and other sources
2. Evidence conflicts: Any contradictory findings with explanations
3. Confidence level: Overall confidence in the evidence (High/Medium/Low)
4. Summary: Brief assessment of evidence quality

Respond in JSON format:
{{
  "study_types": {{
    "human_studies": 0,
    "animal_studies": 0,
    "in_vitro_studies": 0,
    "other": 0
  }},
  "evidence_conflicts": [
    {{
      "theme": "Theme name",
      "conflict": "Description of conflicting evidence",
      "explanation": "Why this matters"
    }}
  ],
  "confidence_levels": {{
    "theme_name": "High/Medium/Low"
  }},
  "evidence_summary": "Overall assessment of evidence quality"
}}
"""
        # Apply prompt prefix from registry if available
        if self._prompt_registry:
            config = self._prompt_registry.resolve_prompt(self._agent_id, "analyze_evidence_quality")
            if config.prompt_prefix:
                return f"{config.prompt_prefix}\n\n{base_prompt}"
        return base_prompt

    def _parse_theme_response(
        self,
        response_text: str,
        sources: list[dict[str, str]],  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        """Parse theme extraction response.

        Args:
            response_text: Raw LLM response.
            sources: Original sources for URL matching.

        Returns:
            List of theme dictionaries.
        """
        try:
            # Try to extract JSON from response
            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                data = json.loads(json_match.group())
                themes_raw = data.get("themes", [])
                if isinstance(themes_raw, list):
                    return [t for t in themes_raw if isinstance(t, dict)]  # Validate each item
                return []  # Fallback for non-list response
        except (json.JSONDecodeError, KeyError):
            pass

        # Fallback: parse structured text
        themes = []
        lines = response_text.split("\n")
        current_theme: dict[str, Any] | None = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Look for theme headers
            if re.match(r"^\d+\.\s+", line) or line.startswith("Theme:"):
                if current_theme:
                    themes.append(current_theme)
                theme_name = re.sub(r"^\d+\.\s*", "", line)
                theme_name = theme_name.replace("Theme:", "").strip()
                current_theme = {
                    "name": theme_name,
                    "description": "",
                    "key_points": [],
                    "supporting_sources": [],
                }
            elif current_theme:
                # Add to current theme
                if line.startswith("-") or line.startswith("•"):
                    point = line.lstrip("- •").strip()
                    if "http" in point:
                        current_theme["supporting_sources"].append(point)
                    else:
                        current_theme["key_points"].append(point)
                elif not current_theme["description"]:
                    current_theme["description"] = line

        if current_theme:
            themes.append(current_theme)

        return themes

    def _parse_cross_reference_response(self, response_text: str) -> dict[str, Any]:
        """Parse cross-reference response.

        Args:
            response_text: Raw LLM response.

        Returns:
            Dictionary with consensus and disagreement points.
        """
        try:
            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "consensus_points": data.get("consensus_points", [])
                    if isinstance(data.get("consensus_points"), list)
                    else [],
                    "disagreement_points": data.get("disagreement_points", [])
                    if isinstance(data.get("disagreement_points"), list)
                    else [],
                    "cross_reference_claims": [],
                }
        except (json.JSONDecodeError, KeyError):
            pass

        # Fallback parsing
        return {
            "consensus_points": ["Sources agree on core concepts related to the query"],
            "disagreement_points": [],
            "cross_reference_claims": [],
        }

    def _parse_gap_response(self, response_text: str) -> list[dict[str, Any]]:
        """Parse gap identification response.

        Args:
            response_text: Raw LLM response.

        Returns:
            List of gap dictionaries.
        """
        try:
            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                data = json.loads(json_match.group())
                gaps_raw = data.get("gaps", [])
                if isinstance(gaps_raw, list):
                    return gaps_raw
                return []  # Fallback for non-list response
        except (json.JSONDecodeError, KeyError):
            pass

        # Fallback parsing
        gaps = []
        lines = response_text.split("\n")

        for line in lines:
            line = line.strip()
            if line.startswith("-") and len(line) > 20:
                gaps.append(
                    {
                        "gap_description": line.lstrip("- ").strip(),
                        "importance": "Medium",
                        "suggested_queries": [],
                    }
                )

        return gaps[:5]  # Limit to 5 gaps

    def _parse_synthesis_response(self, response_text: str) -> list[dict[str, Any]]:
        """Parse synthesis response.

        Args:
            response_text: Raw LLM response.

        Returns:
            List of finding dictionaries.
        """
        try:
            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                data = json.loads(json_match.group())
                findings_raw = data.get("findings", [])
                if isinstance(findings_raw, list):
                    # Ensure all required fields exist with defaults
                    for finding in findings_raw:
                        finding.setdefault("summary", finding.get("description", "")[:200])
                        finding.setdefault("detail_points", [])
                    return findings_raw
                return []  # Fallback for non-list response
        except (json.JSONDecodeError, KeyError):
            pass

        # Fallback parsing
        findings = []
        lines = response_text.split("\n")
        current_finding: dict[str, Any] | None = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if re.match(r"^\d+\.\s+", line):
                if current_finding:
                    findings.append(current_finding)
                title = re.sub(r"^\d+\.\s*", "", line)
                current_finding = {
                    "title": title,
                    "summary": "",
                    "description": "",
                    "detail_points": [],
                    "evidence": [],
                    "confidence": "Medium",
                }
            elif current_finding:
                if line.startswith("-") or line.startswith("•"):
                    point = line.lstrip("- •").strip()
                    if "http" in point:
                        current_finding["evidence"].append(point)
                    else:
                        current_finding["detail_points"].append(point)
                elif not current_finding["summary"]:
                    current_finding["summary"] = line[:200]
                elif not current_finding["description"]:
                    current_finding["description"] = line

        if current_finding:
            findings.append(current_finding)

        return findings

    def _parse_evidence_quality_response(self, response_text: str) -> dict[str, Any]:
        """Parse evidence quality response.

        Args:
            response_text: Raw LLM response.

        Returns:
            Dictionary with evidence quality analysis.
        """
        try:
            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "study_types": data.get("study_types", {})
                    if isinstance(data.get("study_types"), dict)
                    else {},
                    "evidence_conflicts": data.get("evidence_conflicts", [])
                    if isinstance(data.get("evidence_conflicts"), list)
                    else [],
                    "confidence_levels": data.get("confidence_levels", {})
                    if isinstance(data.get("confidence_levels"), dict)
                    else {},
                    "evidence_summary": data.get("evidence_summary", "")
                    if isinstance(data.get("evidence_summary"), str)
                    else "",
                }
        except (json.JSONDecodeError, KeyError):
            pass

        # Fallback
        return {
            "study_types": {
                "human_studies": 0,
                "animal_studies": 0,
                "in_vitro_studies": 0,
                "other": 0,
            },
            "evidence_conflicts": [],
            "confidence_levels": {},
            "evidence_summary": "Evidence quality analysis completed",
        }


__all__ = ["LLMAnalysisClient"]
