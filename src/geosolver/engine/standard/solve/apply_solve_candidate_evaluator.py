"""Select and reorder solve candidates using guard-aware evaluator output."""

from __future__ import annotations

from typing import Any, Callable

from geosolver.engine.standard.interpreter.execution.interpreter_helpers import (
    CandidateEval,
    select_feasible_candidate,
)


def apply_solve_candidate_evaluator(
    ordered: list[list[Any]],
    *,
    candidate_evaluator: Callable[[list[Any]], CandidateEval] | None,
) -> tuple[list[list[Any]], int, int | None, int | None, int, list[str]]:
    """Evaluate and reorder candidate solutions by guard-aware feasibility."""
    if not callable(candidate_evaluator):
        return ordered, 0, None, None, 0, []

    candidate_evals: list[CandidateEval] = []
    candidate_eval_indices: list[int] = []
    error_count = 0
    error_examples: list[str] = []
    for source_index, solution in enumerate(ordered):
        try:
            candidate_evals.append(candidate_evaluator(list(solution)))
            candidate_eval_indices.append(int(source_index))
        except Exception as exc:
            error_count += 1
            if len(error_examples) < 3:
                error_examples.append(str(exc))
            continue

    guard_feasible_count = int(sum(1 for entry in candidate_evals if entry.guard_ok))
    selected = select_feasible_candidate(candidate_evals, mode="solve")
    if selected is None:
        return ordered, guard_feasible_count, None, None, error_count, error_examples

    selected_eval_index = next(
        (index for index, candidate in enumerate(candidate_evals) if candidate is selected),
        -1,
    )
    selected_index = (
        candidate_eval_indices[selected_eval_index]
        if 0 <= selected_eval_index < len(candidate_eval_indices)
        else -1
    )
    if selected_index < 0 or selected_index >= len(ordered):
        return ordered, guard_feasible_count, None, None, error_count, error_examples

    reordered: list[list[Any]] = [list(ordered[selected_index])]
    for index, solution in enumerate(ordered):
        if index == selected_index:
            continue
        reordered.append(list(solution))
    selected_candidate_id = selected.candidate_id
    return reordered, guard_feasible_count, 0, selected_candidate_id, error_count, error_examples
