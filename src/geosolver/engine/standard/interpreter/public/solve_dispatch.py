"""Helpers to dispatch solve-branch execution in autosolve interpreter."""

from __future__ import annotations

LEGACY_BACKEND_COMPAT_ONLY = True

from typing import Any, Callable, Dict, List, Optional, Tuple

from geosolver.engine.standard.interpreter.guards.compile import GuardIR
from geosolver.engine.standard.interpreter.execution.interpreter_helpers import (
    CandidateEval,
    select_feasible_candidate,
)
from geosolver.runtime.logging.compat import emit_legacy_log
from geosolver.engine.standard.solve import solve


FAST_MODE_TIME_LIMIT_MAX = 200.0
FALLBACK_TIME_FLOOR = 40.0
FALLBACK_TIME_SCALE = 0.6
FALLBACK_TIME_DEFAULT = 60.0
RETRY_MIN_REMAINING_TIME = 12.0


def _classify_solve_retry_reason(
    solve_info: Dict[str, Any],
    solve_result: Optional[List[Any]],
) -> str:
    if solve_result is None:
        return "no_solution_candidate"
    if not bool(solve_info.get("success", False)):
        return "solver_reported_failure"
    guard_feasible_count = int(solve_info.get("guard_feasible_count", 0) or 0)
    if guard_feasible_count <= 0 and "guard_feasible_count" in solve_info:
        return "guard_not_feasible"
    residual_value = solve_info.get("residual_norm")
    residual_tolerance = solve_info.get("residual_tolerance")
    try:
        if residual_value is not None and residual_tolerance is not None:
            if residual_value > residual_tolerance:
                return "residual_not_converged"
    except Exception:
        pass
    return "unknown"


def _fallback_time_limit(remaining_time_value: float | None) -> float | None:
    if remaining_time_value is None:
        return float(FALLBACK_TIME_DEFAULT)
    try:
        remaining = max(0.0, float(remaining_time_value))
    except Exception:
        return float(FALLBACK_TIME_DEFAULT)
    if remaining <= 0.0:
        return 0.0
    scaled = max(float(FALLBACK_TIME_FLOOR), remaining * float(FALLBACK_TIME_SCALE))
    return min(remaining, scaled)


def _is_solution_vector(values: Any) -> bool:
    return isinstance(values, (list, tuple)) and (
        len(values) == 0 or not isinstance(values[0], (list, tuple))
    )


def _normalize_all_solutions(all_solutions: Any, best_solution: Any) -> List[List[Any]]:
    if _is_solution_vector(all_solutions):
        return [list(all_solutions)]

    if isinstance(all_solutions, list):
        normalized: List[List[Any]] = []
        for solution in all_solutions:
            if _is_solution_vector(solution):
                normalized.append(list(solution))
        if normalized:
            return normalized

    if _is_solution_vector(best_solution):
        return [list(best_solution)]
    return []


def _apply_candidate_selection(
    *,
    solve_result: Optional[List[Any]],
    solve_info: Dict[str, Any],
    candidate_evaluator: Callable[[List[Any]], CandidateEval] | None,
    residual_tolerance: Optional[float] = None,
) -> tuple[Optional[List[Any]], Dict[str, Any]]:
    existing_index = solve_info.get("selected_solution_index")
    if isinstance(existing_index, int) and existing_index >= 0:
        all_solutions = _normalize_all_solutions(solve_info.get("all_solutions"), solve_result)
        if existing_index < len(all_solutions):
            solve_result = list(all_solutions[existing_index])
            solve_info.setdefault("selected_candidate_id", solve_info.get("best_candidate_id"))
            solve_info.setdefault("selection_residual_source", "selected_solution")
        return solve_result, solve_info

    if not callable(candidate_evaluator):
        return solve_result, solve_info

    all_solutions = _normalize_all_solutions(solve_info.get("all_solutions"), solve_result)
    candidate_evals: list[CandidateEval] = []
    for solution in all_solutions:
        try:
            candidate_evals.append(candidate_evaluator(list(solution)))
        except Exception:
            continue

    if residual_tolerance is not None:
        valid_evals = [
            c for c in candidate_evals
            if c.guard_ok and c.residual_norm <= residual_tolerance
        ]
    else:
        valid_evals = [c for c in candidate_evals if c.guard_ok]

    selected = select_feasible_candidate(valid_evals, mode="solve")
    if selected is not None:
        selected_index = next(
            (
                index
                for index, entry in enumerate(candidate_evals)
                if entry is selected
            ),
            -1,
        )
        if 0 <= selected_index < len(all_solutions):
            solve_result = list(all_solutions[selected_index])
            solve_info["selected_solution_index"] = int(selected_index)
        else:
            solve_result = list(selected.values)
        if residual_tolerance is None or selected.residual_norm <= residual_tolerance:
            solve_info["residual_norm"] = selected.residual_norm
        solve_info["guard_violations"] = list(selected.guard_violations)
        solve_info["selected_candidate_id"] = selected.candidate_id
        solve_info["selection_residual_source"] = "candidate_eval"
        
    solve_info["guard_feasible_count"] = int(sum(1 for entry in candidate_evals if entry.guard_ok))
    solve_info["candidate_count"] = int(len(candidate_evals))
    return solve_result, solve_info


def dispatch_solve(
    *,
    direct_eval_done: bool,
    initial_solution: Optional[List[Any]],
    initial_info: Optional[Dict[str, Any]],
    quick_numeric_solve: Callable[[], Tuple[Optional[List[Any]], Optional[Dict[str, Any]]]],
    precision: int,
    time_limit: Optional[float],
    f_func_fast: Optional[Callable[[List[Any]], List[float]]],
    avoid_fast: bool,
    f_func: Callable[[List[Any]], List[float]],
    n_vars: int,
    v_numeric: List[float],
    bounds: Optional[List[Tuple[float, float]]],
    solve_precision: int,
    verbose: bool,
    remaining_time: Callable[[], Optional[float]],
    f_func_hp: Optional[Callable[[List[Any]], List[Any]]],
    ans_func: Optional[Callable[[List[Any]], Any]],
    needs_all_solutions: bool,
    max_solutions: int,
    random_solve_fallback: Callable[
        [Optional[float], bool, bool],
        Tuple[Optional[List[Any]], Optional[Dict[str, Any]]],
    ],
    candidate_evaluator: Callable[[List[Any]], CandidateEval] | None = None,
    residual_tolerance: Optional[float] = None,
    variable_names: Optional[List[str]] = None,
    guard_irs: Optional[List[GuardIR]] = None,
) -> Tuple[Optional[List[Any]], Dict[str, Any]]:
    """Run solve branch main dispatch while preserving legacy behavior."""
    solve_result = initial_solution
    solve_info = initial_info or {}

    if not direct_eval_done:
        solve_result, solve_info_candidate = quick_numeric_solve()
        solve_info = solve_info_candidate or {}
        if precision is not None and int(precision) >= 30:
            solve_result, solve_info = None, {}

    if (not direct_eval_done) and (solve_result is None or not solve_info.get("success")):
        f_fast_for_solve = f_func_fast
        try:
            use_fast = f_fast_for_solve is not None
            if (precision is not None) and (int(precision) >= 30):
                use_fast = use_fast and (
                    time_limit is not None and float(time_limit) <= FAST_MODE_TIME_LIMIT_MAX
                )
            if avoid_fast:
                use_fast = False
            if not use_fast:
                f_fast_for_solve = None
        except Exception:
            pass

        if verbose:
            try:
                rt = remaining_time()
                emit_legacy_log(f"[run_ir] calling solve() with time_limit={rt}")
            except Exception:
                pass

        best_solution, solve_info = solve(
            n=n_vars,
            f=f_func,
            f_fast=f_fast_for_solve,
            v=v_numeric,
            bounds=bounds,
            precision=solve_precision,
            verbose=verbose,
            time_limit=remaining_time(),
            f_mp=f_func_hp,
            ans=ans_func,
            find_all=needs_all_solutions,
            max_solutions=max_solutions,
            candidate_evaluator=candidate_evaluator,
            variable_names=variable_names,
            guard_irs=guard_irs,
        )
        solve_result = best_solution
        if solve_info is None:
            solve_info = {}
        solve_info["all_solutions"] = _normalize_all_solutions(
            solve_info.get("all_solutions"),
            best_solution,
        )
        solve_result, solve_info = _apply_candidate_selection(
            solve_result=solve_result,
            solve_info=solve_info,
            candidate_evaluator=candidate_evaluator,
            residual_tolerance=residual_tolerance,
        )

        try:
            retry_without_fast = f_fast_for_solve is not None
        except Exception:
            retry_without_fast = False
        if retry_without_fast and (solve_result is None or not solve_info.get("success")):
            solve_info["retry_reason"] = _classify_solve_retry_reason(solve_info, solve_result)
            rem = remaining_time()
            if rem is None or rem >= RETRY_MIN_REMAINING_TIME:
                if verbose:
                    try:
                        emit_legacy_log("[run_ir] retry solve() without fast function")
                    except Exception:
                        pass
                best_solution, solve_info = solve(
                    n=n_vars,
                    f=f_func,
                    f_fast=None,
                    v=v_numeric,
                    bounds=bounds,
                    precision=solve_precision,
                    verbose=verbose,
                    time_limit=remaining_time(),
                    f_mp=f_func_hp,
                    ans=ans_func,
                    find_all=needs_all_solutions,
                    max_solutions=max_solutions,
                    candidate_evaluator=candidate_evaluator,
                    variable_names=variable_names,
                    guard_irs=guard_irs,
                )
                solve_result = best_solution
                if solve_info is None:
                    solve_info = {}
                solve_info["all_solutions"] = _normalize_all_solutions(
                    solve_info.get("all_solutions"),
                    best_solution,
                )
                solve_result, solve_info = _apply_candidate_selection(
                    solve_result=solve_result,
                    solve_info=solve_info,
                    candidate_evaluator=candidate_evaluator,
                    residual_tolerance=residual_tolerance,
                )

    if solve_result is None or not bool(solve_info.get("success", False)):
        fallback_attempts = [
            (False, False),
            (True, True),
        ]
        for aggressive, ignore_guards in fallback_attempts:
            rem = remaining_time()
            fallback_tl = rem if aggressive else _fallback_time_limit(rem)
            if fallback_tl is not None and fallback_tl <= 0.0:
                continue
            fallback_solution, fallback_info = random_solve_fallback(
                fallback_tl,
                aggressive,
                ignore_guards,
            )
            if fallback_info is None:
                fallback_info = {}
            fallback_info["all_solutions"] = _normalize_all_solutions(
                fallback_info.get("all_solutions"),
                fallback_solution,
            )
            fallback_solution, fallback_info = _apply_candidate_selection(
                solve_result=fallback_solution,
                solve_info=fallback_info,
                candidate_evaluator=candidate_evaluator,
                residual_tolerance=residual_tolerance,
            )
            if fallback_solution is not None and bool(fallback_info.get("success", False)):
                fallback_info["retry_strategy"] = (
                    "random_fallback_aggressive" if aggressive else "random_fallback"
                )
                solve_result = fallback_solution
                solve_info = fallback_info
                break
            if solve_result is None and fallback_solution is not None:
                fallback_info["retry_strategy"] = "random_fallback_candidate"
                solve_result = fallback_solution
                solve_info = fallback_info

    if isinstance(solve_info, dict):
        solve_info["all_solutions"] = _normalize_all_solutions(
            solve_info.get("all_solutions"),
            solve_result,
        )
        solve_result, solve_info = _apply_candidate_selection(
            solve_result=solve_result,
            solve_info=solve_info,
            candidate_evaluator=candidate_evaluator,
            residual_tolerance=residual_tolerance,
        )
    return solve_result, solve_info
