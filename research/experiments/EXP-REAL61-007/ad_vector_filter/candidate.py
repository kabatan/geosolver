"""Parity-checked forward-AD vector filter/restoration trust region.

This disposable local candidate operates on the untouched source system.  It
keeps every equality row and every source guard/bound margin as an independent
component.  A two-coordinate filter compares raw equality norm against the
sum of negative margins.  Infeasible iterates use a restoration step; feasible
iterates use a minimum-norm root step with fraction-to-the-boundary protection.

The forward-AD interpreter is the already parity-qualified EXP-REAL61-006
implementation.  Each AD equality/guard row is accepted only after value
parity with an observation made by the original evaluator.  Unsupported rows
fall back to charged one-sided finite differences.  Only bounds literally
present in the source are hard bounds.  There is no gauge fixing, variable or
equation elimination, case routing, truth input, or target-count input.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
import importlib.util
import math
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np
from scipy import linalg


HERE = Path(__file__).resolve().parent
ANALYTIC_SOURCE = (
    HERE.parents[1] / "EXP-REAL61-006" / "analytic_jacobian" / "candidate.py"
)
LEGACY_SOURCE = Path("/home/kabatan/work/geosolver/src")
if str(LEGACY_SOURCE) not in sys.path:
    sys.path.insert(0, str(LEGACY_SOURCE))


def _load_analytic_module():
    name = "geotarget_exp007_ad_vector_filter_forward_ad"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, ANALYTIC_SOURCE)
    if specification is None or specification.loader is None:
        raise ImportError(ANALYTIC_SOURCE)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


AD = _load_analytic_module()
Dual = AD.Dual
UnsupportedExpression = AD.UnsupportedExpression


CANDIDATE = "ad_vector_filter_cpqr_svd"


@dataclass(frozen=True)
class Configuration:
    name: str = CANDIDATE
    fd_relative_step: float = 2.0e-7
    initial_trust_radius: float = 1.0
    minimum_trust_radius: float = 1.0e-9
    maximum_trust_radius: float = 64.0
    maximum_iterations: int = 48
    rank_rtol: float = 3.0e-10
    equality_goal_inf: float = 1.0e-8
    margin_tolerance: float = 1.0e-12
    active_margin_band: float = 1.0e-5
    filter_gamma: float = 1.0e-4
    sufficient_decrease: float = 1.0e-4
    parity_rtol: float = 2.0e-8
    parity_atol: float = 2.0e-10


CONFIGURATION = Configuration()
CONFIGURATIONS = {CANDIDATE: CONFIGURATION}


@dataclass(frozen=True)
class CandidateOutcome:
    endpoint: np.ndarray
    status: str
    counters: Mapping[str, int]


@dataclass(frozen=True)
class GuardComponent:
    source_ordinal: int
    guard: object
    side: str


@dataclass(frozen=True)
class HardComponent:
    kind: str
    symbols: tuple[str, ...]


@dataclass(frozen=True)
class MarginProgram:
    ad_program: object
    guard_components: tuple[GuardComponent, ...]
    lower: np.ndarray
    upper: np.ndarray
    hard_components: tuple[HardComponent, ...]

    @property
    def dimension(self) -> int:
        return int(self.ad_program.dimension)

    @property
    def residual_dimension(self) -> int:
        return int(self.ad_program.residual_dimension)

    @property
    def margin_dimension(self) -> int:
        source_bounds = int(np.count_nonzero(np.isfinite(self.lower))) + int(
            np.count_nonzero(np.isfinite(self.upper))
        )
        # The final row is an opaque, fail-closed semantic fallback.  It does
        # not replace any guard/bound/branch row.
        return len(self.guard_components) + source_bounds + len(self.hard_components) + 1


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _name(node: ast.AST) -> str | None:
    return node.id if isinstance(node, ast.Name) else None


def _hard_components(document: Mapping[str, object]) -> tuple[HardComponent, ...]:
    """Mirror the original structural hard-check compiler, without routing."""

    rows: list[HardComponent] = []
    for raw in document.get("construction") or ():
        if not isinstance(raw, Mapping) or not isinstance(raw.get("expr"), str):
            continue
        try:
            parsed = ast.parse(str(raw["expr"]), mode="eval").body
        except SyntaxError:
            continue
        if not isinstance(parsed, ast.Call):
            continue
        function = _call_name(parsed.func)
        arguments = tuple(_name(value) for value in parsed.args)
        if function in {"Line", "LineThrough"} and len(arguments) >= 2 and all(
            arguments[:2]
        ):
            rows.append(HardComponent("line_distinct", tuple(arguments[:2])))
        elif function in {"Circumcircle", "TriangleCenter", "Incircle", "Incenter"} and len(
            arguments
        ) >= 3 and all(arguments[:3]):
            rows.append(HardComponent("triangle_nondegenerate", tuple(arguments[:3])))
        elif function == "Intersect":
            symbol = str(raw.get("name", ""))
            keywords = {item.arg: _name(item.value) for item in parsed.keywords}
            exclude = keywords.get("exclude")
            if symbol and exclude:
                rows.append(HardComponent("intersection_exclude", (symbol, exclude)))
            if symbol and keywords.get("near"):
                rows.append(HardComponent("branch_near", (symbol, str(keywords["near"]))))
            if symbol and keywords.get("far"):
                rows.append(HardComponent("branch_far", (symbol, str(keywords["far"]))))
    return tuple(rows)


def compile_program(document: Mapping[str, object]) -> MarginProgram:
    ad_program = AD.compile_program(document)
    components: list[GuardComponent] = []
    for ordinal, guard in enumerate(ad_program.guards):
        if str(getattr(guard, "kind", "")) in {"bound", "bound_open"}:
            if getattr(guard, "lower_expr", None) is not None:
                components.append(GuardComponent(ordinal, guard, "lower"))
            if getattr(guard, "upper_expr", None) is not None:
                components.append(GuardComponent(ordinal, guard, "upper"))
            if not components or components[-1].source_ordinal != ordinal:
                components.append(GuardComponent(ordinal, guard, "whole"))
        else:
            components.append(GuardComponent(ordinal, guard, "whole"))
    raw_bounds = document.get("bounds")
    if raw_bounds is None:
        lower = np.full(ad_program.dimension, -math.inf)
        upper = np.full(ad_program.dimension, math.inf)
    else:
        if not isinstance(raw_bounds, list) or len(raw_bounds) != ad_program.dimension:
            raise ValueError("source bounds do not match source variables")
        lower = np.asarray([float(pair[0]) for pair in raw_bounds], dtype=float)
        upper = np.asarray([float(pair[1]) for pair in raw_bounds], dtype=float)
        if np.any(np.isnan(lower)) or np.any(np.isnan(upper)) or np.any(lower >= upper):
            raise ValueError("source bounds are malformed")
    lower.flags.writeable = False
    upper.flags.writeable = False
    return MarginProgram(
        ad_program,
        tuple(components),
        lower,
        upper,
        _hard_components(document),
    )


def _dual_constant(value: float, dimension: int) -> Dual:
    return Dual(float(value), np.zeros(dimension))


def _signed_guard_whole(
    guard: object,
    context: Mapping[str, object],
    dimension: int,
    tolerance: float,
) -> Dual:
    kind = str(getattr(guard, "kind", ""))
    if kind == "compare":
        left = AD._dual(AD._eval_source(getattr(guard, "lhs_expr"), context), dimension)
        right = AD._dual(AD._eval_source(getattr(guard, "rhs_expr"), context), dimension)
        operator = str(getattr(guard, "operator", ""))
        if operator in {">", ">="}:
            return left - right - (tolerance if operator == ">" else -tolerance)
        if operator in {"<", "<="}:
            return right - left - (tolerance if operator == "<" else -tolerance)
        if operator == "==":
            return tolerance - abs(left - right)
        if operator == "!=":
            return abs(left - right) - tolerance
        raise UnsupportedExpression("unknown compare guard")
    if kind == "residual":
        value = AD._dual(
            AD._eval_source(getattr(guard, "residual_expr"), context), dimension
        )
        return tolerance - abs(value)
    if kind == "logical_and":
        children = tuple(getattr(guard, "children", ()))
        if not children:
            return _dual_constant(1.0, dimension)
        return AD.ad_min(
            *(_signed_guard_whole(child, context, dimension, tolerance) for child in children)
        )
    if kind == "logical_or":
        children = tuple(getattr(guard, "children", ()))
        if not children:
            return _dual_constant(-1.0, dimension)
        return AD.ad_max(
            *(_signed_guard_whole(child, context, dimension, tolerance) for child in children)
        )
    if kind == "logical_not":
        children = tuple(getattr(guard, "children", ()))
        if len(children) != 1:
            raise UnsupportedExpression("malformed logical not")
        return -_signed_guard_whole(children[0], context, dimension, tolerance)
    raise UnsupportedExpression("guard is not analytically mirrored")


def _signed_guard_component(
    component: GuardComponent,
    context: Mapping[str, object],
    dimension: int,
    tolerance: float,
) -> Dual:
    guard = component.guard
    kind = str(getattr(guard, "kind", ""))
    if kind not in {"bound", "bound_open"}:
        return _signed_guard_whole(guard, context, dimension, tolerance)
    value = AD._dual(AD._eval_source(getattr(guard, "lhs_expr"), context), dimension)
    offset = tolerance if kind == "bound_open" else -tolerance
    if component.side == "lower":
        lower = AD._dual(
            AD._eval_source(getattr(guard, "lower_expr"), context), dimension
        )
        return value - lower - offset
    if component.side == "upper":
        upper = AD._dual(
            AD._eval_source(getattr(guard, "upper_expr"), context), dimension
        )
        return upper - value - offset
    raise UnsupportedExpression("bound guard has no side")


def _hard_row(
    component: HardComponent,
    context: Mapping[str, object],
    dimension: int,
) -> Dual | None:
    try:
        values = tuple(context[name] for name in component.symbols)
        if component.kind == "line_distinct":
            first, second = values
            scale = AD.ad_max(
                1.0, abs(first.x), abs(first.y), abs(second.x), abs(second.y)
            )
            return AD.Distance(first, second) / scale - 1.0e-12
        if component.kind == "triangle_nondegenerate":
            first, second, third = values
            scale = AD.ad_max(
                1.0,
                abs(first.x), abs(first.y),
                abs(second.x), abs(second.y),
                abs(third.x), abs(third.y),
            )
            twice_area = abs((second - first).cross(third - first))
            return twice_area / (scale * scale) - 1.0e-14
        if component.kind == "intersection_exclude":
            first, second = values
            scale = AD.ad_max(
                1.0, abs(first.x), abs(first.y), abs(second.x), abs(second.y)
            )
            return AD.Distance(first, second) / scale - 1.0e-12
        # Selector traces have no differentiable numeric margin in the float
        # evaluator.  They retain a distinct fail-closed row and therefore use
        # charged FD below rather than inventing a branch expression.
        return None
    except Exception:
        return None


def _parity(left: float, right: float, configuration: Configuration) -> bool:
    return bool(
        math.isfinite(left)
        and math.isfinite(right)
        and abs(left - right)
        <= configuration.parity_atol
        + configuration.parity_rtol * max(1.0, abs(right))
    )


@dataclass
class _State:
    x: np.ndarray
    equality: np.ndarray
    margins: np.ndarray
    equality_jacobian_x: np.ndarray
    margin_jacobian_x: np.ndarray
    semantics_valid: bool

    @property
    def phi(self) -> float:
        if not np.all(np.isfinite(self.equality)):
            return math.inf
        return float(np.linalg.norm(self.equality))

    @property
    def equality_inf(self) -> float:
        if not np.all(np.isfinite(self.equality)):
            return math.inf
        return float(np.linalg.norm(self.equality, ord=np.inf))

    @property
    def theta(self) -> float:
        if not np.all(np.isfinite(self.margins)):
            return math.inf
        return float(np.sum(np.maximum(0.0, -self.margins)))


def _make_state(
    case: object,
    program: MarginProgram,
    point: np.ndarray,
    configuration: Configuration,
    counters: dict[str, int],
) -> _State:
    x = np.asarray(point, dtype=float)
    observation = case.evaluate(x)
    equality = np.asarray(observation.residual, dtype=float)
    if (
        equality.shape != (program.residual_dimension,)
        or not observation.finite
        or not np.all(np.isfinite(equality))
    ):
        equality = np.asarray(case.progressive_residual(x), dtype=float)
        counters["progressive_equality_calls"] += 1
    if equality.shape != (program.residual_dimension,) or not np.all(np.isfinite(equality)):
        equality = np.full(program.residual_dimension, 1.0e3)

    eq_jac = np.full((program.residual_dimension, program.dimension), np.nan)
    margin_values: list[float] = []
    margin_jacobians: list[np.ndarray] = []
    try:
        context = program.ad_program._context(x)
    except Exception:
        context = None

    relation_rows = program.ad_program.relation_rows(x)
    for index, row in enumerate(relation_rows):
        if row is not None and _parity(row.value, equality[index], configuration) and np.all(
            np.isfinite(row.derivative)
        ):
            eq_jac[index] = row.derivative
            counters["analytic_equality_rows"] += 1
        else:
            counters["equality_fd_fallback_rows"] += 1

    raw_violation = np.asarray(observation.violation_vector, dtype=float).reshape(-1)
    source_guard_count = len(program.ad_program.guards)
    opaque_guards = np.zeros(source_guard_count)
    copied = min(source_guard_count, raw_violation.size)
    if copied:
        opaque_guards[:copied] = np.where(
            np.isfinite(raw_violation[:copied]),
            np.maximum(0.0, raw_violation[:copied]),
            1.0,
        )
    by_source: dict[int, list[tuple[int, Dual | None]]] = {}
    for component in program.guard_components:
        row = None
        if context is not None:
            try:
                row = _signed_guard_component(
                    component, context, program.dimension, configuration.margin_tolerance
                )
            except Exception:
                row = None
        position = len(margin_values)
        margin_values.append(
            float(row.value)
            if row is not None and math.isfinite(row.value)
            else -float(opaque_guards[component.source_ordinal])
        )
        margin_jacobians.append(
            np.asarray(row.derivative, dtype=float)
            if row is not None and np.all(np.isfinite(row.derivative))
            else np.full(program.dimension, np.nan)
        )
        by_source.setdefault(component.source_ordinal, []).append((position, row))

    # A top-level guard's opaque violation is the parity authority.  Bound
    # sides remain separate, while their negative parts sum back to that
    # original top-level violation.
    for ordinal, rows in by_source.items():
        expected = sum(max(0.0, -float(row.value)) for _index, row in rows if row is not None)
        all_supported = all(row is not None for _index, row in rows)
        if all_supported and _parity(expected, float(opaque_guards[ordinal]), configuration):
            counters["analytic_guard_margin_rows"] += len(rows)
        else:
            for index, _row in rows:
                margin_jacobians[index][:] = np.nan
                margin_values[index] = -float(opaque_guards[ordinal])
            counters["guard_margin_parity_fallback_rows"] += len(rows)

    # Literal source bounds are independent signed components and are also the
    # only bounds used for clipping.
    for axis in range(program.dimension):
        derivative = np.zeros(program.dimension)
        derivative[axis] = 1.0
        if math.isfinite(float(program.lower[axis])):
            margin_values.append(float(x[axis] - program.lower[axis]))
            margin_jacobians.append(derivative.copy())
            counters["source_bound_margin_rows"] += 1
        if math.isfinite(float(program.upper[axis])):
            margin_values.append(float(program.upper[axis] - x[axis]))
            margin_jacobians.append(-derivative.copy())
            counters["source_bound_margin_rows"] += 1

    # Structural hard rows are kept separately.  Their AD formulas mirror the
    # original structural compiler.  Group sign consistency with the original
    # hard-feasibility decision is required before their derivatives are used.
    hard_positions: list[int] = []
    hard_rows: list[Dual | None] = []
    for component in program.hard_components:
        row = _hard_row(component, context, program.dimension) if context is not None else None
        hard_positions.append(len(margin_values))
        hard_rows.append(row)
        margin_values.append(float(row.value) if row is not None else -1.0)
        margin_jacobians.append(
            np.asarray(row.derivative, dtype=float)
            if row is not None and np.all(np.isfinite(row.derivative))
            else np.full(program.dimension, np.nan)
        )
    guard_ok = not np.any(opaque_guards > configuration.margin_tolerance)
    structural_ok = all(row is not None and row.value >= 0.0 for row in hard_rows)
    hard_ok_observed = bool(observation.semantics_valid or not guard_ok)
    hard_group_parity = bool(not program.hard_components or structural_ok == hard_ok_observed)
    if hard_group_parity:
        counters["analytic_hard_margin_rows"] += sum(row is not None for row in hard_rows)
    else:
        for position in hard_positions:
            margin_jacobians[position][:] = np.nan
        counters["hard_margin_parity_fallback_rows"] += len(hard_positions)

    # Independent fail-closed row for undefined/unrepresented semantic state.
    hard_raw = float(raw_violation[-1]) if raw_violation.size > source_guard_count else 0.0
    semantic_fallback = 1.0 if observation.semantics_valid else -max(1.0, hard_raw)
    margin_values.append(semantic_fallback)
    margin_jacobians.append(
        np.zeros(program.dimension)
        if observation.semantics_valid
        else np.full(program.dimension, np.nan)
    )
    counters["semantic_fallback_rows"] += 1

    margins = np.asarray(margin_values, dtype=float)
    margin_jac = np.vstack(margin_jacobians) if margin_jacobians else np.empty((0, program.dimension))
    if margins.size != program.margin_dimension:
        raise RuntimeError("margin program shape mismatch")
    return _State(x.copy(), equality, margins, eq_jac, margin_jac, bool(observation.finite and observation.semantics_valid))


def _fill_fd_rows(
    case: object,
    program: MarginProgram,
    current: _State,
    origin: np.ndarray,
    scales: np.ndarray,
    lower_z: np.ndarray,
    upper_z: np.ndarray,
    configuration: Configuration,
    counters: dict[str, int],
) -> tuple[np.ndarray, np.ndarray]:
    equality_jac = current.equality_jacobian_x * scales
    margin_jac = current.margin_jacobian_x * scales
    unsupported_eq = np.flatnonzero(~np.all(np.isfinite(equality_jac), axis=1))
    unsupported_margin = np.flatnonzero(~np.all(np.isfinite(margin_jac), axis=1))
    if unsupported_eq.size == 0 and unsupported_margin.size == 0:
        return equality_jac, margin_jac
    z = (current.x - origin) / scales
    for column in range(program.dimension):
        step = configuration.fd_relative_step * max(1.0, abs(float(z[column])))
        trial_value = min(float(upper_z[column]), float(z[column] + step))
        if trial_value == z[column]:
            trial_value = max(float(lower_z[column]), float(z[column] - step))
        delta = trial_value - z[column]
        if delta == 0.0:
            continue
        trial_z = z.copy()
        trial_z[column] = trial_value
        trial = _make_state(
            case,
            program,
            origin + scales * trial_z,
            configuration,
            counters,
        )
        if unsupported_eq.size:
            equality_jac[unsupported_eq, column] = (
                trial.equality[unsupported_eq] - current.equality[unsupported_eq]
            ) / delta
        if unsupported_margin.size:
            margin_jac[unsupported_margin, column] = (
                trial.margins[unsupported_margin] - current.margins[unsupported_margin]
            ) / delta
        counters["fd_direction_evaluations"] += 1
    equality_jac[~np.isfinite(equality_jac)] = 0.0
    margin_jac[~np.isfinite(margin_jac)] = 0.0
    return equality_jac, margin_jac


def _minimum_norm_step(
    matrix: np.ndarray,
    rhs: np.ndarray,
    rank_rtol: float,
    counters: dict[str, int],
) -> np.ndarray:
    columns = matrix.shape[1]
    if not matrix.size or columns == 0 or not np.all(np.isfinite(matrix)):
        return np.zeros(columns)
    try:
        step, _residuals, rank, _singular = linalg.lstsq(
            matrix, rhs, cond=rank_rtol, lapack_driver="gelsy", check_finite=False
        )
        counters["cpqr_steps"] += 1
        if int(rank) < min(matrix.shape):
            counters["rank_deficient_steps"] += 1
            raise linalg.LinAlgError("rank-deficient CPQR; use filtered SVD")
        if np.all(np.isfinite(step)):
            return np.asarray(step, dtype=float)
    except Exception:
        pass
    try:
        u, singular, vh = linalg.svd(matrix, full_matrices=False, check_finite=False)
        if singular.size == 0:
            return np.zeros(columns)
        cutoff = rank_rtol * max(1.0, float(singular[0]))
        inverse = np.zeros_like(singular)
        np.divide(1.0, singular, out=inverse, where=singular > cutoff)
        counters["svd_steps"] += 1
        counters["rank_deficient_steps"] += int(np.count_nonzero(singular > cutoff) < min(matrix.shape))
        return (vh.T * inverse) @ (u.T @ rhs)
    except Exception:
        counters["linear_failures"] += 1
        return np.zeros(columns)


def _filter_acceptable(
    phi: float,
    theta: float,
    entries: Sequence[tuple[float, float]],
    gamma: float,
) -> bool:
    return all(
        phi <= (1.0 - gamma) * old_phi
        or theta <= max(0.0, (1.0 - gamma) * old_theta)
        for old_phi, old_theta in entries
    )


def _insert_filter(entries: list[tuple[float, float]], pair: tuple[float, float]) -> None:
    phi, theta = pair
    entries[:] = [
        (old_phi, old_theta)
        for old_phi, old_theta in entries
        if not (phi <= old_phi and theta <= old_theta)
    ]
    entries.append(pair)
    if len(entries) > 32:
        entries[:] = entries[-32:]


def _better(left: _State, right: _State) -> bool:
    return (
        not left.semantics_valid,
        left.theta,
        left.equality_inf,
        left.phi,
    ) < (
        not right.semantics_valid,
        right.theta,
        right.equality_inf,
        right.phi,
    )


def solve_local(
    case: object,
    program: MarginProgram,
    configuration: Configuration,
    start: Sequence[float],
    *,
    max_callbacks: int,
    deadline_monotonic: float,
) -> CandidateOutcome:
    if program.dimension != int(case.dimension) or program.residual_dimension != int(
        case.residual_dimension
    ):
        raise ValueError("program and original evaluator shapes differ")
    start = np.asarray(start, dtype=float)
    if start.shape != (program.dimension,) or not np.all(np.isfinite(start)):
        raise ValueError("start has wrong shape or is nonfinite")
    if max_callbacks < 2:
        raise ValueError("max_callbacks must be at least two")
    counters = {
        "starts_attempted": 1,
        "iterations": 0,
        "restoration_steps": 0,
        "restoration_tangential_equality_rows": 0,
        "root_steps": 0,
        "accepted_steps": 0,
        "rejected_steps": 0,
        "filter_rejections": 0,
        "analytic_equality_rows": 0,
        "equality_fd_fallback_rows": 0,
        "analytic_guard_margin_rows": 0,
        "guard_margin_parity_fallback_rows": 0,
        "source_bound_margin_rows": 0,
        "analytic_hard_margin_rows": 0,
        "hard_margin_parity_fallback_rows": 0,
        "semantic_fallback_rows": 0,
        "progressive_equality_calls": 0,
        "fd_direction_evaluations": 0,
        "cpqr_steps": 0,
        "svd_steps": 0,
        "rank_deficient_steps": 0,
        "linear_failures": 0,
        "fraction_to_boundary_steps": 0,
        "semantic_entries": 0,
        "reported_safe_endpoint": 0,
        "budget_stops": 0,
        "deadline_stops": 0,
    }
    origin = np.asarray(case.origin, dtype=float)
    scales = np.asarray(case.scales, dtype=float)
    if (
        origin.shape != start.shape
        or scales.shape != start.shape
        or not np.all(np.isfinite(origin))
        or not np.all(np.isfinite(scales))
        or np.any(scales <= 0.0)
    ):
        raise ValueError("invalid working coordinate metadata")
    # Only literal source bounds from the byte-bound source are hard.
    lower = np.asarray(program.lower, dtype=float)
    upper = np.asarray(program.upper, dtype=float)
    lower_z = (lower - origin) / scales
    upper_z = (upper - origin) / scales
    x0 = np.minimum(np.maximum(start, lower), upper)
    try:
        current = _make_state(case, program, x0, configuration, counters)
    except Exception as error:
        if error.__class__.__name__ == "BudgetExceeded":
            counters["budget_stops"] += 1
            return CandidateOutcome(x0.copy(), "budget_before_start", counters)
        raise
    best = current
    radius = configuration.initial_trust_radius
    filter_entries: list[tuple[float, float]] = [(current.phi, current.theta)]
    previous_semantics = current.semantics_valid
    stagnation = 0

    for _ in range(configuration.maximum_iterations):
        if time.monotonic() >= deadline_monotonic:
            counters["deadline_stops"] += 1
            break
        if current.semantics_valid and current.equality_inf <= configuration.equality_goal_inf:
            counters["reported_safe_endpoint"] = 1
            return CandidateOutcome(current.x.copy(), "safe_root", counters)
        counters["iterations"] += 1
        try:
            equality_jac, margin_jac = _fill_fd_rows(
                case,
                program,
                current,
                origin,
                scales,
                lower_z,
                upper_z,
                configuration,
                counters,
            )
        except Exception as error:
            if error.__class__.__name__ == "BudgetExceeded":
                counters["budget_stops"] += 1
                break
            counters["linear_failures"] += 1
            break

        infeasible = current.theta > configuration.margin_tolerance or not current.semantics_valid
        if infeasible:
            active = np.flatnonzero(current.margins < configuration.active_margin_band)
            if active.size == 0:
                active = np.arange(current.margins.size)
            vector = np.minimum(current.margins[active], 0.0)
            # A restoration step is normal to the individual violated-margin
            # rows, with a scale-balanced tangential equality block.  The
            # equality block is essential on geometry systems where entering
            # a guard domain and approaching the construction equations must
            # happen together; its weight is derived from the two filter
            # coordinates, not from a case or family constant.
            equality_weight = min(
                1.0,
                max(current.theta, configuration.margin_tolerance)
                / max(current.phi, configuration.margin_tolerance),
            )
            matrix = np.vstack((margin_jac[active], equality_weight * equality_jac))
            rhs = np.concatenate((-vector, -equality_weight * current.equality))
            counters["restoration_steps"] += 1
            counters["restoration_tangential_equality_rows"] += int(equality_jac.shape[0])
        else:
            matrix = equality_jac
            rhs = -current.equality
            counters["root_steps"] += 1
        step = _minimum_norm_step(matrix, rhs, configuration.rank_rtol, counters)
        norm = float(np.linalg.norm(step))
        if not math.isfinite(norm) or norm == 0.0:
            radius *= 0.25
            stagnation += 1
            if radius < configuration.minimum_trust_radius or stagnation >= 5:
                break
            continue
        if norm > radius:
            step *= radius / norm
            norm = radius

        if not infeasible:
            directional = margin_jac @ step
            threatened = np.flatnonzero(
                (directional < 0.0) & (current.margins + directional < 0.0)
            )
            if threatened.size:
                fractions = 0.9 * current.margins[threatened] / -directional[threatened]
                alpha = max(0.0, min(1.0, float(np.min(fractions))))
                step *= alpha
                norm *= alpha
                counters["fraction_to_boundary_steps"] += 1

        current_z = (current.x - origin) / scales
        accepted = False
        for fraction in (1.0, 0.5, 0.25):
            trial_z = np.minimum(
                np.maximum(current_z + fraction * step, lower_z), upper_z
            )
            trial_x = origin + scales * trial_z
            try:
                trial = _make_state(case, program, trial_x, configuration, counters)
            except Exception as error:
                if error.__class__.__name__ == "BudgetExceeded":
                    counters["budget_stops"] += 1
                    break
                continue
            if _better(trial, best):
                best = trial
            filter_ok = _filter_acceptable(
                trial.phi,
                trial.theta,
                filter_entries,
                configuration.filter_gamma,
            )
            feasibility_progress = trial.theta <= max(
                configuration.margin_tolerance,
                (1.0 - configuration.sufficient_decrease) * current.theta,
            )
            root_progress = (
                trial.theta <= max(configuration.margin_tolerance, 1.05 * current.theta)
                and trial.phi
                <= (1.0 - configuration.sufficient_decrease) * current.phi
            )
            semantic_entry = trial.semantics_valid and not current.semantics_valid
            if filter_ok and (feasibility_progress or root_progress or semantic_entry):
                current = trial
                _insert_filter(filter_entries, (trial.phi, trial.theta))
                counters["accepted_steps"] += 1
                counters["semantic_entries"] += int(semantic_entry)
                previous_semantics = trial.semantics_valid
                accepted = True
                stagnation = 0
                radius = min(configuration.maximum_trust_radius, max(radius, 1.8 * fraction * norm))
                break
            counters["filter_rejections"] += int(not filter_ok)
        if not accepted:
            counters["rejected_steps"] += 1
            stagnation += 1
            radius *= 0.3
            if radius < configuration.minimum_trust_radius or stagnation >= 8:
                break

    if best.semantics_valid and best.equality_inf <= configuration.equality_goal_inf:
        counters["reported_safe_endpoint"] = 1
        status = "safe_root"
    elif time.monotonic() >= deadline_monotonic:
        status = "deadline"
    elif counters["budget_stops"]:
        status = "budget"
    else:
        status = "stalled"
    return CandidateOutcome(best.x.copy(), status, counters)


__all__ = [
    "CANDIDATE",
    "CONFIGURATION",
    "CONFIGURATIONS",
    "CandidateOutcome",
    "Configuration",
    "MarginProgram",
    "compile_program",
    "solve_local",
]
