"""High-precision contamination exception types."""

from __future__ import annotations


class HighPrecisionContaminationError(TypeError):
    """Raised when float-like contamination is detected on HP-critical paths."""
