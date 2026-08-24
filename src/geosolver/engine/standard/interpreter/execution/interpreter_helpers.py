"""Shared helpers for autosolve IR interpreter."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math
from typing import Any

from mpmath import mp
from geosolver.engine.standard.precision.type_guards.ensure_mpf import ensure_mpf
from geosolver.engine.standard.precision.type_guards.high_precision_contamination_error import (
    HighPrecisionContaminationError,
)
from geosolver.engine.standard.precision.type_guards.high_precision_mode import (
    is_high_precision_mode,
)
from geosolver.engine.standard.precision.type_guards.strict_to_mpf import strict_to_mpf

from geosolver.engine.standard.interpreter.answer import (
    _eval_exact_to_mpf,
    _evaluate_answer_high_precision,
    _wrap_exact_value,
)
from geosolver.engine.standard.interpreter.compile import infer_bounds
from geosolver.engine.standard.interpreter.context import (
    _get_fast_geometry_context,
    _get_geometry_context,
    _get_high_precision_context,
)
from geosolver.engine.standard.interpreter.execution.interpreter_result_helpers import (
    build_success_result,
    residual_norm,
)
from geosolver.engine.standard.interpreter.answer.precision_schedule import MIN_PRECISION
from geosolver.engine.standard.interpreter.guards.compile import (
    compile_guards,
    guard_margin_value,
    guard_hard_satisfied,
    guard_violation_value,
)
from geosolver.engine.standard.interpreter.guards.evaluate import _is_guard_satisfied
from geosolver.core.result import SolveResult, SolveStatus
from geosolver.ir.compiler import safe_eval_expr, safe_eval_expr_hp
from geosolver.ir.parser import load_ir
from geosolver.ir.schema import IRSpec
from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import (
    boundary_float_to_mpf,
    BoundaryOrigin,
)

_DEFAULT_BOUND = (-100.0, 100.0)
_DEFAULT_SOLVE_TIME_LIMIT_SECONDS = 300
_DEFAULT_OPTIMIZE_TIME_LIMIT_SECONDS = 180


@dataclass(frozen=True)
class CandidateEval:
    values: list[Any]
    residual_norm: Any
    guard_ok: bool
    guard_violations: list[str]
    objective_value: Any | None
    degeneracy_penalty: Any = mp.mpf("0")
    hp_residual_norm: Any | None = None
    hp_residual_converged: bool | None = None
    candidate_id: int | None = None


def _coerce_mpf_score(value: Any, *, context: str, reject_float: bool = False) -> Any:
    if isinstance(value, mp.mpf):
        return value
    if isinstance(value, float):
        if bool(reject_float) or is_high_precision_mode():
            raise HighPrecisionContaminationError(
                f"float contamination detected at {context}: {value}"
            )
        return ensure_mpf(f"{value}", context=context)
    if isinstance(value, (int, str)):
        return ensure_mpf(value, context=context)
    return ensure_mpf(value, context=context)


def evaluate_candidate(
    values: list[Any],
    *,
    residual_evaluator: Callable[[list[Any]], list[Any]],
    guard_evaluator: Callable[[list[Any]], list[str]] | None = None,
    objective_evaluator: Callable[[list[Any]], Any] | None = None,
    degeneracy_evaluator: Callable[[list[Any]], Any] | None = None,
    reject_float: bool = False,
    candidate_id: int | None = None,
) -> CandidateEval:
    residuals = residual_evaluator(values)
    residual_terms: list[Any] = []
    for index, entry in enumerate(residuals):
        residual_term = _coerce_mpf_score(
            entry,
            context=f"candidate_residual[{index}]",
            reject_float=bool(reject_float),
        )
        if not mp.isfinite(residual_term):
            residual_terms = [mp.inf]
            break
        residual_terms.append(residual_term * residual_term)
    if residual_terms == [mp.inf]:
        residual_value = mp.inf
    else:
        residual_value = mp.sqrt(mp.fsum(residual_terms)) if residual_terms else mp.mpf("0")

    guard_violations: list[str] = []
    if callable(guard_evaluator):
        guard_violations = list(guard_evaluator(values))

    objective_value: Any | None = None
    if callable(objective_evaluator):
        try:
            objective_raw = objective_evaluator(values)
            objective_numeric = _coerce_mpf_score(
                objective_raw,
                context="candidate_objective",
                reject_float=bool(reject_float),
            )
            if mp.isfinite(objective_numeric):
                objective_value = objective_numeric
        except Exception:
            objective_value = None

    degeneracy_penalty = mp.mpf("0")
    if callable(degeneracy_evaluator):
        try:
            degeneracy_penalty = _coerce_mpf_score(
                degeneracy_evaluator(values),
                context="candidate_degeneracy",
                reject_float=bool(reject_float),
            )
            if not mp.isfinite(degeneracy_penalty):
                degeneracy_penalty = mp.mpf("0")
        except Exception:
            degeneracy_penalty = mp.mpf("0")

    return CandidateEval(
        values=list(values),
        residual_norm=residual_value,
        guard_ok=(len(guard_violations) == 0),
        guard_violations=guard_violations,
        objective_value=objective_value,
        degeneracy_penalty=degeneracy_penalty,
        candidate_id=candidate_id,
    )


def select_feasible_candidate(
    candidate_evals: list[CandidateEval],
    *,
    mode: str,
) -> CandidateEval | None:
    if not candidate_evals:
        return None

    if mode == "solve":
        direction = mp.mpf("1")
    else:
        direction = mp.mpf("-1") if mode == "max" else mp.mpf("1")

    best_entry: CandidateEval | None = None
    best_key: tuple | None = None
    for entry in candidate_evals:
        objective_value = entry.objective_value
        objective_key = (
            mp.inf
            if objective_value is None
            else direction * _coerce_mpf_score(objective_value, context="candidate_objective_key")
        )

        if mode == "solve":
            entry_key = (
                mp.mpf("0") if entry.guard_ok else mp.mpf("1"),
                _coerce_mpf_score(entry.residual_norm, context="candidate_residual_key"),
                _coerce_mpf_score(entry.degeneracy_penalty, context="candidate_degeneracy_key"),
            )
        else:
            # PHASE-2: HP feasibility first for optimize.
            # Order: guard_ok -> hp_residual_converged -> hp_residual_norm -> objective -> degeneracy
            hp_converged_key = (
                mp.mpf("0") if entry.hp_residual_converged is True
                else mp.mpf("1")
            )
            hp_residual_key = (
                _coerce_mpf_score(entry.hp_residual_norm, context="candidate_hp_residual_key")
                if entry.hp_residual_norm is not None
                else mp.inf
            )
            entry_key = (
                mp.mpf("0") if entry.guard_ok else mp.mpf("1"),
                hp_converged_key,
                hp_residual_key,
                objective_key,
                _coerce_mpf_score(entry.degeneracy_penalty, context="candidate_degeneracy_key"),
            )

        if best_key is None or entry_key < best_key:
            best_entry = entry
            best_key = entry_key
    return best_entry

def _infer_bounds(*args: Any, **kwargs: Any) -> Any:
    return infer_bounds(*args, **kwargs)

def _load_spec(ir: Any) -> IRSpec:
    if isinstance(ir, IRSpec):
        return ir
    return load_ir(ir)

def _build_base_context(prefer_fast: bool) -> dict[str, Any]:
    if prefer_fast:
        return _get_fast_geometry_context()
    return _get_geometry_context()

def _normalize_bounds(bounds: Any, n_vars: int) -> list[tuple[float, float]] | None:
    if n_vars <= 0:
        return None
    if bounds is None or not isinstance(bounds, list):
        return [_DEFAULT_BOUND for _ in range(n_vars)]

    normalized: list[tuple[float, float]] = []
    for index in range(n_vars):
        bound = bounds[index] if index < len(bounds) else None
        if bound is None:
            normalized.append(_DEFAULT_BOUND)
            continue
        try:
            lo = float(bound[0])
            hi = float(bound[1])
        except Exception:
            normalized.append(_DEFAULT_BOUND)
            continue
        if not math.isfinite(lo) or not math.isfinite(hi) or lo >= hi:
            normalized.append(_DEFAULT_BOUND)
            continue
        normalized.append((lo, hi))
    return normalized

def _merge_bounds(
    explicit_bounds: list[tuple[float, float]] | None,
    inferred_bounds: list[tuple[float, float]] | None,
    n_vars: int,
) -> tuple[list[tuple[float, float]] | None, str]:
    if not explicit_bounds and not inferred_bounds:
        return _normalize_bounds(None, n_vars), "default"
    if explicit_bounds and not inferred_bounds:
        return explicit_bounds, "explicit"
    if not explicit_bounds and inferred_bounds:
        return inferred_bounds, "inferred"
        
    merged = []
    for i in range(n_vars):
        e_bound = explicit_bounds[i] if i < len(explicit_bounds) else _DEFAULT_BOUND
        i_bound = inferred_bounds[i] if i < len(inferred_bounds) else _DEFAULT_BOUND
        merged.append((max(e_bound[0], i_bound[0]), min(e_bound[1], i_bound[1])))
    return merged, "merged"

def _prepare_targets(spec: IRSpec) -> list[Any]:
    count = len(spec.constraints)
    values = list(spec.v) if spec.v is not None else []
    if len(values) < count:
        values.extend([0] * (count - len(values)))
    return values[:count]

def _assign_variables(context: dict[str, Any], var_names: list[str], values: list[float]) -> None:
    for name, value in zip(var_names, values):
        context[name] = value


def _assign_variables_high_precision(
    context: dict[str, Any],
    var_names: list[str],
    values: list[Any],
) -> None:
    for index, (name, value) in enumerate(zip(var_names, values)):
        if isinstance(value, float):
            context[name] = boundary_float_to_mpf(value, origin=BoundaryOrigin.SCIPY_OPTIMIZE)
            continue
        try:
            context[name] = strict_to_mpf(value, context=f"guard_variable:{name}[{index}]")
        except Exception:
            context[name] = boundary_float_to_mpf(
                float(value),
                origin=BoundaryOrigin.SCIPY_OPTIMIZE,
            )


def _evaluate_construction(context: dict[str, Any], spec: IRSpec) -> None:
    for item in spec.construction:
        context[item.name] = safe_eval_expr(item.expr, context)


def _evaluate_construction_for_guards(context: dict[str, Any], spec: IRSpec) -> None:
    for item in spec.construction:
        try:
            context[item.name] = safe_eval_expr_hp(item.expr, context)
        except Exception:
            continue


def _build_solution_context(
    spec: IRSpec,
    var_names: list[str],
    values: list[float],
    base_context: dict[str, Any],
) -> dict[str, Any]:
    context = dict(base_context)
    _assign_variables(context, var_names, values)
    _evaluate_construction(context, spec)
    return context


def _build_guard_context(
    spec: IRSpec,
    var_names: list[str],
    values: list[Any],
    base_context: dict[str, Any],
) -> dict[str, Any]:
    context = dict(base_context)
    context.update(_get_high_precision_context(max(MIN_PRECISION, 80)))
    _assign_variables_high_precision(context, var_names, values)
    _evaluate_construction_for_guards(context, spec)
    return context


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        try:
            exact_value = _eval_exact_to_mpf(value, 50)
            return float(str(exact_value))
        except Exception:
            return float("nan")

def _evaluate_target(target: Any, context: dict[str, Any]) -> float:
    if isinstance(target, str):
        return _to_float(safe_eval_expr(target, context))
    return _to_float(target)

def _compute_residual_vector(
    values: list[float],
    *,
    spec: IRSpec,
    var_names: list[str],
    targets: list[Any],
    base_context: dict[str, Any],
) -> list[float]:
    try:
        context = _build_solution_context(spec, var_names, values, base_context)
    except Exception:
        return [float("nan") for _ in spec.constraints]

    residuals: list[float] = []
    for index, constraint_expr in enumerate(spec.constraints):
        try:
            lhs = _to_float(safe_eval_expr(constraint_expr, context))
            rhs = _evaluate_target(targets[index], context)
            residuals.append(lhs - rhs)
        except Exception:
            residuals.append(float("nan"))
    return residuals

def _compute_objective_value(
    values: list[float],
    *,
    spec: IRSpec,
    var_names: list[str],
    base_context: dict[str, Any],
) -> float:
    if not spec.objective_expr:
        return 0.0
    try:
        context = _build_solution_context(spec, var_names, values, base_context)
        return _to_float(safe_eval_expr(spec.objective_expr, context))
    except Exception:
        return float("nan")

def _evaluate_answer_value(
    values: list[float],
    *,
    spec: IRSpec,
    var_names: list[str],
    base_context: dict[str, Any],
    precision: int,
    use_high_precision: bool,
) -> Any:
    context = _build_solution_context(spec, var_names, values, base_context)
    hp_first = bool(use_high_precision) and int(precision) >= 16
    if spec.answer_expr:
        if hp_first:
            try:
                hp_val, _hp_str, _hp_ctx = _evaluate_answer_high_precision(
                    spec,
                    var_names,
                    values,
                    precision=max(MIN_PRECISION, int(precision)),
                )
                if hp_val is not None:
                    return hp_val
            except Exception:
                pass
        try:
            return safe_eval_expr(spec.answer_expr, context)
        except Exception:
            if hp_first:
                return None
            try:
                hp_val, _hp_str, _hp_ctx = _evaluate_answer_high_precision(
                    spec,
                    var_names,
                    values,
                    precision=max(MIN_PRECISION, int(precision)),
                )
                return hp_val
            except Exception:
                return None
    if spec.objective_expr:
        return safe_eval_expr(spec.objective_expr, context)
    return None

def _collect_guard_evidence(
    values: list[Any],
    *,
    spec: IRSpec,
    var_names: list[str],
    base_context: dict[str, Any],
    compiled_guards: tuple[Any, ...] | None = None,
    include_margins: bool = True,
) -> tuple[list[str], tuple[Any | None, ...]]:
    if not spec.guards:
        return [], ()
    target_dps = max(int(mp.dps), MIN_PRECISION, 80)
    with mp.workdps(target_dps):
        try:
            context = _build_guard_context(spec, var_names, values, base_context)
        except Exception as exc:
            return [f"context_error: {exc}"], tuple(None for _ in spec.guards)

        guard_irs = compiled_guards if compiled_guards is not None else compile_guards(spec.guards)
        violations: list[str] = []
        margins: list[Any | None] = []
        for index, guard_ir in enumerate(guard_irs):
            try:
                guard_ok = guard_hard_satisfied(guard_ir, context)
                if not guard_ok:
                    violations.append(f"guard[{index}] returned False")
                    margins.append(None)
                else:
                    margins.append(
                        guard_margin_value(guard_ir, context)
                        if include_margins
                        else mp.inf
                    )
            except Exception as exc:
                violations.append(f"guard[{index}] raised: {exc}")
                margins.append(None)
        return violations, tuple(margins)


def _collect_guard_violations(
    values: list[Any],
    *,
    spec: IRSpec,
    var_names: list[str],
    base_context: dict[str, Any],
    compiled_guards: tuple[Any, ...] | None = None,
) -> list[str]:
    violations, _margins = _collect_guard_evidence(
        values,
        spec=spec,
        var_names=var_names,
        base_context=base_context,
        compiled_guards=compiled_guards,
    )
    return violations


def _guard_violation_penalty(
    values: list[Any],
    *,
    spec: IRSpec,
    var_names: list[str],
    base_context: dict[str, Any],
    compiled_guards: tuple[Any, ...] | None = None,
) -> float:
    if not spec.guards:
        return 0.0
    target_dps = max(int(mp.dps), MIN_PRECISION, 80)
    with mp.workdps(target_dps):
        try:
            context = _build_guard_context(spec, var_names, values, base_context)
        except Exception:
            return 1.0
        guard_irs = compiled_guards if compiled_guards is not None else compile_guards(spec.guards)
        total = mp.mpf("0")
        for guard_ir in guard_irs:
            try:
                value = guard_violation_value(guard_ir, context)
            except Exception:
                total += mp.mpf("1")
                continue
            if mp.isfinite(value):
                total += value
            else:
                total += mp.mpf("1")
        return float(total)

def _residual_norm(residuals: list[float]) -> float:
    return residual_norm(residuals)

def _build_success_result(
    *,
    values: list[float],
    residuals: list[float],
    precision: int,
    metadata: dict[str, Any],
    answer_value: Any,
) -> SolveResult:
    return build_success_result(
        values=values,
        residuals=residuals,
        precision=precision,
        metadata=metadata,
        answer_value=answer_value,
    )
