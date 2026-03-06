"""Researcher agent implementation.

The researcher agent is responsible for:
- Executing independent research tasks
- Querying Tavily provider for sources
- Formatting results for aggregation
- Error handling and timeout management
"""

import asyncio
import time
from typing import Any

from cc_deep_research.config import Config
from cc_deep_research.models import SearchOptions
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.providers import SearchProvider


class ResearcherAgent:
    """Agent that executes independent research tasks.

    This agent handles:
    - Executing assigned research queries
    - Collecting sources from Tavily provider
    - Formatting results for aggregation
    - Error handling and timeout management
    """

    def __init__(
        self,
        config: Config,
        provider: SearchProvider,
        monitor: ResearchMonitor | None = None,
    ) -> None:
        """Initialize researcher agent.

        Args:
            config: Application configuration.
            provider: Search provider to use for research.
        """
        self._config = config
        self._provider = provider
        self._monitor = monitor

    async def execute_task(
        self,
        task: dict[str, str],
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        """Execute a research task.

        Args:
            task: Task dictionary with 'query' and optional parameters.
            timeout: Maximum execution time in seconds.

        Returns:
            Result dictionary with sources and metadata.

        Raises:
            asyncio.TimeoutError: If execution exceeds timeout.
            ResearchExecutionError: If execution fails.
        """
        query = task.get("query", "")
        task_id = task.get("task_id", "")

        try:
            # Execute search with timeout
            result = await asyncio.wait_for(
                self._execute_search(query),
                timeout=timeout,
            )

            return {
                "task_id": task_id,
                "query": query,
                "status": "success",
                "sources": result["sources"],
                "source_count": result["source_count"],
                "execution_time_ms": result["execution_time_ms"],
            }

        except TimeoutError:
            if self._monitor:
                self._monitor.record_search_query(
                    query=query,
                    provider=self._provider.get_provider_name(),
                    result_count=0,
                    duration_ms=int(timeout * 1000),
                    status="timeout",
                )
                self._monitor.record_tool_call(
                    tool_name=f"{self._provider.get_provider_name()}.search",
                    status="timeout",
                    duration_ms=int(timeout * 1000),
                    query=query,
                )
            return {
                "task_id": task_id,
                "query": query,
                "status": "timeout",
                "error": f"Execution timed out after {timeout}s",
                "sources": [],
                "source_count": 0,
            }
        except Exception as e:
            if self._monitor:
                self._monitor.record_search_query(
                    query=query,
                    provider=self._provider.get_provider_name(),
                    result_count=0,
                    duration_ms=0,
                    status="error",
                    error=str(e),
                )
                self._monitor.record_tool_call(
                    tool_name=f"{self._provider.get_provider_name()}.search",
                    status="error",
                    duration_ms=0,
                    query=query,
                    error=str(e),
                )
            return {
                "task_id": task_id,
                "query": query,
                "status": "error",
                "error": str(e),
                "sources": [],
                "source_count": 0,
            }

    async def _execute_search(
        self,
        query: str,
    ) -> dict[str, Any]:
        """Execute search query using configured provider.

        Args:
            query: Search query string.

        Returns:
            Dictionary with sources and metadata.
        """
        start_time = time.time()
        provider_name = self._provider.get_provider_name()

        if self._monitor:
            self._monitor.record_tool_call(
                tool_name=f"{provider_name}.search",
                status="started",
                duration_ms=0,
                query=query,
            )

        # Create search options
        options = SearchOptions(
            max_results=self._config.tavily.max_results,
            search_depth=self._config.search.depth,
            include_raw_content=True,
        )

        # Execute search
        search_result = await self._provider.search(query, options)

        # Extract sources list from SearchResult
        sources = search_result.results

        execution_time_ms = (time.time() - start_time) * 1000

        if self._monitor:
            self._monitor.record_search_query(
                query=query,
                provider=provider_name,
                result_count=len(sources),
                duration_ms=int(execution_time_ms),
                status="success",
            )
            self._monitor.record_tool_call(
                tool_name=f"{provider_name}.search",
                status="success",
                duration_ms=int(execution_time_ms),
                query=query,
                result_count=len(sources),
            )

        return {
            "sources": sources,
            "source_count": len(sources),
            "execution_time_ms": execution_time_ms,
        }

    async def execute_multiple_tasks(
        self,
        tasks: list[dict[str, str]],
        timeout: float = 120.0,
    ) -> list[dict[str, Any]]:
        """Execute multiple research tasks in parallel.

        Args:
            tasks: List of task dictionaries.
            timeout: Maximum execution time per task.

        Returns:
            List of result dictionaries.
        """
        # Execute all tasks in parallel
        task_coroutines = [self.execute_task(task, timeout) for task in tasks]

        results = await asyncio.gather(*task_coroutines, return_exceptions=True)

        # Handle any exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Create error result
                processed_results.append(
                    {
                        "task_id": tasks[i].get("task_id", ""),
                        "query": tasks[i].get("query", ""),
                        "status": "error",
                        "error": str(result),
                        "sources": [],
                        "source_count": 0,
                    }
                )
            else:
                processed_results.append(result)  # type: ignore[arg-type]

        return processed_results


class ResearchExecutionError(Exception):
    """Exception raised when research execution fails."""

    def __init__(
        self,
        message: str,
        query: str | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.query = query
        self.original_error = original_error


__all__ = [
    "ResearcherAgent",
    "ResearchExecutionError",
]
