"""Compatibility wrapper for legacy solve_simple API."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from geosolver._internal.solver.public.legacy_utils import get_hp_values, get_solution_str
from geosolver._internal.solver.public.solve import solve as _solve_impl


def solve(
    n: int,
    f: Callable[[list[float]], list[float]],
    v: list[float],
    bounds: list[tuple[float, float]] | None = None,
    precision: int = 15,
    find_all: bool = True,
    max_solutions: int = 10,
    time_limit: float = 300.0,
    verbose: bool = True,
    f_mp: Callable | None = None,
    f_fast: Callable | None = None,
    two_pass: bool = True,
    bounds_margin: float = 3.0,
    ans: Callable | None = None,
    seed: int | None = None,
) -> tuple[list[float], dict[str, Any]]:
    """Legacy solve_simple entrypoint routed to internal public solve."""
    return _solve_impl(
        n=n,
        f=f,
        v=v,
        bounds=bounds,
        precision=precision,
        find_all=find_all,
        max_solutions=max_solutions,
        time_limit=time_limit,
        verbose=verbose,
        f_mp=f_mp,
        f_fast=f_fast,
        two_pass=two_pass,
        bounds_margin=bounds_margin,
        ans=ans,
        seed=seed,
    )
