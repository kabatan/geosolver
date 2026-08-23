"""Compatibility wrapper for legacy exact-identification API."""

from __future__ import annotations

from typing import Any, Callable

from geosolver._internal.solver.exact.legacy_api import (
    exact_algebraic as _exact_algebraic_impl,
)
from geosolver._internal.solver.exact.legacy_api import (
    identify as _identify_impl,
)
from geosolver._internal.solver.exact.legacy_api import (
    identify_exact_answers as _identify_exact_answers_impl,
)


def identify(value: Any, precision: int = 50) -> str:
    """Identify exact value representation for a numeric input."""
    return _identify_impl(value=value, precision=precision)


def exact_algebraic(value: Any, precision: int = 50, max_degree: int = 8, **kwargs: Any):
    """Compatibility shim for exact algebraic identification."""
    return _exact_algebraic_impl(value, precision=precision, max_degree=max_degree, **kwargs)


def identify_exact_answers(
    ans: Callable[..., Any],
    all_solutions: list[Any],
    precision: int,
    verbose: bool = True,
    residuals: list[Any] | None = None,
) -> dict[str, Any]:
    """Identify exact answers for solution candidates."""
    return _identify_exact_answers_impl(
        ans=ans,
        all_solutions=all_solutions,
        precision=precision,
        verbose=verbose,
        residuals=residuals,
    )
