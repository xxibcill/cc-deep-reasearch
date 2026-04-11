# Type Errors by File

## Quick Reference

This document provides a per-file breakdown of mypy errors with specific fix instructions.

---

## agents/

### `agents/analyzer.py` (5 errors)

| Line | Error | Fix |
|------|-------|-----|
| 189 | Missing type parameters for generic type "list" | `sources: list[str]` → check actual usage |
| 226 | `re.sub` overload mismatch | `re.sub(pattern, str(repl), string, flags)` - ensure repl is str |
| 262 | Argument type `list[str] \| list[dict]` to `_build_claims` | Add overload or broaden param type |
| 331 | Return type `list[str]` expected `list[AnalysisGap]` | Fix return statement to return AnalysisGap objects |
| 390 | Return type `list[AnalysisGap]` expected `list[str]` | Fix return statement to return strings |

### `agents/ai_analysis_service.py` (2 errors)

| Line | Error | Fix |
|------|-------|-----|
| 161 | `LLMRouter \| None` has no attribute `execute` | Add `if router is None: raise...` before call |
| 168 | Returning `Any` from function | Cast/assert return type |

### `agents/planner.py` (5 errors)

| Line | Error | Fix |
|------|-------|-----|
| 197 | `stop_reason = None` but type is `str` | `stop_reason: str \| None = None` |
| 202 | Same | Same fix |
| 207 | Same | Same fix |
| 212 | Same | Same fix |
| 864 | `str \| Callable` has no `.strip()` | `if callable, call it: val = val() if callable else val` |

### `agents/report_quality_evaluator.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 272 | Returning `Any` | Cast return value to `dict[str, Any]` |

### `agents/report_refiner.py` (2 errors)

| Line | Error | Fix |
|------|-------|-----|
| 271 | Need type annotation for `result` | `result: list[str] = []` |
| 295 | Need type annotation for `current_paragraph` | `current_paragraph: list[str] = []` |

### `agents/reporter.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 457 | `str` to `dict[str, Any]` assignment | Check logic - likely wrong variable |

### `agents/research_lead.py` (2 errors)

| Line | Error | Fix |
|------|-------|-----|
| 141 | Unsupported `+` for "object" and "int" | Cast object to int or fix arithmetic |
| 144 | Expected iterable as variadic | `*base_strategy["tasks"]` - ensure it's a list |

---

## cli/

### `cli/main.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 46 | Call to untyped function | Add type annotations to `register_content_gen_commands` |

### `cli/research.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 203 | Unexpected keyword `execution_mode` | Remove or fix keyword arg |

### `cli/session.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 216 | `str` to `Path` assignment | `Path(session_id)` if it's a path |

---

## config/

### `config/schema.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 20 | List item `str \| None` expected `str` | Filter out None or use `str \| None` as element type |

---

## content_gen/

### `content_gen/agents/angle.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 116 | Missing type parameters for `dict` | `dict[str, Any]` instead of bare `dict` |

### `content_gen/agents/backlog.py` (2 errors)

| Line | Error | Fix |
|------|-------|-----|
| 174 | Missing type parameters for `dict` | `dict[str, Any]` |
| 259 | Unused type:ignore comment | Remove it |

### `content_gen/agents/packaging.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 128 | Missing type parameters for `dict` | `dict[str, Any]` |

### `content_gen/agents/performance.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 112 | Missing type parameters for `dict` | `dict[str, Any]` |

### `content_gen/agents/production.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 102 | Missing type parameters for `dict` | `dict[str, Any]` |

### `content_gen/agents/research_pack.py` (2 errors)

| Line | Error | Fix |
|------|-------|-----|
| 105 | Missing type parameters for `list` | `list[str]` or appropriate type |
| 155 | Missing type parameters for `dict` | `dict[str, Any]` |

### `content_gen/agents/scripting.py` (2 errors)

| Line | Error | Fix |
|------|-------|-----|
| 852 | `CoreInputs \| None` to `CoreInputs` arg | Add `if core_inputs is None: raise...` |
| 997 | Unused type:ignore comment | Remove it |

### `content_gen/agents/visual.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 117 | Missing type parameters for `dict` | `dict[str, Any]` |

### `content_gen/cli.py` (7 errors)

| Line | Error | Fix |
|------|-------|-----|
| 100 | Dict entry type mismatch | Fix dict literal types |
| 532 | Missing type parameters for `dict` | `dict[str, Any]` |
| 651 | Unused type:ignore | Remove |
| 658 | Unused type:ignore | Remove |
| 862 | `AngleOption` not defined | Add import |
| 862 | `ScriptVersion` not defined | Add import |
| 901 | `ScriptVersion` not defined | Add import |
| 909 | `ScriptVersion` not defined | Add import |
| 923 | `AngleOption` not defined | Add import |

### `content_gen/orchestrator.py` (8 errors)

| Line | Error | Fix |
|------|-------|-----|
| 67 | Returning `Any` | Cast return |
| 226 | `str` to `ScriptVersion \| None` | Fix assignment logic |
| 228 | Same | Same |
| 230 | Same | Same |
| 232 | Same | Same |
| 238 | Same | Same |
| 240 | Same | Same |
| 242 | Same | Same |
| 244 | Same | Same |
| 422 | Returning `Any` | Cast return |
| 726 | Missing type parameters for `list` | `list[Any]` |
| 785 | Missing type parameters for `dict` | `dict[str, Any]` |
| 872 | Returning `Any` | Cast return |

### `content_gen/prompts/performance.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 77 | Missing type parameters for `dict` | `dict[str, Any]` |

### `content_gen/router.py` (3 errors)

| Line | Error | Fix |
|------|-------|-----|
| 122 | Returning `Any` | Cast return |
| 177 | Missing type annotation for argument | Add type hint |
| 337 | Missing type annotation for argument | Add type hint |
| 569 | `WebSocket` to `ServerProtocol` arg | Add type: ignore or fix arg type |

### `content_gen/storage/backlog_store.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 38 | Missing type parameters for `dict` | `dict[str, Any]` |

---

## dashboard_app.py (11 errors)

| Line | Error | Fix |
|------|-------|-----|
| 93 | `dict` to `tuple` assignment | This is a logic error - `session` is tuple but being treated as dict |
| 94 | Tuple index with str | Use integer index or fix data structure |
| 97 | Same | Same |
| 98-104 | Tuple has no `.get()` | Use index access or fix data structure |
| 107 | Tuple getitem with str | Use integer index |
| 236 | Pandas stubs missing | `pip install pandas-stubs` or add `# type: ignore` |

---

## llm/

### `llm/anthropic.py` (2 errors)

| Line | Error | Fix |
|------|-------|-----|
| 166 | `list[dict[str, str]]` to `Iterable[MessageParam]` | Cast messages or use proper type |
| 167 | `str \| None` to system param | Cast or use proper type |

### `llm/cerebras.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 387 | Returning `Any` | Cast return to `str` |

### `llm/openrouter.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 396 | Returning `Any` | Cast return to `str` |

---

## models/

### `models/planning.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 142 | `ResearchSubtask \| None` has no `.status` | Add None check: `if subtask: subtask.status` |

### `models/search.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 144 | `PydanticDescriptorProxy` not callable | This is a Pydantic internal issue - may need `# type: ignore` |

---

## monitoring.py (5 errors)

| Line | Error | Fix |
|------|-------|-----|
| 715 | Need type annotation for `domains_by_family` | `domains_by_family: dict[str, list[str]] = {}` |
| 1301 | Returning `Any` | Cast return |
| 1441 | `emit_event` status arg type | Ensure status is `str` - add conversion |
| 1474 | Returning `Any` | Cast return |
| 1488 | Returning `Any` | Cast return |

---

## orchestration/

### `orchestration/agent_access.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 8 | Module doesn't export `ReportRefinerAgent` | Add to `__all__` or use proper import path |

### `orchestration/llm_route_planner.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 390 | Dict entry 3 type `str: int` expected `str: str \| list[str] \| dict` | Fix dict literal or cast value |

### `orchestration/planner_orchestrator.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 62 | `LocalResearchTeam` not defined | Add import or define |

### `orchestration/planning.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 206 | `list[QueryFamily]` to `list[QueryFamily \| str]` | Use `Sequence` instead of `list` |

### `orchestration/source_collection.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 401 | `object` to `_SequentialCollector` arg | Fix argument type or cast |

### `orchestration/source_collection_parallel.py` (2 errors)

| Line | Error | Fix |
|------|-------|-----|
| 31 | Missing type parameters for `dict` | `dict[str, Any]` |
| 144 | `str \| None` to `str` assignment | Add None check or default value |

### `orchestration/task_dispatcher.py` (3 errors)

| Line | Error | Fix |
|------|-------|-----|
| 113 | `TaskExecutionResult \| BaseException` to `TaskExecutionResult` | Already handled in code via isinstance check - mypy issue |
| 114 | BaseException has no `.success` | Same - already caught by isinstance |
| 119 | BaseException has no `.error_message` | Same |

**Note**: These 3 errors are false positives - the code already checks `isinstance(result, Exception)` before accessing attributes. The mypy type narrowing isn't catching it. Fix: use `# type: ignore` or restructure.

---

## post_validator.py (2 errors)

| Line | Error | Fix |
|------|-------|-----|
| 84 | Need type annotation for `issues` | `issues: list[str] = []` |
| 161 | Need type annotation for `warnings` | `warnings: list[str] = []` |

---

## research_runs/

### `research_runs/output.py` (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 22 | Missing type annotation for argument | Add type hint |

### `research_runs/service.py` (4 errors)

| Line | Error | Fix |
|------|-------|-----|
| 73 | Incompatible default for `runner` arg | Fix runner type or default |
| 200 | `TeamResearchOrchestrator` to `PlannerResearchOrchestrator` | Fix variable type or assignment |
| 213 | `PlannerResearchOrchestrator` to `TeamResearchOrchestrator` | Same fix |
| 267 | `EventRouter \| None` has no `.stop()` | Add None check |

---

## search_cache.py (1 error)

| Line | Error | Fix |
|------|-------|-----|
| 447 | `Awaitable[SearchResult]` to `Coroutine` arg | The issue is `asyncio.create_task` expects coroutine but gets awaitable |

---

## telemetry/

### `telemetry/live.py` (9 errors)

| Line | Error | Fix |
|------|-------|-----|
| 127 | Returning `Any` | Cast return |
| 133 | Returning `Any` | Cast return |
| 135 | Returning `Any` | Cast return |
| 417 | Returning `Any` | Cast return |
| 427 | Returning `Any` | Cast return |
| 455 | Returning `Any` | Cast return |
| 711 | Returning `Any` | Cast return |
| 740 | Returning `Any` | Cast return |
| 765 | Returning `Any` | Cast return |

### `telemetry/query.py` (2 errors)

| Line | Error | Fix |
|------|-------|-----|
| 20 | Missing return type annotation | Add `-> str` |
| 459 | Returning `Any` | Cast return |

### `telemetry/tree.py` (3 errors)

| Line | Error | Fix |
|------|-------|-----|
| 423 | Invalid index type `Any \| None` | Add check or cast |
| 1078 | `dict[str, Any] \| None` to `dict` | Add None check |
| 1146 | `dict[str, int]` to `list[dict]` | Fix assignment target |

---

## web_server.py (6 errors)

| Line | Error | Fix |
|------|-------|-----|
| 193 | Missing return type annotation | Add return type |
| 284 | Returning `Any` | Cast return |
| 705 | `to_thread` callable arg type | Fix callable signature |
| 754 | Missing type parameters for `dict` | `dict[str, Any]` |
| 1723 | Missing type parameters for `dict` | `dict[str, Any]` |
| 1787 | `WebSocket` to `ServerProtocol` arg | Add `# type: ignore` |

---

## tui.py (1 note)

Line 46 defines `ResearchRunView` - related to `cli/research.py:203` error about `execution_mode` keyword.

---

## Summary by File Count

| Files with Errors | Error Count |
|-------------------|-------------|
| content_gen/ | 19 |
| telemetry/ | 14 |
| dashboard_app.py | 11 |
| orchestration/ | 10 |
| agents/ | 10 |
| web_server.py | 6 |
| research_runs/ | 5 |
| llm/ | 4 |
| cli/ | 3 |
| models/ | 2 |
| monitoring.py | 5 |
| config/ | 1 |
| post_validator.py | 2 |
| search_cache.py | 1 |
| tui.py | 1 |
