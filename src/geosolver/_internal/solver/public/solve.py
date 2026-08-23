"""Public solve() orchestrator delegated to legacy parity pipeline."""

from collections.abc import Callable
from typing import Any

from geosolver._internal.autosolve.guards.compile import GuardIR
from geosolver._internal.autosolve.execution.interpreter_helpers import CandidateEval

from .legacy_solve_engine import run_legacy_solve_pipeline


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
    candidate_evaluator: Callable[[list[float]], CandidateEval] | None = None,
    variable_names: list[str] | None = None,
    guard_irs: list[GuardIR] | None = None,
) -> tuple[list[float], dict[str, Any]]:
    """Run legacy parity solve pipeline and return best solution + diagnostics."""
    return run_legacy_solve_pipeline(
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
        candidate_evaluator=candidate_evaluator,
        variable_names=variable_names,
        guard_irs=guard_irs,
    )
