"""Shared hard-feasibility evaluation helpers."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from mpmath import mp

from geosolver._internal.pipeline.contracts.hard_feasibility_check import (
    HardFeasibilityCheck,
    KIND_GUARD,
    KIND_INTERSECTION_EXCLUDE_DISTINCT,
    KIND_INTERSECTION_SELECTION_TRACE,
    KIND_LINE_DISTINCT,
    KIND_TRIANGLE_NONDEGENERATE,
)
from geosolver._internal.pipeline.contracts.hard_feasibility_snapshot import (
    HardFeasibilitySnapshot,
)
from geosolver._internal.pipeline.contracts.problem_bundle import ProblemBundle
from geosolver._internal.pipeline.contracts.selection_trace_entry import SelectionTraceEntry
from geosolver._internal.pipeline.evaluator.selection_trace import (
    capture_selection_trace,
    index_selection_trace,
    use_selection_symbol,
)
from geosolver._internal.solver.precision.type_guards.boundary_float_to_mpf import (
    BoundaryOrigin,
    boundary_float_to_mpf,
)
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat
from geosolver._internal.solver.precision.type_guards.strict_to_mpf import strict_to_mpf

LINE_MARGIN_MIN = mp.mpf("1e-12")
TRIANGLE_MARGIN_MIN = mp.mpf("1e-14")
INTERSECTION_MARGIN_MIN = mp.mpf("1e-12")
SELECTION_MIN_CANDIDATE_COUNT = 2


@dataclass(frozen=True)
class HardFeasibilityRuntimeState:
    """Runtime state materialized for check evaluation."""

    context: dict[str, object]
    trace_entries: dict[str, SelectionTraceEntry]


def _to_mpf_value(value: object, *, allow_float: bool, context: str) -> MPFloat | None:
    if isinstance(value, float):
        if not allow_float:
            return None
        return boundary_float_to_mpf(value, origin=BoundaryOrigin.INITIAL_POINT)
    try:
        return strict_to_mpf(value, context=context)
    except Exception:
        if not allow_float:
            return None
    try:
        return boundary_float_to_mpf(float(value), origin=BoundaryOrigin.INITIAL_POINT)
    except Exception:
        return None


def _point_coordinates(
    value: object,
    *,
    allow_float: bool,
    context: str,
) -> tuple[MPFloat, MPFloat] | None:
    if not (hasattr(value, "x") and hasattr(value, "y")):
        return None
    x_value = _to_mpf_value(getattr(value, "x"), allow_float=allow_float, context=f"{context}.x")
    y_value = _to_mpf_value(getattr(value, "y"), allow_float=allow_float, context=f"{context}.y")
    if x_value is None or y_value is None:
        return None
    return x_value, y_value


def _point_distance_margin(
    first: object,
    second: object,
    *,
    allow_float: bool,
    context: str,
) -> MPFloat | None:
    first_coords = _point_coordinates(first, allow_float=allow_float, context=f"{context}.first")
    second_coords = _point_coordinates(second, allow_float=allow_float, context=f"{context}.second")
    if first_coords is None or second_coords is None:
        return None
    x1, y1 = first_coords
    x2, y2 = second_coords
    dx = x1 - x2
    dy = y1 - y2
    distance = mp.sqrt((dx * dx) + (dy * dy))
    scale = max(abs(x1), abs(y1), abs(x2), abs(y2), mp.mpf("1"))
    return distance / scale


def _triangle_margin(
    a: object,
    b: object,
    c: object,
    *,
    allow_float: bool,
    context: str,
) -> MPFloat | None:
    a_coords = _point_coordinates(a, allow_float=allow_float, context=f"{context}.a")
    b_coords = _point_coordinates(b, allow_float=allow_float, context=f"{context}.b")
    c_coords = _point_coordinates(c, allow_float=allow_float, context=f"{context}.c")
    if a_coords is None or b_coords is None or c_coords is None:
        return None
    ax, ay = a_coords
    bx, by = b_coords
    cx, cy = c_coords
    twice_area = abs(((bx - ax) * (cy - ay)) - ((by - ay) * (cx - ax)))
    scale = max(abs(ax), abs(ay), abs(bx), abs(by), abs(cx), abs(cy), mp.mpf("1"))
    return twice_area / (scale * scale)


def _expected_selector_kind(check_id: str) -> str | None:
    if check_id.endswith(":near"):
        return "near"
    if check_id.endswith(":far"):
        return "far"
    if check_id.endswith(":exclude"):
        return "exclude"
    return None


def _evaluate_guard_check(
    *,
    check: HardFeasibilityCheck,
    guard_ok: bool,
    guard_violations: tuple[str, ...],
) -> tuple[bool, str | None, MPFloat | None]:
    if guard_ok:
        return True, None, mp.mpf("1")
    if guard_violations:
        return False, guard_violations[0], None
    return False, check.check_id, None


def _evaluate_line_distinct_check(
    *,
    check: HardFeasibilityCheck,
    state: HardFeasibilityRuntimeState,
    allow_float: bool,
) -> tuple[bool, str | None, MPFloat | None]:
    if len(check.symbol_names) < 2:
        return False, f"{check.check_id}:missing_symbols", None
    first = state.context.get(check.symbol_names[0])
    second = state.context.get(check.symbol_names[1])
    if first is None or second is None:
        return False, f"{check.check_id}:missing_symbol_value", None
    margin = _point_distance_margin(
        first,
        second,
        allow_float=allow_float,
        context=check.check_id,
    )
    if margin is None:
        return False, f"{check.check_id}:margin_unavailable", None
    if margin <= LINE_MARGIN_MIN:
        return False, f"{check.check_id}:line_not_distinct", margin
    return True, None, margin


def _evaluate_triangle_check(
    *,
    check: HardFeasibilityCheck,
    state: HardFeasibilityRuntimeState,
    allow_float: bool,
) -> tuple[bool, str | None, MPFloat | None]:
    if len(check.symbol_names) < 3:
        return False, f"{check.check_id}:missing_symbols", None
    a = state.context.get(check.symbol_names[0])
    b = state.context.get(check.symbol_names[1])
    c = state.context.get(check.symbol_names[2])
    if a is None or b is None or c is None:
        return False, f"{check.check_id}:missing_symbol_value", None
    margin = _triangle_margin(
        a,
        b,
        c,
        allow_float=allow_float,
        context=check.check_id,
    )
    if margin is None:
        return False, f"{check.check_id}:margin_unavailable", None
    if margin <= TRIANGLE_MARGIN_MIN:
        return False, f"{check.check_id}:triangle_degenerate", margin
    return True, None, margin


def _evaluate_intersection_exclude_check(
    *,
    check: HardFeasibilityCheck,
    state: HardFeasibilityRuntimeState,
    allow_float: bool,
) -> tuple[bool, str | None, MPFloat | None]:
    if len(check.symbol_names) < 2:
        return False, f"{check.check_id}:missing_symbols", None
    candidate = state.context.get(check.symbol_names[0])
    exclude_symbol = state.context.get(check.symbol_names[1])
    if candidate is None or exclude_symbol is None:
        return False, f"{check.check_id}:missing_symbol_value", None
    margin = _point_distance_margin(
        candidate,
        exclude_symbol,
        allow_float=allow_float,
        context=check.check_id,
    )
    if margin is None:
        return False, f"{check.check_id}:margin_unavailable", None
    if margin <= INTERSECTION_MARGIN_MIN:
        return False, f"{check.check_id}:exclude_not_distinct", margin
    return True, None, margin


def _evaluate_selection_trace_check(
    *,
    check: HardFeasibilityCheck,
    state: HardFeasibilityRuntimeState,
) -> tuple[bool, str | None, MPFloat | None]:
    symbol_name = check.reference_symbol
    if symbol_name is None and check.symbol_names:
        symbol_name = check.symbol_names[0]
    if symbol_name is None:
        return False, f"{check.check_id}:missing_symbol", None
    trace = state.trace_entries.get(symbol_name)
    expected_kind = _expected_selector_kind(check.check_id)
    if trace is None:
        if expected_kind in {"near", "far"} and symbol_name in state.context:
            return True, None, mp.mpf("1")
        return False, f"{check.check_id}:trace_not_found", None
    if expected_kind is not None and trace.selector_kind != expected_kind:
        return False, f"{check.check_id}:selector_mismatch", None
    if trace.candidate_count < SELECTION_MIN_CANDIDATE_COUNT:
        return False, f"{check.check_id}:insufficient_candidates", None
    return True, None, mp.mpf(trace.candidate_count - 1)


def _build_runtime_state(
    *,
    bundle: ProblemBundle,
    values: Sequence[object],
    eval_expr: Callable[[str, dict[str, object]], object],
    cast_value: Callable[[object], object],
) -> HardFeasibilityRuntimeState:
    context: dict[str, object] = dict(bundle.base_context)
    for symbol_name, value in zip(bundle.var_names, values):
        context[symbol_name] = cast_value(value)
    with capture_selection_trace() as trace_entries:
        for item in bundle.spec.construction:
            with use_selection_symbol(item.name):
                try:
                    context[item.name] = eval_expr(item.expr, context)
                except Exception:
                    context[item.name] = None
    return HardFeasibilityRuntimeState(
        context=context,
        trace_entries=index_selection_trace(tuple(trace_entries)),
    )


def _evaluate_single_check(
    *,
    check: HardFeasibilityCheck,
    state: HardFeasibilityRuntimeState,
    allow_float: bool,
    guard_ok: bool,
    guard_violations: tuple[str, ...],
) -> tuple[bool, str | None, MPFloat | None]:
    if check.kind == KIND_GUARD:
        return _evaluate_guard_check(
            check=check,
            guard_ok=guard_ok,
            guard_violations=guard_violations,
        )
    if check.kind == KIND_LINE_DISTINCT:
        return _evaluate_line_distinct_check(
            check=check,
            state=state,
            allow_float=allow_float,
        )
    if check.kind == KIND_TRIANGLE_NONDEGENERATE:
        return _evaluate_triangle_check(
            check=check,
            state=state,
            allow_float=allow_float,
        )
    if check.kind == KIND_INTERSECTION_EXCLUDE_DISTINCT:
        return _evaluate_intersection_exclude_check(
            check=check,
            state=state,
            allow_float=allow_float,
        )
    if check.kind == KIND_INTERSECTION_SELECTION_TRACE:
        return _evaluate_selection_trace_check(
            check=check,
            state=state,
        )
    return False, f"{check.check_id}:unsupported_kind", None


def _is_all_input_finite(values: Sequence[object], *, allow_float: bool) -> bool:
    for index, value in enumerate(values):
        as_mpf = _to_mpf_value(
            value,
            allow_float=allow_float,
            context=f"hard_feasibility.values[{index}]",
        )
        if as_mpf is None or (not mp.isfinite(as_mpf)):
            return False
    return True


def evaluate_hard_feasibility(
    *,
    bundle: ProblemBundle,
    checks: tuple[HardFeasibilityCheck, ...],
    values: Sequence[object],
    eval_expr: Callable[[str, dict[str, object]], object],
    cast_value: Callable[[object], object],
    allow_float: bool,
    guard_ok: bool,
    guard_violations: tuple[str, ...],
) -> HardFeasibilitySnapshot:
    """Evaluate hard-feasibility checks and return aggregated snapshot."""
    if not checks:
        return HardFeasibilitySnapshot(
            hard_feasible=True,
            failure_tags=(),
            min_margin=None,
        )
    if not _is_all_input_finite(values, allow_float=allow_float):
        return HardFeasibilitySnapshot(
            hard_feasible=False,
            failure_tags=("non_finite_input",),
            min_margin=None,
        )
    try:
        state = _build_runtime_state(
            bundle=bundle,
            values=values,
            eval_expr=eval_expr,
            cast_value=cast_value,
        )
    except Exception as exc:
        return HardFeasibilitySnapshot(
            hard_feasible=False,
            failure_tags=(f"construction_error:{exc}",),
            min_margin=None,
        )
    failure_tags: list[str] = []
    passed_margins: list[MPFloat] = []
    for check in checks:
        ok, failure_tag, margin = _evaluate_single_check(
            check=check,
            state=state,
            allow_float=allow_float,
            guard_ok=guard_ok,
            guard_violations=guard_violations,
        )
        if ok:
            if margin is not None and mp.isfinite(margin):
                passed_margins.append(margin)
            continue
        if failure_tag is None:
            failure_tags.append(check.check_id)
            continue
        failure_tags.append(failure_tag)
    min_margin = min(passed_margins) if passed_margins else None
    return HardFeasibilitySnapshot(
        hard_feasible=(len(failure_tags) == 0),
        failure_tags=tuple(failure_tags),
        min_margin=min_margin,
    )
