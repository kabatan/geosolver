"""Execution modes for autosolve IR interpreter."""

from __future__ import annotations

from functools import partial
import math
import time
from typing import Any
from mpmath import mp

from geosolver.engine.standard.interpreter.answer import (
    _eval_exact_to_mpf,
    _evaluate_answer_high_precision,
    _wrap_exact_value,
)
from geosolver.engine.standard.interpreter.context import _get_high_precision_context
from geosolver.engine.standard.interpreter.guards.compile import compile_guards
from geosolver.engine.standard.interpreter.public.solve_dispatch import dispatch_solve
from geosolver.engine.standard.interpreter.public.solve_finalize import (
    build_solve_failure_result,
    build_solve_success_result,
)
from geosolver.engine.standard.result import SolveResult, SolveStatus
from geosolver.problem.ir.compiler import safe_eval_expr, safe_eval_expr_hp
from geosolver.problem.ir.schema import IRSpec
from geosolver.engine.standard.precision.type_guards.ensure_no_float import (
    ensure_high_precision_mode,
    ensure_no_float,
)
from geosolver.engine.standard.precision.type_guards.high_precision_contamination_error import (
    HighPrecisionContaminationError,
)
from geosolver.engine.standard.precision.type_guards.hp_contract import hp_contract
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import (
    boundary_float_to_mpf,
    BoundaryOrigin,
)
from geosolver.engine.standard.precision.type_guards.should_use_mpmath import (
    mpmath_precision_threshold,
    precision_backend_name,
    should_use_mpmath,
)
from geosolver.engine.standard.solver.tolerances import solve_residual_tolerance
from geosolver.engine.standard.solver import solve

from .interpreter_hp_helpers import (
    collect_hp_float_return_symbols as _collect_hp_float_return_symbols,
    evaluate_candidate_entry as _evaluate_candidate_entry,
    evaluate_candidate_residual_high_precision as _evaluate_candidate_residual_high_precision,
    extract_hp_float_contamination as _extract_hp_float_contamination,
    normalize_solution_list_for_hp as _normalize_solution_list_for_hp,
    normalize_solution_values_for_hp as _normalize_solution_values_for_hp,
    to_mpf_value as _to_mpf_value,
)
from .interpreter_helpers import (
    _DEFAULT_SOLVE_TIME_LIMIT_SECONDS,
    _build_success_result,
    _collect_guard_violations,
    _compute_residual_vector,
    _evaluate_answer_value,
    _evaluate_construction,
    _evaluate_target,
    _infer_bounds,
    _prepare_targets,
    _residual_norm,
    _to_float,
    _normalize_bounds,
    _merge_bounds,
    _DEFAULT_BOUND,
)
from .interpreter_degeneracy import compute_degeneracy_penalty

def _remaining_time(*, started_at: float, time_limit: float | None) -> float | None:
    if time_limit is None:
        return None
    elapsed = time.monotonic() - started_at
    return max(0.0, float(time_limit) - elapsed)


def _quick_numeric_solve_placeholder() -> tuple[list[Any] | None, dict[str, Any]]:
    return None, {}


def _random_solve_fallback_placeholder(
    _time_limit: float | None,
    aggressive: bool,
    ignore_guards: bool,
) -> tuple[list[Any] | None, dict[str, Any]]:
    _ = (aggressive, ignore_guards)
    return None, {}


def _random_solve_fallback(
    fallback_time_limit: float | None,
    aggressive: bool,
    ignore_guards: bool,
    *,
    solve_kwargs: dict[str, Any],
) -> tuple[list[Any] | None, dict[str, Any]]:
    _ = ignore_guards
    kwargs = dict(solve_kwargs)
    kwargs["time_limit"] = fallback_time_limit
    if aggressive:
        kwargs["two_pass"] = True
        try:
            kwargs["bounds_margin"] = max(4.0, float(kwargs.get("bounds_margin", 3.0)))
        except Exception:
            kwargs["bounds_margin"] = 4.0
    try:
        result, info = solve(**kwargs)
    except Exception:
        return None, {}
    return result, (info if isinstance(info, dict) else {})


def _identity_preprocess_expr(expr: str) -> str:
    return expr


def _apply_fixed_points_noop(_context: dict[str, Any]) -> None:
    return None


def _resolve_solve_sampling_policy(spec: IRSpec, precision: int, n_vars: int) -> tuple[bool, int]:
    needs_all_solutions = bool(len(spec.constraints) > 1 or precision >= 50 or n_vars > 1)
    if needs_all_solutions:
        max_solutions = max(2, min(12, n_vars * 4))
    else:
        max_solutions = 1
    return needs_all_solutions, max_solutions


def _normalize_answer_value_for_hp(answer_value: Any, *, precision: int) -> Any:
    if answer_value is None:
        return None
    if isinstance(answer_value, float):
        return boundary_float_to_mpf(answer_value, origin=BoundaryOrigin.OBJECTIVE_VALUE)
    try:
        return _to_mpf_value(
            answer_value,
            precision=int(precision),
            context="_normalize_answer_value_for_hp",
        )
    except HighPrecisionContaminationError:
        try:
            converted = _eval_exact_to_mpf(str(answer_value), int(precision))
            if converted is not None:
                return converted
        except Exception:
            pass
        raise
    except Exception:
        try:
            return _eval_exact_to_mpf(str(answer_value), int(precision))
        except Exception:
            return answer_value


@hp_contract(input_names=("values",))
def _build_solution_context_high_precision(
    spec: IRSpec,
    var_names: list[str],
    values: list[Any],
    base_context: dict[str, Any],
    precision: int,
) -> dict[str, Any]:
    context = dict(base_context)
    context.update(_get_high_precision_context(int(precision)))
    for name, value in zip(var_names, values):
        val_mpf = _to_mpf_value(value, precision=int(precision), context=f"variable:{name}")
        ensure_no_float(val_mpf, context=f"hp_variable:{name}")
        context[name] = val_mpf
    for item in spec.construction:
        context[item.name] = safe_eval_expr_hp(item.expr, context)
    return context


def _evaluate_target_high_precision(
    target: Any,
    context: dict[str, Any],
    *,
    precision: int,
    index: int,
) -> Any:
    if isinstance(target, str):
        value = safe_eval_expr_hp(target, context)
    else:
        value = target
    return _to_mpf_value(value, precision=int(precision), context=f"target:{index}")


@hp_contract(input_names=("values",))
def _compute_residual_vector_high_precision(
    values: list[Any],
    *,
    spec: IRSpec,
    var_names: list[str],
    targets: list[Any],
    base_context: dict[str, Any],
    precision: int,
    failure_indices: list[int] | None = None,
    float_return_symbols: list[str] | None = None,
) -> list[Any]:
    from geosolver.engine.standard.precision.type_guards.high_precision_contamination_error import (
        HighPrecisionContaminationError as _HPC,
    )
    try:
        context = _build_solution_context_high_precision(
            spec,
            var_names,
            values,
            base_context,
            int(precision),
        )
    except _HPC:
        raise
    except Exception:
        failed_all = list(range(len(spec.constraints)))
        if isinstance(failure_indices, list):
            failure_indices.extend(failed_all)
        return [mp.nan for _ in spec.constraints]

    residuals: list[Any] = []
    for index, constraint_expr in enumerate(spec.constraints):
        try:
            lhs = _to_mpf_value(
                safe_eval_expr_hp(constraint_expr, context),
                precision=int(precision),
                context=f"constraint_lhs:{index}",
            )
            rhs = _evaluate_target_high_precision(
                targets[index],
                context,
                precision=int(precision),
                index=index,
            )
            residual = lhs - rhs
            residuals.append(residual)
            if (not mp.isfinite(lhs)) or (not mp.isfinite(rhs)) or (not mp.isfinite(residual)):
                if isinstance(failure_indices, list):
                    failure_indices.append(index)
        except _HPC:
            raise
        except Exception:
            residuals.append(mp.nan)
            if isinstance(failure_indices, list):
                failure_indices.append(index)
    _collect_hp_float_return_symbols(context, float_return_symbols)
    return residuals


def _residual_norm_high_precision(residuals: list[Any]) -> Any:
    terms: list[Any] = []
    for index, residual in enumerate(residuals):
        value = _to_mpf_value(residual, precision=80, context=f"residual:{index}")
        if not mp.isfinite(value):
            return mp.inf
        terms.append(value * value)
    if not terms:
        return mp.mpf("0")
    return mp.sqrt(mp.fsum(terms))


def _compute_residual_vector_hp_as_float(
    values: list[Any],
    *,
    residual_fn_hp: Any,
) -> list[float]:
    """Call residual_fn_hp and convert HP residuals to float, mapping non-finite to inf."""
    try:
        hp_residuals = residual_fn_hp(values)
    except Exception:
        return [float("inf")]
    result: list[float] = []
    for r in hp_residuals:
        try:
            if not mp.isfinite(r):
                result.append(float("inf"))
            else:
                result.append(float(r))
        except Exception:
            result.append(float("inf"))
    return result


def _run_direct_without_variables(
    *,
    spec: IRSpec,
    precision: int,
    base_context: dict[str, Any],
) -> SolveResult:
    try:
        context = dict(base_context)
        _evaluate_construction(context, spec)
    except Exception as exc:
        return SolveResult(status=SolveStatus.INVALID_INPUT, errors=[str(exc)])
    
    residuals: list[Any] = []
    targets = _prepare_targets(spec)
    is_hp = should_use_mpmath(precision)

    for index, constraint_expr in enumerate(spec.constraints):
        try:
            if is_hp:
                with high_precision_mode():
                    hp_context = _build_solution_context_high_precision(
                        spec, [], [], base_context, precision
                    )
                    lhs = _to_mpf_value(
                        safe_eval_expr_hp(constraint_expr, hp_context),
                        precision=precision,
                        context="direct.eval_lhs",
                    )
                    rhs = _evaluate_target_high_precision(
                        targets[index],
                        hp_context,
                        precision=precision,
                        index=index,
                    )
                    residuals.append(lhs - rhs)
            else:
                lhs = _to_float(safe_eval_expr(constraint_expr, context))
                rhs = _evaluate_target(targets[index], context)
                residuals.append(lhs - rhs)
        except Exception:
            residuals.append(float("nan") if not is_hp else mp.mpf("nan"))

    metadata: dict[str, Any] = {"residual_norm": _residual_norm_high_precision(residuals) if is_hp else _residual_norm(residuals)}
    answer_value: Any = None
    if spec.answer_expr:
        try:
            if is_hp:
                with high_precision_mode():
                    eval_context = _build_solution_context_high_precision(spec, [], [], base_context, precision)
                    answer_value = safe_eval_expr_hp(spec.answer_expr, eval_context)
                    answer_value = _to_mpf_value(answer_value, precision=precision, context="direct.eval_answer")
            else:
                answer_value = safe_eval_expr(spec.answer_expr, context)
        except Exception as exc:
            metadata["answer_error"] = str(exc)
    elif spec.objective_expr:
        try:
            if is_hp:
                with high_precision_mode():
                    eval_context = _build_solution_context_high_precision(spec, [], [], base_context, precision)
                    answer_value = safe_eval_expr_hp(spec.objective_expr, eval_context)
                    answer_value = _to_mpf_value(answer_value, precision=precision, context="direct.eval_objective")
            else:
                answer_value = safe_eval_expr(spec.objective_expr, context)
            metadata["objective_value"] = answer_value
        except Exception as exc:
            metadata["objective_error"] = str(exc)

    return _build_success_result(
        values=[],
        residuals=residuals,
        precision=precision,
        metadata=metadata,
        answer_value=answer_value,
    )


def _init_hp_eval_metadata(metadata: dict[str, Any]) -> None:
    """Initialize HP evaluation tracking keys with safe defaults."""
    metadata.setdefault("hp_residual_eval_failed", False)
    metadata.setdefault("hp_residual_eval_error_count", 0)
    metadata.setdefault("hp_residual_eval_error_indices", [])
    metadata.setdefault("candidate_eval_error_count", 0)
    metadata.setdefault("candidate_eval_error_examples", [])


def _evaluate_hp_residuals_into_metadata(
    *,
    metadata: dict[str, Any],
    values: list[Any],
    spec: IRSpec,
    var_names: list[str],
    targets: Any,
    base_context: dict[str, Any],
    precision: int,
    use_high_precision: bool,
    residual_fn_hp: Any,
    context_prefix: str,
) -> None:
    """Evaluate HP residuals and store results in metadata."""
    if use_high_precision and callable(residual_fn_hp):
        try:
            with high_precision_mode():
                hp_failure_indices: list[int] = []
                hp_float_return_symbols: list[str] = []
                hp_residuals = _compute_residual_vector_high_precision(
                    values,
                    spec=spec,
                    var_names=var_names,
                    targets=targets,
                    base_context=base_context,
                    precision=precision,
                    failure_indices=hp_failure_indices,
                    float_return_symbols=hp_float_return_symbols,
                )
                ensure_no_float(hp_residuals, context=f"{context_prefix}.solution_residuals_hp")
                hp_residual_norm = _residual_norm_high_precision(hp_residuals)
                metadata["constraint_residual_hp"] = hp_residual_norm
                metadata["hp_residual_eval_failed"] = bool(hp_failure_indices) or (not mp.isfinite(hp_residual_norm))
                metadata["hp_residual_eval_error_count"] = len(hp_failure_indices)
                metadata["hp_residual_eval_error_indices"] = list(sorted(set(hp_failure_indices)))
                metadata["hp_float_return_symbols"] = list(hp_float_return_symbols)
                if mp.isfinite(hp_residual_norm):
                    metadata["residual_norm_hp"] = hp_residual_norm
                    metadata["residual_norm_float"] = hp_residual_norm
        except HighPrecisionContaminationError:
            raise
        except Exception:
            metadata["hp_residual_eval_failed"] = True
            metadata["hp_residual_eval_error_count"] = int(len(spec.constraints))
            metadata["hp_residual_eval_error_indices"] = list(range(len(spec.constraints)))


def _finalize_precision_metadata(
    *,
    metadata: dict[str, Any],
    residual_norm_float: Any,
    use_high_precision: bool,
    precision: int,
) -> None:
    """Finalize backend info, residual source, contamination, and residual_norm."""
    metadata["used_high_precision"] = bool(use_high_precision)
    metadata["precision_backend"] = precision_backend_name(int(precision))
    metadata["precision_threshold"] = mpmath_precision_threshold()
    if "constraint_residual_hp" in metadata and (not mp.isfinite(metadata["constraint_residual_hp"])):
        metadata["residual_source"] = "hp_invalid"
    else:
        metadata["residual_source"] = metadata.get("selection_residual_source", "legacy_hp" if use_high_precision else "legacy_float")
    contamination_count, contamination_examples = _extract_hp_float_contamination(metadata)
    metadata["hp_float_contamination_count"] = int(contamination_count)
    metadata["hp_float_contamination_examples"] = list(contamination_examples)
    if contamination_count > 0:
        metadata["success"] = False
        metadata["failure_reason"] = "hp_float_contamination"
    if use_high_precision and "residual_norm_hp" in metadata and mp.isfinite(metadata["residual_norm_hp"]):
        metadata["residual_norm"] = metadata["residual_norm_hp"]
    else:
        metadata["residual_norm_float"] = residual_norm_float


def _run_solve(
    *,
    spec: IRSpec,
    var_names: list[str],
    precision: int,
    time_limit: float | None,
    verbose: bool,
    base_context: dict[str, Any],
) -> SolveResult:
    started_at = time.monotonic()
    targets = _prepare_targets(spec)
    residual_fn = partial(
        _compute_residual_vector,
        spec=spec,
        var_names=var_names,
        targets=targets,
        base_context=base_context,
    )
    use_high_precision = bool(int(precision) >= 16 or should_use_mpmath(int(precision)))
    residual_fn_hp = (
        partial(
            _compute_residual_vector_high_precision,
            spec=spec,
            var_names=var_names,
            targets=targets,
            base_context=base_context,
            precision=int(precision),
        )
        if use_high_precision
        else None
    )
    residual_fn_for_candidates = (
        partial(
            _evaluate_candidate_residual_high_precision,
            residual_fn_hp=residual_fn_hp,
            precision=int(precision),
        )
        if use_high_precision and callable(residual_fn_hp)
        else residual_fn
    )
    answer_fn = partial(
        _evaluate_answer_value,
        spec=spec,
        var_names=var_names,
        base_context=base_context,
        precision=int(precision),
        use_high_precision=bool(use_high_precision),
    )
    remaining_time = partial(
        _remaining_time,
        started_at=started_at,
        time_limit=(
            _DEFAULT_SOLVE_TIME_LIMIT_SECONDS if time_limit is None else float(time_limit)
        ),
    )

    needs_all_solutions, max_solutions = _resolve_solve_sampling_policy(
        spec, int(precision), len(var_names)
    )
    compiled_guards = compile_guards(spec.guards)

    guard_fn = partial(
        _collect_guard_violations,
        spec=spec,
        var_names=var_names,
        base_context=base_context,
        compiled_guards=compiled_guards,
    )
    
    degeneracy_fn = partial(
        compute_degeneracy_penalty,
        spec=spec,
        context=base_context,
        precision=int(precision),
    )

    candidate_evaluator = partial(
        _evaluate_candidate_entry,
        residual_fn=residual_fn_for_candidates,
        guard_fn=guard_fn,
        objective_fn=None,
        degeneracy_fn=degeneracy_fn,
        reject_float=bool(use_high_precision),
    )

    dispatch_residual_tolerance = float(solve_residual_tolerance(int(precision)))

    explicit_bounds = _normalize_bounds(spec.bounds, len(var_names))
    # If explicit_bounds matches default completely (no explicit bounds provided), consider it None for merging
    if explicit_bounds and all(b == _DEFAULT_BOUND for b in explicit_bounds) and not getattr(spec, "bounds", None):
        explicit_bounds = None
        
    inferred_bounds = _infer_bounds(spec, len(var_names), base_context)
    merged_bounds, bounds_source = _merge_bounds(explicit_bounds, inferred_bounds, len(var_names))
    random_solve_kwargs = {
        "n": len(var_names),
        "f": residual_fn,
        "v": [0] * len(spec.constraints),
        "bounds": merged_bounds,
        "precision": precision,
        "find_all": needs_all_solutions,
        "max_solutions": max_solutions,
        "verbose": verbose,
        "f_mp": residual_fn_hp,
        "f_fast": None,
        "two_pass": True,
        "bounds_margin": 3.0,
        "ans": answer_fn,
        "candidate_evaluator": candidate_evaluator,
        "variable_names": var_names,
        "guard_irs": compiled_guards,
    }
    random_solve_fallback = partial(
        _random_solve_fallback,
        solve_kwargs=random_solve_kwargs,
    )

    solve_result, solve_info = dispatch_solve(
        direct_eval_done=False,
        initial_solution=None,
        initial_info={},
        quick_numeric_solve=_quick_numeric_solve_placeholder,
        precision=precision,
        time_limit=time_limit,
        f_func_fast=None,
        avoid_fast=False,
        f_func=residual_fn,
        n_vars=len(var_names),
        v_numeric=[0] * len(spec.constraints),
        bounds=merged_bounds,
        solve_precision=precision,
        verbose=verbose,
        remaining_time=remaining_time,
        f_func_hp=residual_fn_hp,
        ans_func=answer_fn,
        needs_all_solutions=needs_all_solutions,
        max_solutions=max_solutions,
        random_solve_fallback=random_solve_fallback,
        candidate_evaluator=candidate_evaluator,
        residual_tolerance=dispatch_residual_tolerance,
        variable_names=var_names,
        guard_irs=compiled_guards,
    )
    if not solve_result:
        return build_solve_failure_result(
            spec=spec,
            var_names=var_names,
            precision=precision,
            solve_result=solve_result,
            solve_info=solve_info if isinstance(solve_info, dict) else {},
            hp_context=_get_high_precision_context(precision),
            evaluate_answer_high_precision=_evaluate_answer_high_precision,
            preprocess_hp_expr=_identity_preprocess_expr,
            apply_fixed_points=_apply_fixed_points_noop,
            wrap_exact_value=_wrap_exact_value,
            errors=["No solution found"],
        )

    if isinstance(solve_result, (list, tuple)):
        values = list(solve_result)
    else:
        values = [solve_result]
    if use_high_precision:
        # Zone B: HP 繝｢繝ｼ繝峨↓蜈･繧句燕縺ｫ float 竊・mpf 螟画鋤 (INV-14/INV-3)
        values = [
            boundary_float_to_mpf(v, origin=BoundaryOrigin.SCIPY_OPTIMIZE)
            if isinstance(v, float)
            else v
            for v in values
        ]
        if isinstance(solve_info, dict):
            all_solutions_raw = solve_info.get("all_solutions", [])
            if isinstance(all_solutions_raw, list):
                converted_all: list[Any] = []
                for sol in all_solutions_raw:
                    if isinstance(sol, list):
                        converted_all.append([
                            boundary_float_to_mpf(v, origin=BoundaryOrigin.SCIPY_OPTIMIZE)
                            if isinstance(v, float) else v
                            for v in sol
                        ])
                    else:
                        converted_all.append(sol)
                solve_info["all_solutions"] = converted_all
        with high_precision_mode():
            ensure_high_precision_mode(context="_run_solve")
            values = _normalize_solution_values_for_hp(
                values,
                precision=int(precision),
                context="_run_solve.hp_values",
            )
            ensure_no_float(values, context="_run_solve.hp_values")
            if isinstance(solve_info, dict):
                all_solutions = solve_info.get("all_solutions", [])
                if isinstance(all_solutions, list):
                    solve_info["all_solutions"] = _normalize_solution_list_for_hp(
                        all_solutions,
                        precision=int(precision),
                        context="_run_solve.hp_candidates",
                    )
                ensure_no_float(solve_info.get("all_solutions", []), context="_run_solve.hp_candidates")
    residuals = residual_fn(values)
    metadata = dict(solve_info) if isinstance(solve_info, dict) else {}
    _init_hp_eval_metadata(metadata)
    residual_norm = _residual_norm(residuals)
    _evaluate_hp_residuals_into_metadata(
        metadata=metadata,
        values=values,
        spec=spec,
        var_names=var_names,
        targets=targets,
        base_context=base_context,
        precision=int(precision),
        use_high_precision=use_high_precision,
        residual_fn_hp=residual_fn_hp,
        context_prefix="_run_solve",
    )
    metadata["residual_norm"] = residual_norm
    try:
        _raw_tol = metadata.get("residual_tolerance")
        if isinstance(_raw_tol, mp.mpf):
            residual_tolerance = _raw_tol
        elif _raw_tol is not None:
            residual_tolerance = float(_raw_tol)
        else:
            residual_tolerance = solve_residual_tolerance(int(precision))
    except Exception:
        residual_tolerance = solve_residual_tolerance(int(precision))
    metadata["residual_tolerance"] = residual_tolerance
    metadata["bounds_source"] = bounds_source
    _finalize_precision_metadata(
        metadata=metadata,
        residual_norm_float=residual_norm,
        use_high_precision=use_high_precision,
        precision=int(precision),
    )

    if use_high_precision and "residual_norm_hp" in metadata:
        _tol_mpf = residual_tolerance if isinstance(residual_tolerance, mp.mpf) else boundary_float_to_mpf(residual_tolerance, origin=BoundaryOrigin.LEGACY_TOLERANCE)
        success_by_residual = (
            bool(values)
            and bool(metadata.get("success", True))
            and mp.isfinite(metadata["residual_norm_hp"])
            and mp.isfinite(_tol_mpf)
            and metadata["residual_norm_hp"] <= _tol_mpf
        )
    else:
        success_by_residual = (
            bool(values)
            and bool(metadata.get("success", True))
            and math.isfinite(residual_norm)
            and math.isfinite(residual_tolerance)
            and residual_norm <= residual_tolerance
        )
    guard_violations = _collect_guard_violations(
        values, spec=spec, var_names=var_names, base_context=base_context
    )
    if guard_violations or not success_by_residual:
        metadata["guard_violations"] = guard_violations
        metadata["success"] = False
        errors: list[str] = []
        if guard_violations:
            errors.append("Guard conditions violated")
        if not success_by_residual:
            errors.append("Residual tolerance check failed")
        return build_solve_failure_result(
            spec=spec,
            var_names=var_names,
            precision=precision,
            solve_result=values,
            solve_info=metadata,
            hp_context=_get_high_precision_context(precision),
            evaluate_answer_high_precision=_evaluate_answer_high_precision,
            preprocess_hp_expr=_identity_preprocess_expr,
            apply_fixed_points=_apply_fixed_points_noop,
            wrap_exact_value=_wrap_exact_value,
            errors=errors,
        )
    if int(metadata.get("hp_float_contamination_count", 0) or 0) > 0:
        return build_solve_failure_result(
            spec=spec,
            var_names=var_names,
            precision=precision,
            solve_result=values,
            solve_info=metadata,
            hp_context=_get_high_precision_context(precision),
            evaluate_answer_high_precision=_evaluate_answer_high_precision,
            preprocess_hp_expr=_identity_preprocess_expr,
            apply_fixed_points=_apply_fixed_points_noop,
            wrap_exact_value=_wrap_exact_value,
            errors=["High precision float contamination detected"],
        )

    try:
        result, _numeric_ans = build_solve_success_result(
            spec=spec,
            var_names=var_names,
            precision=precision,
            solve_result=values,
            solve_info=metadata,
            hp_context=_get_high_precision_context(precision),
            evaluate_answer_high_precision=_evaluate_answer_high_precision,
            preprocess_hp_expr=_identity_preprocess_expr,
            apply_fixed_points=_apply_fixed_points_noop,
            wrap_exact_value=_wrap_exact_value,
            eval_exact_to_mpf=_eval_exact_to_mpf,
        )
        return result
    except HighPrecisionContaminationError:
        raise
    except Exception:
        try:
            answer_value = answer_fn(values)
        except Exception as exc:
            metadata["answer_error"] = str(exc)
            answer_value = None
        return _build_success_result(
            values=values,
            residuals=residuals,
            precision=precision,
            metadata=metadata,
            answer_value=answer_value,
        )
