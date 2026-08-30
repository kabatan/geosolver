"""Smooth search penalty for compiled guard conditions."""

from __future__ import annotations

from typing import Any

from mpmath import mp

from geosolver.engine.standard.interpreter.context import _get_high_precision_context
from geosolver.engine.standard.interpreter.guards.compile import (
    compile_guards,
    guard_hard_satisfied,
    guard_margin_value,
    guard_violation_value,
)
from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import (
    BoundaryOrigin,
    boundary_float_to_mpf,
)
from geosolver.engine.standard.precision.type_guards.strict_to_mpf import strict_to_mpf
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.problem.ir.schema import IRSpec


def _guard_context(
    spec: IRSpec,
    var_names: list[str],
    values: list[Any],
    base_context: dict[str, Any],
) -> dict[str, Any]:
    context = dict(base_context)
    context.update(_get_high_precision_context(80))
    for index, (name, value) in enumerate(zip(var_names, values, strict=True)):
        if isinstance(value, float):
            context[name] = boundary_float_to_mpf(
                value,
                origin=BoundaryOrigin.SCIPY_OPTIMIZE,
            )
        else:
            try:
                context[name] = strict_to_mpf(value, context=f"guard_variable:{name}[{index}]")
            except Exception:
                context[name] = boundary_float_to_mpf(
                    float(value),
                    origin=BoundaryOrigin.SCIPY_OPTIMIZE,
                )
    for item in spec.construction:
        try:
            context[item.name] = safe_eval_expr_hp(item.expr, context)
        except Exception:
            continue
    return context


def guard_violation_penalty(
    values: list[Any],
    *,
    spec: IRSpec,
    var_names: list[str],
    base_context: dict[str, Any],
    compiled_guards: tuple[Any, ...] | None = None,
) -> float:
    if not spec.guards:
        return 0.0
    with mp.workdps(max(int(mp.dps), 80)):
        try:
            context = _guard_context(spec, var_names, values, base_context)
        except Exception:
            return 1.0
        guard_irs = compiled_guards if compiled_guards is not None else compile_guards(spec.guards)
        total = mp.mpf("0")
        for guard_ir in guard_irs:
            try:
                value = guard_violation_value(guard_ir, context)
            except Exception:
                total += 1
                continue
            total += value if mp.isfinite(value) else 1
        return float(total)


def collect_guard_evidence(
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
    with mp.workdps(max(int(mp.dps), 80)):
        try:
            context = _guard_context(spec, var_names, values, base_context)
        except Exception as error:
            return [f"context_error: {error}"], tuple(None for _ in spec.guards)
        guard_irs = compiled_guards if compiled_guards is not None else compile_guards(spec.guards)
        violations: list[str] = []
        margins: list[Any | None] = []
        for index, guard_ir in enumerate(guard_irs):
            try:
                if not guard_hard_satisfied(guard_ir, context):
                    violations.append(f"guard[{index}] returned False")
                    margins.append(None)
                else:
                    margins.append(
                        guard_margin_value(guard_ir, context) if include_margins else mp.inf
                    )
            except Exception as error:
                violations.append(f"guard[{index}] raised: {error}")
                margins.append(None)
        return violations, tuple(margins)


def collect_guard_violations(
    values: list[Any],
    *,
    spec: IRSpec,
    var_names: list[str],
    base_context: dict[str, Any],
    compiled_guards: tuple[Any, ...] | None = None,
) -> list[str]:
    violations, _margins = collect_guard_evidence(
        values,
        spec=spec,
        var_names=var_names,
        base_context=base_context,
        compiled_guards=compiled_guards,
    )
    return violations
