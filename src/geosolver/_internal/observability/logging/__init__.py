"""Structured logging utilities for solver observability."""

from .compat import emit_legacy_log
from .logger import StructuredLogger

__all__ = ["StructuredLogger", "emit_legacy_log"]
