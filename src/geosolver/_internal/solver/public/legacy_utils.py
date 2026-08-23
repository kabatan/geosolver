"""Compatibility wrappers for legacy solver utility exports."""

from __future__ import annotations

from typing import Any

from .solution_format import get_hp_values as _get_hp_values_impl
from .solution_format import get_solution_str as _get_solution_str_impl


def get_solution_str(*args: Any, **kwargs: Any) -> Any:
    """Backward-compatible wrapper for legacy solution string formatting."""
    return _get_solution_str_impl(*args, **kwargs)


def get_hp_values(*args: Any, **kwargs: Any) -> Any:
    """Backward-compatible wrapper for legacy high-precision value extraction."""
    return _get_hp_values_impl(*args, **kwargs)
