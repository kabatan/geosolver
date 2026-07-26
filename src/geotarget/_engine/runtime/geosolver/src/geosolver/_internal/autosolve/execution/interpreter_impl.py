"""Autosolve run_ir implementation used by compatibility entrypoints."""

from __future__ import annotations

import time
from typing import Any

from geosolver._internal.autosolve.answer import (
    _eval_exact_to_mpf,
    _evaluate_answer_high_precision,
    _wrap_exact_value,
)
from geosolver._internal.autosolve.context import (
    _get_fast_geometry_context,
    _get_geometry_context,
    _get_high_precision_context,
)
from geosolver._internal.autosolve.guards import _evaluate_guards
from geosolver.core.result import SolveResult, SolveStatus

from .interpreter_helpers import _build_base_context, _infer_bounds, _load_spec
from .interpreter_modes import (
    _run_direct_without_variables,
    _run_solve,
)


def _run_ir_impl(ir: Any, **kwargs: Any) -> SolveResult:
    """Execute IR payload and return SolveResult without legacy recursion."""
    started_at = time.time()
    try:
        spec = _load_spec(ir)
    except Exception as exc:
        return SolveResult(
            status=SolveStatus.INVALID_INPUT,
            elapsed_time=time.time() - started_at,
            errors=[str(exc)],
        )

    precision = int(kwargs.get("precision", 50))
    time_limit = kwargs.get("time_limit")
    verbose = bool(kwargs.get("verbose", False))
    prefer_fast = bool(kwargs.get("prefer_fast", False))
    base_context = _build_base_context(prefer_fast=prefer_fast)
    var_names = spec.variables.resolved_names()

    if not var_names:
        result = _run_direct_without_variables(
            spec=spec,
            precision=precision,
            base_context=base_context,
        )
        result.elapsed_time = time.time() - started_at
        return result

    if spec.task == "solve":
        result = _run_solve(
            spec=spec,
            var_names=var_names,
            precision=precision,
            time_limit=time_limit,
            verbose=verbose,
            base_context=base_context,
        )
    else:
        result = SolveResult(status=SolveStatus.INVALID_INPUT, errors=[f"Unknown task: {spec.task}"])

    result.elapsed_time = time.time() - started_at
    return result


__all__ = [
    "_eval_exact_to_mpf",
    "_evaluate_answer_high_precision",
    "_evaluate_guards",
    "_get_fast_geometry_context",
    "_get_geometry_context",
    "_get_high_precision_context",
    "_infer_bounds",
    "_run_ir_impl",
    "_wrap_exact_value",
]
