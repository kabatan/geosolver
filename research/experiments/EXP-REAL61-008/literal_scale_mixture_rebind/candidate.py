"""Source-literal-scale, full-support static discovery prefix.

This disposable EXP-REAL61-008 arm changes proposal points only.  It reads
numeric literals from the untouched source DSL to obtain anonymous *soft*
coordinate scales.  It does not add a bound, finite envelope, coordinate
clamp, gauge, symmetry reduction, variable, or equation.

The caller supplies the frozen source-only prefix.  Ordinals divisible by four
must be its counter-keyed product-Cauchy insurance lane and are returned
bit-for-bit.  The other ordinals rotate through Cauchy, log-symmetric, and
asinh-rational charts.  Each chart maps an open unit cube onto the complete
source domain (or has that domain as its topological support).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import json
import math
import struct
from typing import Iterable, Mapping, Sequence

import numpy as np
from scipy.stats import qmc


SCHEMA = "geotarget.exp-real61-008.literal-scale-mixture-rebind/v1"
INSURANCE_PERIOD = 4
INSURANCE_SOURCE = "counter_product_cauchy"
CAUCHY = "source_literal_product_cauchy"
LOG_SYMMETRIC = "source_literal_log_symmetric"
ASINH_RATIONAL = "source_literal_asinh_rational"
FALLBACK = "same_ordinal_source_only_fallback"
ARMS = (CAUCHY, LOG_SYMMETRIC, ASINH_RATIONAL)
DYADIC_EXPONENTS = (0, 1, -1, 2, -2, 3, -3, 4, -4, 6, -6, 8, -8, 10, -10)

# ``2*u-1`` must remain strictly inside (-1, 1) after Float64 rounding for
# the asinh-rational chart.  This protects a chart parameter endpoint only;
# emitted problem coordinates are never clipped.
_OPEN_LOW = 2.0**-53
_OPEN_HIGH = math.nextafter(1.0, 0.0)
_LANE_TAGS = {
    CAUCHY: b"literal-cauchy",
    LOG_SYMMETRIC: b"literal-log-symmetric",
    ASINH_RATIONAL: b"literal-asinh-rational",
}


@dataclass(frozen=True)
class LiteralScalePlan:
    variable_names: tuple[str, ...]
    scales: np.ndarray
    direct_anchor_counts: tuple[int, ...]
    activation: Mapping[str, object]


@dataclass(frozen=True)
class LiteralScalePrefix:
    points: tuple[np.ndarray, ...]
    sources: tuple[str, ...]
    scale_exponents: tuple[int | None, ...]
    literal_scales: np.ndarray
    sha256: str
    activation: Mapping[str, object]


class ProposalContractError(ValueError):
    """The source-only proposal contract is malformed."""


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _parse_expression(value: object) -> ast.AST | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return ast.Constant(value=value)
    if not isinstance(value, str):
        return None
    try:
        return ast.parse(value, mode="eval").body
    except SyntaxError:
        return None


def _constant_value(node: ast.AST) -> float | None:
    """Evaluate only a small, name-free numeric-expression grammar."""

    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        value = float(node.value)
    elif isinstance(node, ast.Name) and node.id in {"pi", "e"}:
        value = math.pi if node.id == "pi" else math.e
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _constant_value(node.operand)
        if operand is None:
            return None
        value = operand if isinstance(node.op, ast.UAdd) else -operand
    elif isinstance(node, ast.BinOp):
        left = _constant_value(node.left)
        right = _constant_value(node.right)
        if left is None or right is None:
            return None
        try:
            if isinstance(node.op, ast.Add):
                value = left + right
            elif isinstance(node.op, ast.Sub):
                value = left - right
            elif isinstance(node.op, ast.Mult):
                value = left * right
            elif isinstance(node.op, ast.Div):
                value = left / right
            elif isinstance(node.op, ast.Pow):
                value = left**right
            else:
                return None
        except (OverflowError, ValueError, ZeroDivisionError):
            return None
    elif isinstance(node, ast.Call):
        name = _call_name(node)
        arguments = [_constant_value(argument) for argument in node.args]
        if any(argument is None for argument in arguments):
            return None
        values = [float(argument) for argument in arguments if argument is not None]
        try:
            if name == "sqrt" and len(values) == 1:
                value = math.sqrt(values[0])
            elif name == "abs" and len(values) == 1:
                value = abs(values[0])
            elif name == "sin" and len(values) == 1:
                value = math.sin(values[0])
            elif name == "cos" and len(values) == 1:
                value = math.cos(values[0])
            else:
                return None
        except (OverflowError, ValueError, ZeroDivisionError):
            return None
    else:
        return None
    return value if math.isfinite(value) else None


def _maximal_constant_magnitudes(node: ast.AST | None) -> list[float]:
    """Return maximal constant subexpressions, not misleading raw leaves."""

    if node is None:
        return []
    value = _constant_value(node)
    if value is not None:
        magnitude = abs(value)
        return [magnitude] if magnitude > 0.0 else []
    output: list[float] = []
    for child in ast.iter_child_nodes(node):
        output.extend(_maximal_constant_magnitudes(child))
    return output


def _dependencies(
    node: ast.AST | None,
    variable_axes: Mapping[str, int],
    constructed_dependencies: Mapping[str, set[int]],
) -> set[int]:
    if node is None:
        return set()
    result: set[int] = set()
    for item in ast.walk(node):
        if not isinstance(item, ast.Name):
            continue
        axis = variable_axes.get(item.id)
        if axis is not None:
            result.add(axis)
        result.update(constructed_dependencies.get(item.id, ()))
    return result


def _attach(
    anchors: list[list[float]], axes: Iterable[int], values: Iterable[float]
) -> int:
    usable = [
        float(value)
        for value in values
        if math.isfinite(float(value)) and float(value) > 0.0
    ]
    count = 0
    for axis in set(axes):
        anchors[axis].extend(usable)
        count += len(usable)
    return count


def _robust_soft_scale(values: Sequence[float], fallback: float) -> float:
    usable = [float(value) for value in values if math.isfinite(value) and value > 0.0]
    if not usable:
        return fallback
    # A unit reference prevents one isolated extreme literal from determining
    # the scale.  It is a scale prior only; it creates no search envelope.
    logarithms = np.asarray([0.0, *(math.log(value) for value in usable)], dtype=float)
    candidate = math.exp(float(np.median(logarithms)))
    return candidate if math.isfinite(candidate) and candidate > 0.0 else fallback


def derive_literal_scale_plan(document: Mapping[str, object]) -> LiteralScalePlan:
    """Derive anonymous per-axis soft scales without modifying ``document``."""

    variables = document.get("variables")
    raw_names = variables.get("names") if isinstance(variables, Mapping) else None
    if not isinstance(raw_names, list):
        raise ProposalContractError("variables.names is missing")
    names = tuple(str(name) for name in raw_names)
    if len(set(names)) != len(names) or any(not name for name in names):
        raise ProposalContractError("variable names must be unique nonempty strings")
    variable_axes = {name: axis for axis, name in enumerate(names)}
    constructed_dependencies: dict[str, set[int]] = {}
    anchors: list[list[float]] = [[] for _ in names]
    parsed = 0
    attached = 0

    construction = document.get("construction")
    for item in construction if isinstance(construction, list) else ():
        if not isinstance(item, Mapping):
            continue
        node = _parse_expression(item.get("expr"))
        if node is None:
            continue
        parsed += 1
        axes = _dependencies(node, variable_axes, constructed_dependencies)
        attached += _attach(anchors, axes, _maximal_constant_magnitudes(node))
        symbol = item.get("name")
        if isinstance(symbol, str) and symbol:
            constructed_dependencies[symbol] = set(axes)

    constraints = document.get("constraints")
    for item in constraints if isinstance(constraints, list) else ():
        if not isinstance(item, Mapping):
            continue
        definition = _parse_expression(item.get("def"))
        value = _parse_expression(item.get("value"))
        if definition is not None or value is not None:
            parsed += 1
        axes = _dependencies(
            definition, variable_axes, constructed_dependencies
        ) | _dependencies(value, variable_axes, constructed_dependencies)
        literals = _maximal_constant_magnitudes(
            definition
        ) + _maximal_constant_magnitudes(value)
        attached += _attach(anchors, axes, literals)

    guards = document.get("guards")
    for raw_guard in guards if isinstance(guards, list) else ():
        node = _parse_expression(raw_guard)
        if node is None:
            continue
        parsed += 1
        attached += _attach(
            anchors,
            _dependencies(node, variable_axes, constructed_dependencies),
            _maximal_constant_magnitudes(node),
        )

    answer = _parse_expression(document.get("answer"))
    if answer is not None:
        parsed += 1
        attached += _attach(
            anchors,
            _dependencies(answer, variable_axes, constructed_dependencies),
            _maximal_constant_magnitudes(answer),
        )

    raw_bounds = document.get("bounds")
    if isinstance(raw_bounds, list) and len(raw_bounds) == len(names):
        for axis, pair in enumerate(raw_bounds):
            if not isinstance(pair, list) or len(pair) != 2:
                continue
            values: list[float] = []
            for endpoint in pair:
                values.extend(_maximal_constant_magnitudes(_parse_expression(endpoint)))
            attached += _attach(anchors, (axis,), values)

    all_anchors = [value for axis_anchors in anchors for value in axis_anchors]
    global_fallback = _robust_soft_scale(all_anchors, 1.0)
    scales = np.asarray(
        [_robust_soft_scale(axis_anchors, global_fallback) for axis_anchors in anchors],
        dtype=float,
    )
    return LiteralScalePlan(
        variable_names=names,
        scales=scales,
        direct_anchor_counts=tuple(len(values) for values in anchors),
        activation={
            "schema_version": SCHEMA,
            "dimension": len(names),
            "parsed_dsl_expressions": parsed,
            "literal_anchor_attachments": attached,
            "axes_with_direct_literal_anchors": sum(bool(values) for values in anchors),
            "unit_fallback_only_when_literal_evidence_missing": True,
            "literal_scales_are_soft_proposal_scales": True,
            "literal_scales_are_hard_bounds": False,
        },
    )


def _literal_source_bounds(
    document: Mapping[str, object], dimension: int
) -> tuple[np.ndarray, np.ndarray]:
    raw = document.get("bounds")
    if raw is None:
        return np.full(dimension, -math.inf), np.full(dimension, math.inf)
    if not isinstance(raw, list) or len(raw) != dimension:
        raise ProposalContractError("source bounds do not match variables.names")
    try:
        lower = np.asarray([float(pair[0]) for pair in raw], dtype=float)
        upper = np.asarray([float(pair[1]) for pair in raw], dtype=float)
    except (IndexError, TypeError, ValueError) as error:
        raise ProposalContractError("source bounds are malformed") from error
    if (
        np.any(~np.isfinite(lower))
        or np.any(~np.isfinite(upper))
        or np.any(lower >= upper)
    ):
        raise ProposalContractError("source bounds must be finite and ordered")
    return lower, upper


def _counter_seed(seed: int, lane: str) -> int:
    payload = struct.pack("<q", int(seed)) + _LANE_TAGS[lane]
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "little")


def _open_unit(value: float) -> float:
    return min(max(float(value), _OPEN_LOW), _OPEN_HIGH)


def _positive_chart(unit: float, chart: str) -> float:
    if chart == CAUCHY:
        return math.tan(0.5 * math.pi * unit)
    if chart == LOG_SYMMETRIC:
        return -math.log1p(-unit)
    if chart == ASINH_RATIONAL:
        return unit / math.sqrt((1.0 - unit) * (1.0 + unit))
    raise ProposalContractError(f"unknown literal-scale chart: {chart}")


def _two_sided_chart(unit: float, chart: str) -> float:
    if chart == CAUCHY:
        return math.tan(math.pi * (unit - 0.5))
    if chart == LOG_SYMMETRIC:
        return math.log(unit) - math.log1p(-unit)
    if chart == ASINH_RATIONAL:
        signed = 2.0 * unit - 1.0
        return signed / math.sqrt((1.0 - abs(signed)) * (1.0 + abs(signed)))
    raise ProposalContractError(f"unknown literal-scale chart: {chart}")


def _map_axis(
    unit: float, lower: float, upper: float, *, scale: float, chart: str
) -> float:
    unit = _open_unit(unit)
    if math.isfinite(lower) and math.isfinite(upper):
        return (1.0 - unit) * lower + unit * upper
    positive = _positive_chart(unit, chart)
    if math.isfinite(lower):
        return lower + scale * positive
    if math.isfinite(upper):
        return upper - scale * positive
    return scale * _two_sided_chart(unit, chart)


def _prefix_digest(points: Sequence[np.ndarray]) -> str:
    digest = hashlib.sha256(b"geotarget.exp-real61-008.literal-scale-prefix-f8/v1\0")
    digest.update(struct.pack("<Q", len(points)))
    for point in points:
        values = np.asarray(point, dtype="<f8")
        digest.update(struct.pack("<Q", values.size))
        digest.update(values.tobytes(order="C"))
    return digest.hexdigest()


def _inside_source_domain(
    point: np.ndarray, lower: np.ndarray, upper: np.ndarray
) -> bool:
    return bool(
        point.shape == lower.shape
        and np.all(np.isfinite(point))
        and np.all(point >= lower)
        and np.all(point <= upper)
    )


def build_literal_scale_prefix(
    document: Mapping[str, object],
    source_lower: Sequence[float],
    source_upper: Sequence[float],
    base_points: Sequence[np.ndarray],
    base_sources: Sequence[str],
    *,
    seed: int,
) -> LiteralScalePrefix:
    """Replace only non-insurance starts of an EXP008 source-only prefix."""

    plan = derive_literal_scale_plan(document)
    dimension = len(plan.variable_names)
    lower = np.asarray(source_lower, dtype=float).copy()
    upper = np.asarray(source_upper, dtype=float).copy()
    if lower.shape != (dimension,) or upper.shape != (dimension,):
        raise ProposalContractError("source endpoint shape mismatch")
    if np.any(np.isnan(lower)) or np.any(np.isnan(upper)) or np.any(lower >= upper):
        raise ProposalContractError("source endpoints are malformed")
    literal_lower, literal_upper = _literal_source_bounds(document, dimension)
    if not np.array_equal(lower, literal_lower) or not np.array_equal(upper, literal_upper):
        raise ProposalContractError("caller endpoints differ from literal source bounds")

    base = tuple(np.asarray(point, dtype=float).copy() for point in base_points)
    labels = tuple(str(source) for source in base_sources)
    if not base or len(base) != len(labels):
        raise ProposalContractError("base source-only prefix is empty or misaligned")
    if any(not _inside_source_domain(point, lower, upper) for point in base):
        raise ProposalContractError("base prefix violates the source domain")
    for ordinal in range(0, len(base), INSURANCE_PERIOD):
        if labels[ordinal] != INSURANCE_SOURCE:
            raise ProposalContractError("every fourth base point must be counter-Cauchy")

    noninsurance_count = len(base) - (len(base) + INSURANCE_PERIOD - 1) // INSURANCE_PERIOD
    draws_per_arm = max(1, (noninsurance_count + len(ARMS) - 1) // len(ARMS))
    power = max(0, (draws_per_arm - 1).bit_length())
    units: dict[str, np.ndarray] = {}
    for arm in ARMS:
        if dimension == 0:
            units[arm] = np.empty((max(1, draws_per_arm), 0), dtype=float)
            continue
        sampler = qmc.Sobol(
            dimension,
            scramble=True,
            seed=_counter_seed(seed, arm) & 0xFFFFFFFF,
        )
        sample = sampler.random_base2(power) if draws_per_arm > 1 else sampler.random(1)
        units[arm] = np.asarray(sample, dtype=float)

    emitted: list[np.ndarray] = []
    sources: list[str] = []
    exponents: list[int | None] = []
    pulls = {arm: 0 for arm in ARMS}
    fallbacks = 0
    noninsurance_ordinal = 0
    for ordinal, raw_point in enumerate(base):
        if ordinal % INSURANCE_PERIOD == 0:
            emitted.append(raw_point.copy())
            sources.append(INSURANCE_SOURCE)
            exponents.append(None)
            continue
        arm = ARMS[noninsurance_ordinal % len(ARMS)]
        noninsurance_ordinal += 1
        pull = pulls[arm]
        pulls[arm] += 1
        exponent = DYADIC_EXPONENTS[pull % len(DYADIC_EXPONENTS)]
        try:
            point = np.empty(dimension, dtype=float)
            for axis in range(dimension):
                scale = math.ldexp(float(plan.scales[axis]), exponent)
                if not math.isfinite(scale) or scale <= 0.0:
                    raise FloatingPointError("literal proposal scale is not finite")
                point[axis] = _map_axis(
                    float(units[arm][pull, axis]),
                    float(lower[axis]),
                    float(upper[axis]),
                    scale=scale,
                    chart=arm,
                )
            if not _inside_source_domain(point, lower, upper):
                raise FloatingPointError("full-support chart emitted an invalid point")
            source = arm
        except (FloatingPointError, OverflowError, ValueError):
            point = raw_point.copy()
            source = FALLBACK
            fallbacks += 1
        emitted.append(point)
        sources.append(source)
        exponents.append(exponent)

    for ordinal in range(0, len(base), INSURANCE_PERIOD):
        if emitted[ordinal].tobytes() != base[ordinal].tobytes():
            raise AssertionError("counter-Cauchy insurance point changed")
    for length in range(1, len(emitted) + 1):
        insurance = sum(source == INSURANCE_SOURCE for source in sources[:length])
        if INSURANCE_PERIOD * insurance < length:
            raise AssertionError("counter-Cauchy prefix insurance fell below 25%")

    points = tuple(point.copy() for point in emitted)
    activation = {
        "schema_version": SCHEMA,
        "configuration": "static_three_chart_literal_scale_mixture",
        "source_trace": list(sources),
        "pulls": pulls,
        "fallbacks": fallbacks,
        "iid_insurance_bitwise_unchanged": sum(
            ordinal % INSURANCE_PERIOD == 0 for ordinal in range(len(base))
        ),
        "iid_insurance_prefix_floor": True,
        "all_configured_charts_full_support": True,
        "source_problem_modified": False,
        "hard_bounds_added_or_narrowed": False,
        "finite_search_envelope": False,
        "unbounded_coordinate_clipping": False,
        "gauge_or_symmetry_reduction": False,
        "variables_or_equations_removed": False,
        "problem_identity_or_truth_available": False,
        "original_evaluator_is_authoritative": True,
        "scale_plan": dict(plan.activation),
    }
    return LiteralScalePrefix(
        points=points,
        sources=tuple(sources),
        scale_exponents=tuple(exponents),
        literal_scales=plan.scales.copy(),
        sha256=_prefix_digest(points),
        activation=activation,
    )


def configuration_manifest() -> Mapping[str, object]:
    return {
        "schema_version": SCHEMA,
        "algorithm": "static source-literal-scale full-support chart mixture",
        "insurance_period": INSURANCE_PERIOD,
        "insurance_source": INSURANCE_SOURCE,
        "noninsurance_arms": list(ARMS),
        "dyadic_exponents": list(DYADIC_EXPONENTS),
        "chart_support": {
            CAUCHY: "complete source domain",
            LOG_SYMMETRIC: "complete source domain",
            ASINH_RATIONAL: "complete source domain",
        },
        "source_literals_used_only_as_soft_scales": True,
        "source_problem_modified": False,
        "hard_bounds_added_or_narrowed": False,
        "finite_search_envelope": False,
        "unbounded_coordinate_clipping": False,
        "gauge_or_symmetry_reduction": False,
        "variables_or_equations_removed": False,
        "problem_identity_or_truth_available": False,
        "original_evaluator_is_authoritative": True,
        "real_compute_admitted": False,
    }


def configuration_digest() -> str:
    payload = json.dumps(
        configuration_manifest(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "ARMS",
    "ASINH_RATIONAL",
    "CAUCHY",
    "FALLBACK",
    "INSURANCE_SOURCE",
    "LOG_SYMMETRIC",
    "LiteralScalePlan",
    "LiteralScalePrefix",
    "ProposalContractError",
    "build_literal_scale_prefix",
    "configuration_digest",
    "configuration_manifest",
    "derive_literal_scale_plan",
]
