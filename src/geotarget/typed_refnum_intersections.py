"""General Intersect extension for the typed RefNum runtime.

This module is intentionally independent from ``typed_refnum_ir`` so its
compiler and runtime can integrate the extension without an edit-time cycle.
Admission depends only on resolved operand types, selector kind, and this
semantic ABI.  No problem identity, corpus metadata, or symbol spelling is
accepted by the API.

The formulas, candidate order, clamping, and double selector behavior mirror
the frozen SymPy geometry runtime.  High-precision selector authority remains
outside this module: the typed route emits a double diagnostic trace, while HP,
guards, hard feasibility, and exact authority continue to evaluate the source
selector through the frozen evaluator.  This extension does not introduce a
new HP trace-replay path.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Literal

from sympy import Max, N, sqrt

SEMANTIC_ABI = "geotarget.typed-refnum-intersect/sympy-1.14-selector-v1"
OperandType = Literal["line2", "circle2"]
SELECTOR_TYPE_SCHEMA = {
    "n": "exact_int",
    "exclude": "point2",
    "near": "point2",
    "far": "point2",
}


class UnsupportedTypedIntersect(RuntimeError):
    """The complete problem must use the reference evaluator."""


class TypedIntersectRuntimeFault(RuntimeError):
    """The frozen intersection or selector failed at runtime."""


@dataclass(frozen=True)
class IntersectSupportKey:
    operand_types: tuple[OperandType, OperandType]
    selector_kind: str
    selector_operand_types: tuple[tuple[str, str], ...]
    semantic_abi: str = SEMANTIC_ABI


@dataclass(frozen=True)
class IntersectPlan:
    """Identity-free compiler payload for one typed Intersect node."""

    support_key: IntersectSupportKey
    ordinal: int | None = None

    @property
    def result_type(self) -> str:
        if self.support_key.selector_kind == "exclude":
            return "point_or_list"
        if self.support_key.selector_kind == "none" and self.support_key.operand_types != (
            "line2",
            "line2",
        ):
            return "point_list"
        return "point2"


@dataclass(frozen=True)
class DoubleSelectorTraceEntry:
    selector_kind: str
    candidate_count: int
    selected_original_index: int
    selected_active_index: int
    ambient_dps: int
    hp_authority_complete: bool = False


@dataclass(frozen=True)
class IntersectEvaluation:
    value: Any
    trace: DoubleSelectorTraceEntry | None
    hp_authority_complete: bool


def compile_intersect_extension(
    operand_types: tuple[str, str],
    selectors: Mapping[str, Any],
    *,
    selector_operand_types: Mapping[str, str] | None = None,
) -> IntersectPlan:
    """Compile selector literals without reading a problem or construction ID."""

    if operand_types not in {
        ("line2", "line2"),
        ("line2", "circle2"),
        ("circle2", "line2"),
        ("circle2", "circle2"),
    }:
        raise UnsupportedTypedIntersect(f"unsupported Intersect operand types: {operand_types!r}")
    unknown = set(selectors) - {"n", "exclude", "near", "far"}
    if unknown:
        raise UnsupportedTypedIntersect(f"unsupported Intersect selector: {sorted(unknown)[0]}")
    references = [name for name in ("exclude", "near", "far") if name in selectors]
    if len(references) > 1:
        raise UnsupportedTypedIntersect("exclude, near, and far selectors are mutually exclusive")
    ordinal = selectors.get("n")
    if ordinal is not None:
        if isinstance(ordinal, bool) or not isinstance(ordinal, int):
            raise UnsupportedTypedIntersect("intersection ordinal must be a literal int")
        if ordinal < 1:
            raise UnsupportedTypedIntersect("intersection ordinal must be at least one")
    provided_types = dict(selector_operand_types or {})
    unknown_type_entries = set(provided_types) - set(selectors)
    if unknown_type_entries:
        raise UnsupportedTypedIntersect(
            f"selector type supplied without selector: {sorted(unknown_type_entries)[0]}"
        )
    resolved_types: dict[str, str] = {}
    for name, value in selectors.items():
        resolved = provided_types.get(name)
        if resolved is None:
            if name == "n" and isinstance(value, int) and not isinstance(value, bool):
                resolved = "exact_int"
            else:
                resolved = getattr(value, "result_type", None)
        expected = SELECTOR_TYPE_SCHEMA[name]
        allowed = (
            {"point2", "point_or_list"}
            if expected == "point2"
            else {expected}
        )
        if resolved not in allowed:
            raise UnsupportedTypedIntersect(
                f"selector {name} requires {expected} or a runtime-narrowable union, "
                f"got {resolved or 'unresolved'}"
            )
        resolved_types[name] = resolved
    selector_kind = references[0] if references else "none"
    if ordinal is not None:
        selector_kind = "n" if selector_kind == "none" else f"{selector_kind}+n"
    return IntersectPlan(
        support_key=IntersectSupportKey(
            operand_types=operand_types,  # type: ignore[arg-type]
            selector_kind=selector_kind,
            selector_operand_types=tuple(sorted(resolved_types.items())),
        ),
        ordinal=ordinal,
    )


def require_point_consumer(plan: IntersectPlan) -> None:
    """Reject list/union outputs before compiling a Point-only consumer."""

    if plan.result_type != "point2":
        raise UnsupportedTypedIntersect(
            f"Point consumer cannot accept Intersect result type {plan.result_type}"
        )


def resolve_operand_type(value: Any) -> OperandType:
    """Resolve by the geometry contract, not by a concrete implementation class."""

    if all(hasattr(value, name) for name in ("a", "b", "c")):
        return "line2"
    if hasattr(value, "center") and hasattr(value, "radius"):
        return "circle2"
    raise UnsupportedTypedIntersect(
        f"unsupported Intersect runtime operand: {type(value).__name__}"
    )


def _line_line(first: Any, second: Any, point: Callable[[Any, Any], Any]) -> Any:
    determinant = first.a * second.b - second.a * first.b
    if determinant == 0:
        return None
    return point(
        (first.b * second.c - second.b * first.c) / determinant,
        (first.c * second.a - second.c * first.a) / determinant,
    )


def _line_circle(line: Any, circle: Any, point: Callable[[Any, Any], Any]) -> list[Any]:
    a, b, c = line.a, line.b, line.c
    xc, yc, radius = circle.center.x, circle.center.y, circle.radius
    shifted = a * xc + b * yc + c
    divisor = a**2 + b**2
    if divisor == 0:
        # Frozen default SymPy path uses this sentinel rather than raising.
        return [point(1e9, 1e9), point(1e9, 1e9)]
    distance_squared = shifted**2 / divisor
    delta = radius**2 - distance_squared
    multiplier = sqrt(Max(0, delta) / divisor)
    x0 = -a * shifted / divisor
    y0 = -b * shifted / divisor
    return [
        point(xc + x0 + b * multiplier, yc + y0 - a * multiplier),
        point(xc + x0 - b * multiplier, yc + y0 + a * multiplier),
    ]


def _circle_circle(first: Any, second: Any, point: Callable[[Any, Any], Any]) -> list[Any]:
    x1, y1, radius1 = first.center.x, first.center.y, first.radius
    x2, y2, radius2 = second.center.x, second.center.y, second.radius
    distance_squared = (x1 - x2) ** 2 + (y1 - y2) ** 2
    distance = sqrt(distance_squared)
    along = (radius1**2 - radius2**2 + distance_squared) / (2 * distance)
    height = sqrt(Max(0, radius1**2 - along**2))
    x0 = x1 + along * (x2 - x1) / distance
    y0 = y1 + along * (y2 - y1) / distance
    offset_x = -(y2 - y1) * (height / distance)
    offset_y = (x2 - x1) * (height / distance)
    return [
        point(x0 + offset_x, y0 + offset_y),
        point(x0 - offset_x, y0 - offset_y),
    ]


def _point_equal(first: Any, second: Any) -> bool:
    try:
        if first.x == second.x and first.y == second.y:
            return True
    except Exception:
        pass
    try:
        dx = float(N(first.x - second.x, 15))
        dy = float(N(first.y - second.y, 15))
        return abs(dx) < 1e-14 and abs(dy) < 1e-14
    except Exception:
        return False


def _distance_squared(first: Any, second: Any) -> Any:
    dx = first.x - second.x
    dy = first.y - second.y
    return dx * dx + dy * dy


def _to_float_safe(value: Any, ambient_dps: int) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    precision = max(50, int(ambient_dps * 0.8))
    try:
        return float(N(value, precision))
    except Exception:
        pass
    try:
        return float(value.evalf(precision))
    except Exception:
        return 1e100


def _selector_base_kind(selector_kind: str) -> str:
    return selector_kind.removesuffix("+n")


def _select(
    plan: IntersectPlan,
    result: Any,
    *,
    exclude: Any,
    near: Any,
    far: Any,
    ambient_dps: int,
    frozen_branch_index: int | None,
) -> IntersectEvaluation:
    selector_kind = plan.support_key.selector_kind
    base_kind = _selector_base_kind(selector_kind)
    has_selector = selector_kind != "none"
    if result is None:
        if has_selector:
            raise TypedIntersectRuntimeFault("No intersection found")
        return IntersectEvaluation(None, None, False)
    candidates = list(result) if isinstance(result, list) else [result]
    if not candidates:
        if has_selector:
            raise TypedIntersectRuntimeFault("No intersection found")
        return IntersectEvaluation([], None, False)

    if frozen_branch_index is not None:
        if 0 <= frozen_branch_index < len(candidates):
            trace = DoubleSelectorTraceEntry(
                selector_kind=base_kind,
                candidate_count=len(candidates),
                selected_original_index=frozen_branch_index,
                selected_active_index=frozen_branch_index,
                ambient_dps=ambient_dps,
                hp_authority_complete=False,
            )
            return IntersectEvaluation(candidates[frozen_branch_index], trace, False)
        raise TypedIntersectRuntimeFault("frozen selector branch is outside candidates")

    active: list[tuple[int, Any]] = list(enumerate(candidates))
    if base_kind == "exclude":
        if exclude is None:
            raise TypedIntersectRuntimeFault("exclude selector value is missing")
        tolerance = 10 ** (-ambient_dps + 10)
        tolerance_squared = tolerance * tolerance
        filtered: list[tuple[int, Any]] = []
        for original_index, candidate in active:
            if _point_equal(candidate, exclude):
                continue
            try:
                distance = _to_float_safe(_distance_squared(candidate, exclude), ambient_dps)
                if distance > tolerance_squared:
                    filtered.append((original_index, candidate))
            except Exception:
                filtered.append((original_index, candidate))
        active = filtered
        if not active:
            raise TypedIntersectRuntimeFault("No intersection found after exclusion")
    elif base_kind in {"near", "far"}:
        reference = near if base_kind == "near" else far
        if reference is None:
            raise TypedIntersectRuntimeFault(f"{base_kind} selector value is missing")
        # Frozen selection keeps candidate order when a dynamic selector is
        # not point-like (including a point-or-list union's list arm).
        with suppress(Exception):
            active.sort(
                key=lambda item: _to_float_safe(
                    _distance_squared(item[1], reference), ambient_dps
                ),
                reverse=(base_kind == "far"),
            )
    elif base_kind not in {"none", "n"}:
        raise TypedIntersectRuntimeFault(f"unknown selector kind: {base_kind}")

    if base_kind == "exclude" and plan.ordinal is None:
        original_index, chosen = active[0]
        trace = DoubleSelectorTraceEntry(
            selector_kind="exclude",
            candidate_count=len(active),
            selected_original_index=original_index,
            selected_active_index=0,
            ambient_dps=ambient_dps,
            hp_authority_complete=False,
        )
        # Frozen semantics return the remaining list when exclusion did not
        # reduce it to one candidate.  This is a real union, not "first".
        value = chosen if len(active) == 1 else [item[1] for item in active]
        return IntersectEvaluation(value, trace, False)

    ordinal = plan.ordinal or 1
    if plan.ordinal is not None and ordinal > len(active):
        raise TypedIntersectRuntimeFault(
            f"Intersection #{ordinal} does not exist (found {len(active)})"
        )
    if base_kind == "none" and plan.ordinal is None:
        if len(active) == 1:
            return IntersectEvaluation(active[0][1], None, True)
        return IntersectEvaluation([item[1] for item in active], None, False)

    active_index = ordinal - 1
    original_index, chosen = active[active_index]
    trace_kind = "n" if base_kind == "n" else base_kind
    authority_complete = trace_kind == "n"
    trace = DoubleSelectorTraceEntry(
        selector_kind=trace_kind,
        candidate_count=len(active),
        selected_original_index=original_index,
        selected_active_index=active_index,
        ambient_dps=ambient_dps,
        hp_authority_complete=authority_complete,
    )
    return IntersectEvaluation(chosen, trace, authority_complete)


def evaluate_intersect_extension(
    plan: IntersectPlan,
    first: Any,
    second: Any,
    *,
    point_factory: Callable[[Any, Any], Any],
    exclude: Any = None,
    near: Any = None,
    far: Any = None,
    ambient_dps: int = 15,
    frozen_branch_index: int | None = None,
    require_hp_authority: bool = False,
) -> IntersectEvaluation:
    """Evaluate one typed Intersect node and emit its double branch trace."""

    if isinstance(ambient_dps, bool) or not isinstance(ambient_dps, int):
        raise ValueError("ambient_dps must be an integer")
    if ambient_dps < 1:
        raise ValueError("ambient_dps must be positive")
    runtime_selectors = {"exclude": exclude, "near": near, "far": far}
    for name, expected_type in plan.support_key.selector_operand_types:
        if name == "n":
            continue
        value = runtime_selectors[name]
        if value is None:
            raise TypedIntersectRuntimeFault(f"{name} selector value is missing")
        if hasattr(value, "x") and hasattr(value, "y"):
            actual_type = "point2"
        elif isinstance(value, list):
            actual_type = "point_list"
        else:
            actual_type = "scalar"
        compatible_types = (
            {"point2", "point_list"}
            if expected_type == "point_or_list"
            else {expected_type}
        )
        if actual_type not in compatible_types:
            raise TypedIntersectRuntimeFault(
                f"selector {name} runtime type {actual_type} does not match plan"
            )
    actual_types = (resolve_operand_type(first), resolve_operand_type(second))
    if actual_types != plan.support_key.operand_types:
        raise TypedIntersectRuntimeFault(
            f"Intersect runtime types {actual_types!r} do not match plan"
        )
    if actual_types == ("line2", "line2"):
        result = _line_line(first, second, point_factory)
    elif actual_types == ("line2", "circle2"):
        result = _line_circle(first, second, point_factory)
    elif actual_types == ("circle2", "line2"):
        result = _line_circle(second, first, point_factory)
    else:
        result = _circle_circle(first, second, point_factory)
    evaluated = _select(
        plan,
        result,
        exclude=exclude,
        near=near,
        far=far,
        ambient_dps=ambient_dps,
        frozen_branch_index=frozen_branch_index,
    )
    if require_hp_authority and not evaluated.hp_authority_complete:
        raise UnsupportedTypedIntersect(
            "HP selector authority is record-only; whole-problem fallback required"
        )
    return evaluated


def extension_manifest() -> dict[str, Any]:
    return {
        "semantic_abi": SEMANTIC_ABI,
        "case_specific_routing": False,
        "problem_identity_read": False,
        "support_key_fields": [
            "operand_types",
            "selector_kind",
            "selector_operand_types",
            "semantic_abi",
        ],
        "selector_type_schema": dict(SELECTOR_TYPE_SCHEMA),
        "union_result_policy": "point_or_list_requires_typed_consumer_or_fallback",
        "candidate_order": "frozen_LL_LC_CL_CC",
        "clamp": "sympy_Max_zero",
        "double_selector_trace": True,
        "hp_selector_authority": "frozen_reference_delegate_no_new_replay",
    }
