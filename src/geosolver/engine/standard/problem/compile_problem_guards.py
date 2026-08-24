"""Compile problem guards once for evaluator reuse."""

from __future__ import annotations

from geosolver.engine.standard.interpreter.guards.compile import GuardIR, compile_guards

from geosolver.engine.standard.contracts.problem_bundle import ProblemBundle


def compile_problem_guards(bundle: ProblemBundle) -> tuple[GuardIR, ...]:
    """Compile all guard expressions in the problem bundle."""
    return tuple(compile_guards(bundle.spec.guards))

