"""CLI compatibility exports."""

from .main import Config, ingest_telemetry_to_duckdb, main, subprocess
from .shared import resolve_parallel_mode_override as _resolve_parallel_mode_override

__all__ = [
    "Config",
    "_resolve_parallel_mode_override",
    "ingest_telemetry_to_duckdb",
    "main",
    "subprocess",
]
