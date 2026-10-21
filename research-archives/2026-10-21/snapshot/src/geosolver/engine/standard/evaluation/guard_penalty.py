"""Smooth search penalty for compiled guard conditions."""

from __future__ import annotations

from typing import Any

from mpmath import mp

from geosolver.engine.standard.evaluation.selection_trace import (
    capture_selection_trace,
    replay_selection_trace,
)
from geosolver.engine.standard.evaluation.snapshots import numerical_snapshot
from geosolver.engine.standard.interpreter.guards.compile import (
    compile_guards,
    guard_hard_satisfied,
    guard_margin_value,
    guard_violation_value,
)
from geosolver.problem.evaluation_trace import capture_calls, replay_calls
from geosolver.problem.ir.schema import IRSpec
from geosolver.runtime.deadline import check_deadline, count_event


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
            snapshot = numerical_snapshot(spec, var_names, values, base_context)
            context = snapshot.for_expressions(spec.guards, partial=True)
        except TimeoutError:
            raise
        except Exception:
            return 1.0
        guard_irs = compiled_guards if compiled_guards is not None else compile_guards(spec.guards)
        total = mp.mpf("0")
        for guard_ir in guard_irs:
            check_deadline()
            try:
                value = guard_violation_value(guard_ir, context)
            except TimeoutError:
                raise
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
            snapshot = numerical_snapshot(spec, var_names, values, base_context)
            key = ("guard_evidence", tuple(spec.guards), bool(include_margins))
        except TimeoutError:
            raise
        except Exception as error:
            return [f"context_error: {error}"], tuple(None for _ in spec.guards)
        if key not in snapshot.memo:
            with capture_calls() as calls, capture_selection_trace() as trace:
                context = snapshot.for_expressions(spec.guards, partial=True)
                guard_irs = (
                    compiled_guards if compiled_guards is not None else compile_guards(spec.guards)
                )
                violations, margins = _evaluate_guards(guard_irs, context, include_margins)
            snapshot.memo[key] = tuple(violations), tuple(margins), tuple(calls), tuple(trace)
        else:
            count_event("guard_evidence_cache_hits")
        violations, margins, calls, trace = snapshot.memo[key]
        replay_calls(calls)
        replay_selection_trace(trace)
        return list(violations), margins


def _evaluate_guards(guards, context, include_margins):
    violations, margins = [], []
    for index, guard in enumerate(guards):
        check_deadline()
        try:
            if not guard_hard_satisfied(guard, context):
                violations.append(f"guard[{index}] returned False")
                margins.append(None)
            else:
                margins.append(guard_margin_value(guard, context) if include_margins else mp.inf)
        except TimeoutError:
            raise
        except Exception as error:
            violations.append(f"guard[{index}] raised: {error}")
            margins.append(None)
    return violations, margins


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
        include_margins=False,
    )
    return violations
