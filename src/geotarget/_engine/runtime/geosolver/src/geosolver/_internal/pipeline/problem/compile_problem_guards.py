"""Compile problem guards once for evaluator reuse."""

from __future__ import annotations

from geosolver._internal.autosolve.guards.compile import GuardIR, compile_guards

from geosolver._internal.pipeline.contracts.problem_bundle import ProblemBundle


def compile_problem_guards(bundle: ProblemBundle) -> tuple[GuardIR, ...]:
    """Compile all guard expressions in the problem bundle."""
    return tuple(compile_guards(bundle.spec.guards))

