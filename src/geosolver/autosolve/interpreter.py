"""Compatibility layer for legacy autosolve interpreter module."""

from typing import Any

from geosolver._internal.autosolve.execution import interpreter_impl as _impl
from geosolver._internal.autosolve.public.run_ir import run_ir as _run_ir_public
from geosolver.core.result import SolveResult


def _run_ir_impl(ir: Any, **kwargs: Any) -> SolveResult:
    """Compatibility entrypoint that delegates to internal implementation."""
    return _impl._run_ir_impl(ir, **kwargs)


def run_ir(ir: Any, **kwargs: Any) -> SolveResult:
    """Public entrypoint — always uses external pipeline."""
    return _run_ir_public(ir, **kwargs)


def __getattr__(name: str) -> Any:
    """Forward legacy helper symbols to the internal implementation module."""
    return getattr(_impl, name)
