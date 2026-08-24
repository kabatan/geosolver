"""Build structured candidate ledger for legacy solve diagnostics."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from mpmath import mp

from geosolver.engine.standard.interpreter.execution.interpreter_helpers import CandidateEval
from geosolver.engine.standard.precision.type_guards.high_precision_contamination_error import (
    HighPrecisionContaminationError,
)
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat
from geosolver.engine.standard.solver.evaluate_hp_residual import evaluate_hp_residual
from geosolver.engine.standard.solver.tracked_candidate import TrackedCandidate


def build_solve_candidate_ledger(
    *,
    ordered: Sequence[Sequence[Any] | TrackedCandidate],
    residual_norms: Sequence[Any],
    candidate_evaluator: Callable[[list[Any]], CandidateEval] | None,
    hp_path_enabled: bool,
    f_hp: Callable[[list[MPFloat]], Sequence[MPFloat]] | None = None,
    hp_targets: Sequence[MPFloat] | None = None,
    search_distribution: dict[str, Any] | None = None,
    max_items: int = 5,
) -> list[dict[str, Any]]:
    """Build top-k candidate diagnostics including optional HP residuals.

    FIX-0: Uses evaluate_hp_residual() as the single-source-of-truth
    HP residual evaluator to ensure consistency with acceptance and
    fail diagnostics.
    """
    ledger: list[dict[str, Any]] = []
    limit = max(0, int(max_items))
    for index, solution in enumerate(ordered[:limit]):
        candidate_id: int | None = None
        candidate_source: str | None = None
        if isinstance(solution, TrackedCandidate):
            candidate_id = solution.candidate_id
            candidate_source = solution.source
            values = list(solution.values)
        else:
            values = list(solution)
        try:
            residual_norm = residual_norms[index] if index < len(residual_norms) else mp.inf
        except Exception:
            residual_norm = mp.inf

        guard_ok = None
        guard_violations: list[str] = []
        objective_value: Any = None
        if callable(candidate_evaluator):
            try:
                eval_values = values if hp_path_enabled else [float(value) for value in values]
                evaluated = candidate_evaluator(eval_values)
                guard_ok = bool(evaluated.guard_ok)
                guard_violations = [str(entry) for entry in evaluated.guard_violations]
                if evaluated.objective_value is not None:
                    objective_value = evaluated.objective_value
            except Exception:
                guard_ok = None

        hp_residual: MPFloat | None = None
        hp_residual_error: str | None = None
        if hp_path_enabled and callable(f_hp) and hp_targets is not None:
            try:
                with high_precision_mode():
                    result = evaluate_hp_residual(
                        point=values,
                        f_hp=f_hp,
                        targets=hp_targets,
                    )
                if result.is_finite:
                    hp_residual = result.residual_norm
                else:
                    hp_residual_error = "hp_residual_non_finite"
            except HighPrecisionContaminationError:
                raise
            except Exception:
                hp_residual = None
                hp_residual_error = "hp_residual_error"

        entry: dict[str, Any] = {
            "rank": index + 1,
            "ledger_rank": index + 1,
            "values": values,
            "residual_norm": residual_norm,
            "guard_ok": guard_ok,
            "guard_violations": guard_violations,
            "objective_value": objective_value,
            "hp_residual_norm": hp_residual,
            "hp_residual_error": hp_residual_error,
            "search_distribution": (search_distribution if index == 0 else None),
        }
        if candidate_id is not None:
            entry["candidate_id"] = candidate_id
            entry["candidate_source"] = candidate_source
        ledger.append(entry)
    return ledger

