"""Helpers for solve-branch result finalization."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from mpmath import mp

from geosolver.engine.standard.result import SolveResult, SolveStatus
from geosolver.problem.ir.compiler import safe_eval_expr_hp


def _converged_solution_indices(metadata: Dict[str, Any], total_solutions: int) -> List[int]:
    tolerance = metadata.get("residual_tolerance", 1e-6)
    try:
        tolerance_mpf = mp.mpf(tolerance)
    except Exception:
        tolerance_mpf = mp.mpf("1e-6")

    residuals_hp = metadata.get("solution_residuals_hp")
    residuals_float = metadata.get("solution_residuals_float")

    converged: List[int] = []
    for index in range(max(0, int(total_solutions))):
        residual_value = None
        if isinstance(residuals_hp, list) and index < len(residuals_hp):
            residual_value = residuals_hp[index]
        elif isinstance(residuals_float, list) and index < len(residuals_float):
            residual_value = residuals_float[index]

        if residual_value is None:
            continue
        try:
            residual_mpf = mp.mpf(residual_value)
            if mp.isfinite(residual_mpf) and residual_mpf <= tolerance_mpf:
                converged.append(index)
        except Exception:
            continue
    return converged


def answer_close(a: Any, b: Any) -> bool:
    """Return True if two numeric answers are close enough for deduplication."""
    try:
        da = mp.mpf(a)
        db = mp.mpf(b)
        if not (mp.isfinite(da) and mp.isfinite(db)):
            return False
        scale = max(mp.mpf(1), abs(da), abs(db))
        tol = mp.mpf("1e-8")
        return abs(da - db) <= tol * scale
    except Exception:
        return False


def _is_solution_vector(values: Any) -> bool:
    return isinstance(values, (list, tuple)) and (
        len(values) == 0 or not isinstance(values[0], (list, tuple))
    )


def _normalize_all_solutions(
    all_solutions: Any,
    fallback_solution: Any,
) -> List[List[Any]]:
    normalized: List[List[Any]] = []

    if _is_solution_vector(all_solutions):
        return [list(all_solutions)]

    if isinstance(all_solutions, list):
        for solution in all_solutions:
            if _is_solution_vector(solution):
                normalized.append(list(solution))
        if normalized:
            return normalized

    if _is_solution_vector(fallback_solution):
        return [list(fallback_solution)]

    return []


def _sanitize_answer_values(values: Any) -> List[Any]:
    if not isinstance(values, list):
        return []
    return [entry for entry in values if entry is not None]


def _diagnostic_converged_answers(
    *,
    raw_answer_values: Any,
    sanitized_answer_values: List[Any],
    all_solutions: List[List[Any]],
    converged_indices: set[int],
) -> List[Any]:
    diagnostics: List[Any] = []
    if isinstance(raw_answer_values, list) and len(raw_answer_values) == len(all_solutions):
        for index, value in enumerate(raw_answer_values):
            if index not in converged_indices or value is None:
                continue
            if any(answer_close(value, existing) for existing in diagnostics if existing is not None):
                continue
            diagnostics.append(value)
        return diagnostics
    if converged_indices:
        return list(sanitized_answer_values[: len(converged_indices)])
    return []


def _evaluate_answer_with_fallback(
    *,
    spec: Any,
    var_names: List[str],
    precision: int,
    solution: List[Any],
    hp_context: Dict[str, Any],
    evaluate_answer_high_precision: Callable[[Any, List[str], List[Any], int], Tuple[Any, Any, Any]],
    preprocess_hp_expr: Callable[[str], str],
    apply_fixed_points: Callable[[Dict[str, Any]], None],
) -> Any:
    try:
        hp_val, _hp_str, _hp_ctx = evaluate_answer_high_precision(
            spec, var_names, solution, precision
        )
        if hp_val is not None:
            return hp_val
    except Exception:
        pass

    ctx = hp_context.copy()
    for name, val in zip(var_names, solution):
        ctx[name] = val
    for item in spec.construction:
        expr = preprocess_hp_expr(item.expr)
        val = safe_eval_expr_hp(expr, ctx)
        ctx[item.name] = val
    apply_fixed_points(ctx)
    expr = preprocess_hp_expr(spec.answer_expr)
    return safe_eval_expr_hp(expr, ctx)


def build_solve_success_result(
    *,
    spec: Any,
    var_names: List[str],
    precision: int,
    solve_result: List[Any],
    solve_info: Dict[str, Any],
    hp_context: Dict[str, Any],
    evaluate_answer_high_precision: Callable[[Any, List[str], List[Any], int], Tuple[Any, Any, Any]],
    preprocess_hp_expr: Callable[[str], str],
    apply_fixed_points: Callable[[Dict[str, Any]], None],
    wrap_exact_value: Callable[[Any, int], Any],
    eval_exact_to_mpf: Callable[[str, int], Any],
) -> Tuple[SolveResult, Any]:
    """Build initial SolveResult object for successful solve branch."""
    value = solve_result
    solutions_list = _normalize_all_solutions(solve_info.get("all_solutions"), solve_result)
    metadata = dict(solve_info)
    metadata["all_solutions"] = solutions_list

    answer_values: List[Any] = []
    unique_solutions: List[Any] = []
    duplicate_count = 0
    legacy_answer_values = solve_info.get("answer_values") if isinstance(solve_info, dict) else None

    for index, solution in enumerate(solutions_list):
        try:
            hp_val = _evaluate_answer_with_fallback(
                spec=spec,
                var_names=var_names,
                precision=precision,
                solution=solution,
                hp_context=hp_context,
                evaluate_answer_high_precision=evaluate_answer_high_precision,
                preprocess_hp_expr=preprocess_hp_expr,
                apply_fixed_points=apply_fixed_points,
            )
            if hp_val is None and isinstance(legacy_answer_values, list) and index < len(legacy_answer_values):
                hp_val = legacy_answer_values[index]

            is_dup = False
            for v0 in answer_values:
                if v0 is None:
                    continue
                if answer_close(hp_val, v0):
                    is_dup = True
                    break
            if not is_dup:
                unique_solutions.append(solution)
                answer_values.append(hp_val)
            else:
                duplicate_count += 1
        except Exception:
            fallback_value = None
            if isinstance(legacy_answer_values, list) and index < len(legacy_answer_values):
                fallback_value = legacy_answer_values[index]
            unique_solutions.append(solution)
            answer_values.append(fallback_value)

    metadata["duplicate_count"] = duplicate_count
    metadata["solution_count"] = len(unique_solutions)
    answer_values = _sanitize_answer_values(answer_values)
    metadata["answer_values"] = answer_values

    numeric_ans = answer_values[0] if answer_values else None
    if numeric_ans is not None:
        metadata["numeric_answer"] = numeric_ans
        metadata["numeric_answer_raw"] = numeric_ans

    if "most_likely_answer" in solve_info and solve_info["most_likely_answer"]:
        metadata.setdefault("formatted_answer", solve_info["most_likely_answer"])
    elif numeric_ans is not None:
        metadata.setdefault("formatted_answer", numeric_ans)
    else:
        metadata.setdefault("formatted_answer", solve_info.get("best_residual", 0.0))

    exact_source = solve_info.get("most_likely_answer")
    if exact_source is None and numeric_ans is not None:
        exact_source = numeric_ans
    exact_wrapped = wrap_exact_value(exact_source, int(precision))
    try:
        if exact_wrapped is not None and numeric_ans is not None:
            ex_num = eval_exact_to_mpf(str(exact_wrapped), int(precision))
            if ex_num is not None:
                diff = abs(mp.mpf(numeric_ans) - mp.mpf(ex_num))
                metadata["exact_numeric_diff"] = float(diff)
                metadata["exact_numeric_consistent"] = bool(diff <= mp.mpf("1e-8"))
    except Exception:
        pass

    result = SolveResult(
        status=SolveStatus.SUCCESS,
        value=unique_solutions[0] if unique_solutions else value,
        solutions=unique_solutions,
        answer_values=answer_values,
        residual=solve_info.get("residual_norm", float("inf")),
        precision_achieved=int(solve_info.get("precision_achieved", 0)),
        elapsed_time=solve_info.get("elapsed_time", 0.0),
        exact_answer=exact_wrapped,
        minimal_polynomial=solve_info.get("minimal_polynomial"),
        metadata=metadata,
    )
    return result, numeric_ans


def build_solve_failure_result(
    *,
    spec: Any,
    var_names: List[str],
    precision: int,
    solve_result: Any,
    solve_info: Dict[str, Any],
    hp_context: Dict[str, Any],
    evaluate_answer_high_precision: Callable[[Any, List[str], List[Any], int], Tuple[Any, Any, Any]],
    preprocess_hp_expr: Callable[[str], str],
    apply_fixed_points: Callable[[Dict[str, Any]], None],
    wrap_exact_value: Callable[[Any, int], Any],
    errors: List[str] | None = None,
) -> SolveResult:
    metadata = dict(solve_info) if isinstance(solve_info, dict) else {}
    contamination_count = int(metadata.get("hp_float_contamination_count", 0) or 0)
    is_contamination_failure = contamination_count > 0
    if contamination_count > 0:
        metadata["success"] = False
        metadata["failure_reason"] = "hp_float_contamination"
    all_solutions = _normalize_all_solutions(metadata.get("all_solutions"), solve_result)
    if is_contamination_failure:
        all_solutions = []
    metadata["all_solutions"] = all_solutions

    raw_answer_values = metadata.get("answer_values")
    answer_values = _sanitize_answer_values(raw_answer_values)
    diagnostic_answer_values = list(answer_values)
    if metadata.get("residual_source") == "hp_invalid":
        answer_values = []
    if is_contamination_failure:
        answer_values = []
        diagnostic_answer_values = []
    answer_values = _sanitize_answer_values(answer_values)
    diagnostic_answer_values = _sanitize_answer_values(diagnostic_answer_values)
    converged_indices = set(_converged_solution_indices(metadata, len(all_solutions)))
    metadata["diagnostic_converged_solutions"] = [
        list(all_solutions[index])
        for index in sorted(converged_indices)
        if 0 <= index < len(all_solutions)
    ]
    metadata["diagnostic_converged_answer_values"] = _diagnostic_converged_answers(
        raw_answer_values=raw_answer_values,
        sanitized_answer_values=answer_values,
        all_solutions=all_solutions,
        converged_indices=converged_indices,
    )
    metadata["diagnostic_answer_values"] = list(diagnostic_answer_values)
    filtered_count = 0

    if answer_values and len(answer_values) == len(all_solutions):
        filtered_answers: List[Any] = []
        for i in range(len(all_solutions)):
            if i in converged_indices:
                val = answer_values[i]
                is_dup = any(answer_close(val, v0) for v0 in filtered_answers if v0 is not None)
                if not is_dup:
                    filtered_answers.append(val)
                else:
                    filtered_count += 1
            else:
                filtered_count += 1
        answer_values = filtered_answers
    else:
        # Fail-closed: do not synthesize failure answers from unconverged/all_solutions fallback.
        if answer_values:
            filtered_count += len(answer_values)
        answer_values = []

    metadata["filtered_answer_values_count"] = int(filtered_count)

    metadata["answer_values"] = answer_values
    metadata["success"] = False
    diagnostic_formatted_answer = (
        metadata.get("most_likely_answer")
        or (diagnostic_answer_values[0] if diagnostic_answer_values else None)
        or metadata.get("formatted_answer")
    )
    metadata["diagnostic_formatted_answer"] = diagnostic_formatted_answer
    if not metadata.get("formatted_answer"):
        metadata["formatted_answer"] = (
            ""
            if is_contamination_failure
            else metadata.get("most_likely_answer") or (
            answer_values[0] if answer_values else (
                diagnostic_answer_values[0] if diagnostic_answer_values else ""
            )
            )
        )

    exact_source = metadata.get("most_likely_answer")
    if exact_source is None and answer_values and not is_contamination_failure:
        exact_source = answer_values[0]
    exact_wrapped = wrap_exact_value(exact_source, int(precision))

    primary_value: Any = None
    if _is_solution_vector(solve_result) and not is_contamination_failure:
        primary_value = list(solve_result)
    elif all_solutions and not is_contamination_failure:
        primary_value = all_solutions[0]

    normalized_errors = list(errors or [])
    if is_contamination_failure and not normalized_errors:
        normalized_errors = ["High precision float contamination detected"]

    return SolveResult(
        status=SolveStatus.NO_SOLUTION,
        value=primary_value,
        solutions=all_solutions,
        answer_values=answer_values,
        residual=metadata.get("residual_norm", float("inf")),
        precision_achieved=int(metadata.get("precision_achieved", int(precision))),
        elapsed_time=metadata.get("elapsed_time", 0.0),
        exact_answer=exact_wrapped,
        minimal_polynomial=metadata.get("minimal_polynomial"),
        metadata=metadata,
        errors=normalized_errors,
    )
