"""Shared persistence primitives used by local storage backends."""

from cc_deep_research.persistence.files import atomic_write_json, atomic_write_text

__all__ = ["atomic_write_json", "atomic_write_text"]
