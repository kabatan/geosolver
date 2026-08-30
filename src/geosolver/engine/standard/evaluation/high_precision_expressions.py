"""High-precision construction, target, and residual evaluation."""

from __future__ import annotations

from typing import Any

from mpmath import mp

from geosolver.engine.standard.interpreter.answer import _eval_exact_to_mpf
from geosolver.engine.standard.interpreter.context import _get_high_precision_context
from geosolver.engine.standard.precision.type_guards.ensure_no_float import ensure_no_float
from geosolver.engine.standard.precision.type_guards.high_precision_contamination_error import (
    HighPrecisionContaminationError,
)
from geosolver.engine.standard.precision.type_guards.hp_contract import hp_contract
from geosolver.engine.standard.precision.type_guards.strict_to_mpf import strict_to_mpf
from geosolver.problem.evaluation_trace import evaluation_scope
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.problem.ir.schema import IRSpec


def to_mpf_value(value: Any, *, precision: int, context: str) -> Any:
    if isinstance(value, str):
        return _eval_exact_to_mpf(value, int(precision))
    if isinstance(value, float):
        raise HighPrecisionContaminationError(
            f"float value reached high-precision evaluation at {context}: {value!r}"
        )
    return strict_to_mpf(value, context=context)


def _collect_hp_float_return_symbols(
    context: dict[str, Any],
    destination: list[str] | None,
) -> None:
    if destination is None:
        return
    collector = context.get("_hp_get_float_return_symbols")
    if not callable(collector):
        return
    try:
        symbols = collector()
    except Exception:
        return
    for symbol in symbols:
        symbol_name = str(symbol)
        if symbol_name not in destination:
            destination.append(symbol_name)


@hp_contract(input_names=("values",))
def build_solution_context_high_precision(
    spec: IRSpec,
    var_names: list[str],
    values: list[Any],
    base_context: dict[str, Any],
    precision: int,
) -> dict[str, Any]:
    context = dict(base_context)
    context.update(_get_high_precision_context(int(precision)))
    for name, value in zip(var_names, values, strict=True):
        value_hp = to_mpf_value(value, precision=int(precision), context=f"variable:{name}")
        ensure_no_float(value_hp, context=f"hp_variable:{name}")
        context[name] = value_hp
    for item in spec.construction:
        with evaluation_scope(item.name):
            context[item.name] = safe_eval_expr_hp(item.expr, context)
    return context


def evaluate_target_high_precision(
    target: Any,
    context: dict[str, Any],
    *,
    precision: int,
    index: int,
) -> Any:
    value = safe_eval_expr_hp(target, context) if isinstance(target, str) else target
    return to_mpf_value(value, precision=int(precision), context=f"target:{index}")


@hp_contract(input_names=("values",))
def compute_residual_vector_high_precision(
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
    try:
        context = build_solution_context_high_precision(
            spec,
            var_names,
            values,
            base_context,
            int(precision),
        )
    except HighPrecisionContaminationError:
        raise
    except Exception:
        if failure_indices is not None:
            failure_indices.extend(range(len(spec.constraints)))
        return [mp.nan for _ in spec.constraints]

    residuals: list[Any] = []
    for index, constraint_expr in enumerate(spec.constraints):
        try:
            lhs = to_mpf_value(
                safe_eval_expr_hp(constraint_expr, context),
                precision=int(precision),
                context=f"constraint_lhs:{index}",
            )
            rhs = evaluate_target_high_precision(
                targets[index],
                context,
                precision=int(precision),
                index=index,
            )
            residual = lhs - rhs
            residuals.append(residual)
            if not all(mp.isfinite(value) for value in (lhs, rhs, residual)) and (
                failure_indices is not None
            ):
                failure_indices.append(index)
        except HighPrecisionContaminationError:
            raise
        except Exception:
            residuals.append(mp.nan)
            if failure_indices is not None:
                failure_indices.append(index)
    _collect_hp_float_return_symbols(context, float_return_symbols)
    return residuals


def residual_norm_high_precision(residuals: list[Any]) -> Any:
    terms: list[Any] = []
    for index, residual in enumerate(residuals):
        value = to_mpf_value(residual, precision=80, context=f"residual:{index}")
        if not mp.isfinite(value):
            return mp.inf
        terms.append(value * value)
    return mp.sqrt(mp.fsum(terms)) if terms else mp.mpf("0")
