"""High-precision numerical semantic checks for the disposable v3 worker.

This module intentionally proves neither exact configuration identity nor
root-set completeness.  It replays the untouched numerical DSL at independent
precisions and emits the concrete gates required by
``NUMERICAL_SUCCESS_POLICY_V3.json``.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from typing import Any, Mapping, Sequence

from mpmath import mp


ABSOLUTE_GATE_TEXT = "1e-100"
HARD_STRUCTURAL_THRESHOLD = mp.mpf("1e-12")
PARAMETRIC_FUNCTIONS = {
    "InscribedPolygon",
    "PointOnArc",
    "PointOnCircle",
    "PointOnSegment",
}
FIXED_UNIT_INTERVAL_PARAMETER_POSITIONS = {
    "PointOnArc": 1,
    "PointOnCircle": 1,
    "PointOnSegment": 2,
}


class NumericalSemanticError(ValueError):
    """The source or a numerical replay could not satisfy the v3 contract."""


def canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise NumericalSemanticError("value is not canonical JSON") from error


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def mp_text(value: object, digits: int) -> str:
    return mp.nstr(value, n=max(40, int(digits)), strip_zeros=False)


def precision_noise_floor(dps: int):
    return mp.power(10, -max(12, int(dps) // 2))


def _finite_mpf(value: object, label: str):
    try:
        result = mp.mpf(value)
    except Exception as error:
        raise NumericalSemanticError(f"{label} is not an MP scalar") from error
    if not mp.isfinite(result):
        raise NumericalSemanticError(f"{label} is not finite")
    return result


def _trace_signature(trace: object) -> list[dict[str, object]]:
    return [
        {
            "branch_index": int(entry.branch_index),
            "kind": str(entry.kind),
        }
        for entry in getattr(trace, "entries", ())
    ]


def selector_trace_evidence(trace: object, *, dps: int) -> dict[str, object]:
    floor = precision_noise_floor(dps)
    entries: list[dict[str, object]] = []
    stable = True
    finite_margins = []
    for entry in getattr(trace, "entries", ()):
        margin = mp.mpf(entry.margin)
        finite = bool(mp.isfinite(margin))
        if finite:
            finite_margins.append(margin)
            margin_ok = bool(margin > floor)
            stable = stable and margin_ok
        else:
            margin_ok = True
        entries.append(
            {
                "branch_index": int(entry.branch_index),
                "kind": str(entry.kind),
                "margin": mp_text(margin, min(120, dps)) if finite else None,
                "margin_unbounded": not finite,
                "margin_above_noise_floor": margin_ok,
            }
        )
    return {
        "signature": _trace_signature(trace),
        "entries": entries,
        "noise_floor": mp_text(floor, min(120, dps)),
        "minimum_finite_margin": (
            None if not finite_margins else mp_text(min(finite_margins), min(120, dps))
        ),
        "stable": bool(stable),
    }


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _unit_interval_parameter_nodes(
    node: ast.Call,
    function_name: str,
) -> tuple[tuple[int, ast.AST], ...]:
    """Return only the intrinsic unit-interval arguments of one DSL call.

    The primitive signatures, rather than argument order guesses, define the
    domain-bearing positions.  In particular, unrelated keyword arguments are
    never interpreted as parameters and every variadic ``InscribedPolygon``
    parameter is retained.
    """

    if function_name == "InscribedPolygon":
        parameters = node.args[1:]
        if any(isinstance(parameter, ast.Starred) for parameter in parameters):
            raise NumericalSemanticError(
                "InscribedPolygon starred parameter domains are unsupported"
            )
        return tuple(enumerate(parameters))

    position = FIXED_UNIT_INTERVAL_PARAMETER_POSITIONS[function_name]
    positional = node.args[position] if len(node.args) > position else None
    keyword_parameters = [
        keyword.value for keyword in node.keywords if keyword.arg == "t"
    ]
    if len(keyword_parameters) > 1 or (positional is not None and keyword_parameters):
        raise NumericalSemanticError(
            f"{function_name} parameter is specified more than once"
        )
    parameter = positional or (keyword_parameters[0] if keyword_parameters else None)
    if parameter is None:
        raise NumericalSemanticError(f"{function_name} has no parameter argument")
    return ((0, parameter),)


def intrinsic_domain_parameter_occurrences(
    source_document: Mapping[str, Any],
) -> tuple[dict[str, object], ...]:
    """Inventory every intrinsic ``0 <= t <= 1`` obligation in source AST.

    Occurrences, rather than only direct variable names, are recorded.  This
    keeps expression parameters such as ``u + v`` and repeated uses of one
    variable source-bound and independently replayable.
    """

    construction = source_document.get("construction") or []
    if not isinstance(construction, list):
        raise NumericalSemanticError("source construction is malformed")
    result: list[dict[str, object]] = []
    for construction_index, item in enumerate(construction):
        if not isinstance(item, Mapping) or not isinstance(item.get("expr"), str):
            raise NumericalSemanticError("source construction is malformed")
        expression_text = str(item["expr"])
        try:
            expression = ast.parse(expression_text, mode="eval")
        except SyntaxError as error:
            raise NumericalSemanticError(
                "source construction expression is malformed"
            ) from error
        occurrence_by_function: dict[str, int] = {}
        for node in ast.walk(expression):
            if not isinstance(node, ast.Call):
                continue
            function_name = _call_name(node)
            if function_name not in PARAMETRIC_FUNCTIONS:
                continue
            call_occurrence = occurrence_by_function.get(function_name, 0)
            occurrence_by_function[function_name] = call_occurrence + 1
            for parameter_index, parameter in _unit_interval_parameter_nodes(
                node, function_name
            ):
                argument_ast = ast.dump(
                    parameter, annotate_fields=True, include_attributes=False
                )
                base_label = (
                    f"construction[{construction_index}].intrinsic."
                    f"{function_name}[{call_occurrence}].parameter[{parameter_index}]"
                )
                result.append(
                    {
                        "base_label": base_label,
                        "construction_label": f"construction[{construction_index}]",
                        "function": function_name,
                        "call_occurrence": call_occurrence,
                        "parameter_index": parameter_index,
                        "argument_expression": ast.unparse(parameter),
                        "argument_ast_sha256": hashlib.sha256(
                            argument_ast.encode("utf-8")
                        ).hexdigest(),
                    }
                )
    return tuple(result)


def intrinsic_domain_bound_entries(
    source_document: Mapping[str, Any],
) -> tuple[dict[str, object], ...]:
    """Return deterministic authority inventory entries for intrinsic bounds."""

    result: list[dict[str, object]] = []
    for occurrence in intrinsic_domain_parameter_occurrences(source_document):
        for side in ("lower", "upper"):
            result.append(
                {
                    **occurrence,
                    "label": f"{occurrence['base_label']}.{side}",
                    "strict": False,
                    "side": side,
                    "domain": "closed_unit_interval",
                }
            )
    return tuple(result)


def intrinsic_domain_bounds_replay(
    source_document: Mapping[str, Any],
    context: Mapping[str, object],
    *,
    dps: int,
) -> dict[str, dict[str, object]]:
    """Replay all intrinsic primitive domains in one fresh precision lane."""

    from geosolver.geometry.mp.mp_primitives_intersections import capture_selector_trace
    from geosolver.ir.compiler import safe_eval_expr_hp

    result: dict[str, dict[str, object]] = {}
    evaluation_context = dict(context)
    evaluation_context.setdefault("mpf", mp.mpf)
    for occurrence in intrinsic_domain_parameter_occurrences(source_document):
        label = str(occurrence["base_label"])
        try:
            # Parameter expressions can contain arbitrary untouched DSL.  Do
            # not append any selectors they evaluate to the construction's
            # already-recorded branch trace a second time.
            with mp.workdps(dps), capture_selector_trace():
                raw_value = safe_eval_expr_hp(
                    str(occurrence["argument_expression"]), evaluation_context
                )
            value = _finite_mpf(raw_value, f"{label} parameter")
        except NumericalSemanticError:
            raise
        except Exception as error:
            raise NumericalSemanticError(f"{label} parameter replay failed") from error
        margins = {"lower": value, "upper": mp.mpf("1") - value}
        for side, margin in margins.items():
            result[f"{label}.{side}"] = {
                "passed": bool(margin >= 0),
                "margin": margin,
                "strict": False,
            }
    return result


def _semantic_parameter_variables(
    source_document: Mapping[str, Any], variable_names: Sequence[str]
) -> tuple[str, ...]:
    known = set(variable_names)
    result: list[str] = []
    for occurrence in intrinsic_domain_parameter_occurrences(source_document):
        try:
            candidate = ast.parse(
                str(occurrence["argument_expression"]), mode="eval"
            ).body
        except SyntaxError:
            continue
        if isinstance(candidate, ast.Name) and candidate.id in known:
            result.append(candidate.id)
    return tuple(dict.fromkeys(result))


def source_uses_unsupported_ordinal_intersection(
    source_document: Mapping[str, Any],
) -> bool:
    """The current MP Intersect implementation ignores ``n=``; fail closed."""

    for item in source_document.get("construction") or ():
        if not isinstance(item, Mapping) or not isinstance(item.get("expr"), str):
            continue
        try:
            expression = ast.parse(str(item["expr"]), mode="eval")
        except SyntaxError:
            continue
        for node in ast.walk(expression):
            if not isinstance(node, ast.Call) or _call_name(node) != "Intersect":
                continue
            if any(keyword.arg == "n" for keyword in node.keywords):
                return True
    return False


def _source_number(value: object, *, precision: int):
    from geosolver._internal.autosolve.answer import _eval_exact_to_mpf

    if isinstance(value, Decimal):
        return mp.mpf(str(value))
    if isinstance(value, str):
        return _eval_exact_to_mpf(value, int(precision))
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NumericalSemanticError("source bound is not numeric")
    return mp.mpf(str(value))


def bounds_evidence(
    source_document: Mapping[str, Any],
    exact_source_document: Mapping[str, Any],
    variable_names: Sequence[str],
    point: Sequence[object],
    *,
    dps: int,
) -> dict[str, object]:
    if len(point) != len(variable_names):
        raise NumericalSemanticError("bound replay dimension mismatch")
    by_name = {
        name: mp.mpf(value) for name, value in zip(variable_names, point, strict=True)
    }
    entries: list[dict[str, object]] = []
    all_inside = True

    raw_bounds = exact_source_document.get("bounds")
    if raw_bounds is not None:
        if not isinstance(raw_bounds, list):
            raise NumericalSemanticError("source bounds are malformed")
        for index, raw in enumerate(raw_bounds[: len(variable_names)]):
            if raw is None:
                continue
            if not isinstance(raw, list) or len(raw) != 2:
                raise NumericalSemanticError("source bound entry is malformed")
            lower = _source_number(raw[0], precision=dps)
            upper = _source_number(raw[1], precision=dps)
            value = by_name[variable_names[index]]
            lower_margin = value - lower
            upper_margin = upper - value
            inside = bool(lower_margin >= 0 and upper_margin >= 0)
            all_inside = all_inside and inside
            entries.append(
                {
                    "kind": "source_explicit_inclusive",
                    "variable": variable_names[index],
                    "inside": inside,
                    "lower_margin": mp_text(lower_margin, min(120, dps)),
                    "upper_margin": mp_text(upper_margin, min(120, dps)),
                }
            )

    for name in _semantic_parameter_variables(source_document, variable_names):
        value = by_name[name]
        lower_margin = value
        upper_margin = mp.mpf("1") - value
        inside = bool(lower_margin >= 0 and upper_margin >= 0)
        all_inside = all_inside and inside
        entries.append(
            {
                "kind": "semantic_parametric_inclusive_0_1",
                "variable": name,
                "inside": inside,
                "lower_margin": mp_text(lower_margin, min(120, dps)),
                "upper_margin": mp_text(upper_margin, min(120, dps)),
            }
        )
    return {
        "entries": entries,
        "semantic_bound_count": len(entries),
        "all_inside": bool(all_inside),
        "inferred_search_envelopes_used": False,
    }


def _point_xy(value: object, label: str):
    if not hasattr(value, "x") or not hasattr(value, "y"):
        raise NumericalSemanticError(f"{label} is not a point")
    return _finite_mpf(value.x, f"{label}.x"), _finite_mpf(value.y, f"{label}.y")


def _acute_triangle_margin(call: ast.Call, context: Mapping[str, object]):
    if len(call.args) != 3 or not all(isinstance(arg, ast.Name) for arg in call.args):
        raise NumericalSemanticError("AssumeAcute arguments are not named points")
    points = [_point_xy(context[arg.id], f"AssumeAcute.{arg.id}") for arg in call.args]
    margins = []
    for vertex_index in range(3):
        vertex = points[vertex_index]
        first = points[(vertex_index + 1) % 3]
        second = points[(vertex_index + 2) % 3]
        ux, uy = first[0] - vertex[0], first[1] - vertex[1]
        vx, vy = second[0] - vertex[0], second[1] - vertex[1]
        dot = ux * vx + uy * vy
        scale = max(
            mp.mpf("1"),
            mp.sqrt(ux * ux + uy * uy) * mp.sqrt(vx * vx + vy * vy),
        )
        margins.append(dot / scale)
    return min(margins)


def _guard_numeric(expr: str, context: Mapping[str, object]):
    from geosolver.ir.compiler import safe_eval_expr_hp

    return _finite_mpf(
        safe_eval_expr_hp(expr, dict(context)), f"guard expression {expr}"
    )


def _guard_profile(guard: object, context: Mapping[str, object], *, dps: int):
    from geosolver._internal.autosolve.guards.compile import guard_hard_satisfied

    kind = str(guard.kind)
    floor = precision_noise_floor(dps)
    satisfied = bool(guard_hard_satisfied(guard, dict(context)))
    base: dict[str, object] = {
        "kind": kind,
        "source": str(guard.source),
        "satisfied": satisfied,
        "strict_margin_required": False,
        "strict_margin_available": True,
        "strict_margin": None,
        "strict_margin_above_noise_floor": True,
        "children": [],
    }
    margin = None
    strict = False
    available = True
    if kind == "compare":
        lhs = _guard_numeric(str(guard.lhs_expr), context)
        rhs = _guard_numeric(str(guard.rhs_expr), context)
        scale = max(mp.mpf("1"), abs(lhs), abs(rhs))
        operator = str(guard.operator)
        if operator == ">":
            margin, strict = (lhs - rhs) / scale, True
        elif operator == "<":
            margin, strict = (rhs - lhs) / scale, True
        elif operator == "!=":
            margin, strict = abs(lhs - rhs) / scale, True
        elif operator == ">=":
            margin = (lhs - rhs) / scale
        elif operator == "<=":
            margin = (rhs - lhs) / scale
        elif operator == "==":
            margin = -abs(lhs - rhs) / scale
        else:
            available = False
    elif kind in {"bound", "bound_open"}:
        value = _guard_numeric(str(guard.lhs_expr), context)
        distances = []
        scale = max(mp.mpf("1"), abs(value))
        if guard.lower_expr is not None:
            lower = _guard_numeric(str(guard.lower_expr), context)
            scale = max(scale, abs(lower))
            distances.append(value - lower)
        if guard.upper_expr is not None:
            upper = _guard_numeric(str(guard.upper_expr), context)
            scale = max(scale, abs(upper))
            distances.append(upper - value)
        margin = min(distances, default=mp.inf) / scale
        strict = kind == "bound_open"
    elif kind == "residual":
        try:
            parsed = ast.parse(str(guard.source), mode="eval").body
        except SyntaxError:
            parsed = None
        if isinstance(parsed, ast.Call) and _call_name(parsed) == "AssumeAcute":
            margin = _acute_triangle_margin(parsed, context)
            strict = True
        else:
            # Equality-like residual guards do not need a strict interior.
            # Unknown inequality-style residual guards must not manufacture a
            # boundary clearance.
            name = _call_name(parsed) if isinstance(parsed, ast.Call) else None
            strict = name in {"AssumeObtuse", "AssumeOrder"}
            available = not strict
    elif kind in {"logical_and", "logical_or", "logical_not"}:
        children = [_guard_profile(child, context, dps=dps) for child in guard.children]
        base["children"] = children
        strict_children = [
            child for child in children if child["strict_margin_required"]
        ]
        strict = bool(strict_children)
        available = all(child["strict_margin_available"] for child in strict_children)
        margins = [
            mp.mpf(child["strict_margin"])
            for child in strict_children
            if child["strict_margin"] is not None
        ]
        if margins:
            margin = min(margins) if kind != "logical_or" else max(margins)
    else:
        available = not satisfied

    if margin is not None and mp.isfinite(margin):
        base["strict_margin"] = mp_text(margin, min(120, dps))
    base["strict_margin_required"] = strict
    base["strict_margin_available"] = available
    base["strict_margin_above_noise_floor"] = bool(
        not strict or (available and margin is not None and margin > floor)
    )
    return base


def guards_evidence(
    compiled_guards: Sequence[object],
    context: Mapping[str, object],
    *,
    dps: int,
) -> dict[str, object]:
    profiles = [_guard_profile(guard, context, dps=dps) for guard in compiled_guards]
    return {
        "profiles": profiles,
        "truth_signature": [bool(profile["satisfied"]) for profile in profiles],
        "all_satisfied": all(bool(profile["satisfied"]) for profile in profiles),
        "strict_margins_available": all(
            not profile["strict_margin_required"]
            or bool(profile["strict_margin_available"])
            for profile in profiles
        ),
        "strict_margins_positive": all(
            bool(profile["strict_margin_above_noise_floor"]) for profile in profiles
        ),
        "noise_floor": mp_text(precision_noise_floor(dps), min(120, dps)),
    }


def strict_output_descriptor(owned_descriptor: Mapping[str, Any]) -> dict[str, object]:
    coefficients_high = [
        int(value) for value in owned_descriptor["minimal_polynomial_high_to_low"]
    ]
    if len(coefficients_high) < 2:
        raise NumericalSemanticError("minimal polynomial has no positive degree")
    interval = owned_descriptor["isolating_interval"]
    left = Fraction(str(interval["left"]))
    right = Fraction(str(interval["right"]))
    if left == right:
        if len(coefficients_high) != 2:
            raise NumericalSemanticError(
                "only a linear rational root may have point isolation"
            )
        # SymPy represents a rational real root by the point interval [q,q].
        # The scorer requires an open isolator and also requires every point in
        # it to lie within 1e-100 of the 1024-bit target.  A fixed exact
        # rational radius keeps both properties without truth-informed data.
        radius = Fraction(1, 10**110)
        left -= radius
        right += radius
    if left >= right:
        raise NumericalSemanticError("target isolating interval is not ordered")
    return {
        "coefficients": list(reversed(coefficients_high)),
        "root_index": int(interval["real_root_index"]) + 1,
        "lower": {"numerator": left.numerator, "denominator": left.denominator},
        "upper": {"numerator": right.numerator, "denominator": right.denominator},
    }


def descriptor_identity(descriptor: Mapping[str, Any]) -> tuple[tuple[int, ...], int]:
    return (
        tuple(int(value) for value in descriptor["coefficients"]),
        int(descriptor["root_index"]),
    )


def max_abs_disagreement(left: Sequence[str], right: Sequence[str]):
    if len(left) != len(right):
        raise NumericalSemanticError("coordinate lane dimension mismatch")
    return max(
        (abs(mp.mpf(a) - mp.mpf(b)) for a, b in zip(left, right, strict=True)),
        default=mp.mpf("0"),
    )


__all__ = [
    "ABSOLUTE_GATE_TEXT",
    "NumericalSemanticError",
    "bounds_evidence",
    "intrinsic_domain_bound_entries",
    "intrinsic_domain_bounds_replay",
    "intrinsic_domain_parameter_occurrences",
    "canonical_bytes",
    "canonical_sha256",
    "descriptor_identity",
    "guards_evidence",
    "max_abs_disagreement",
    "mp_text",
    "precision_noise_floor",
    "selector_trace_evidence",
    "source_uses_unsupported_ordinal_intersection",
    "strict_output_descriptor",
]
