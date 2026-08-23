"""mpmath-based staged local refiner (compatibility/debugging only)."""

from __future__ import annotations

import ast
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from mpmath import mp

from geosolver._internal.autosolve.compile.infer_bounds import infer_bound_expansion_locks
from geosolver._internal.autosolve.execution.interpreter_hp_helpers import to_mpf_value
from geosolver._internal.autosolve.execution.interpreter_modes import (
    _build_solution_context_high_precision,
)
from geosolver._internal.pipeline.contracts.candidate_record import (
    FloatCandidate,
    RefinedCandidate,
    RefinementBatchResult,
)
from geosolver._internal.pipeline.contracts.evaluator_port import EvaluatorPort
from geosolver._internal.pipeline.contracts.local_refiner_port import LocalRefinerPort
from geosolver._internal.pipeline.contracts.problem_bundle import ProblemBundle
from geosolver._internal.pipeline.evaluator.classify_evaluation_failure import EvaluationStatus
from geosolver._internal.pipeline.problem.infer_problem_bounds import infer_problem_bounds
from geosolver._internal.solver.precision.type_guards.boundary_float_to_mpf import (
    BoundaryOrigin,
    boundary_float_to_mpf,
)
from geosolver._internal.solver.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat
from geosolver.ir.compiler import safe_eval_expr_hp

from .finite_difference_jacobian import compute_finite_difference_jacobian
from .levenberg_marquardt_step import compute_levenberg_marquardt_step
from .line_search import _point_within_bounds, run_line_search
from .refiner_config import RefinerConfig

NON_FINITE_INITIAL = "non_finite_initial"
BRANCH_INSTABILITY = "branch_instability"
LINE_SEARCH_FAILED = "line_search_failed"
STALLED = "stalled"
TARGET_REACHED = "target_reached"
MAX_ITERS = "max_iters"
INTEGER_CLOSURE_PHASE = "integer_closure"
_BINARY_ARITY = 2
_RANK_AWARE_MAX_STEPS = 64


class _ClosureDeadlineExceeded(RuntimeError):
    """Internal control signal for an optional closure that used its budget."""


def _vector_norm(values: list[MPFloat]) -> MPFloat:
    return mp.sqrt(mp.fsum(value * value for value in values))


@dataclass(frozen=True)
class IntegerConstraintSpec:
    """Top-level zero-target ``IsInteger`` constraint metadata."""

    constraint_index: int
    inner_expression: str


@dataclass(frozen=True)
class IntegerConstraintClosure:
    """Linearized target for one top-level ``IsInteger`` constraint."""

    constraint_index: int
    inner_expression: str
    target_integer: MPFloat


@dataclass(frozen=True)
class ProjectedIntegerObservation:
    """Projected non-integer-manifold sample with integer observations."""

    point: tuple[MPFloat, ...]
    integer_values: tuple[MPFloat, ...]


def _closure_start_threshold(config: RefinerConfig, dps: int) -> MPFloat:
    return max(
        mp.mpf(config.stage_tolerance),
        mp.mpf(config.promotion_threshold_for_dps(dps)),
    )


def _evaluate_hard_feasibility(
    evaluator: EvaluatorPort,
    point: list[MPFloat],
    precision: int,
    *,
    include_margins: bool = True,
) -> object:
    with high_precision_mode():
        return evaluator.evaluate_hp_hard_feasibility(
            point,
            precision=int(precision),
            include_margins=bool(include_margins),
        )


def _is_zero_target(target: object) -> bool:
    """Return whether the target is numerically zero."""

    if isinstance(target, str):
        return target.strip() == "0"
    try:
        return mp.mpf(target) == mp.mpf("0")
    except Exception:
        return False


def _extract_isinteger_inner_expression(constraint_expression: str) -> str | None:
    """Extract the inner expression from an ``IsInteger(inner)`` constraint."""

    try:
        parsed = ast.parse(constraint_expression, mode="eval")
    except SyntaxError:
        return None
    call = parsed.body
    if not isinstance(call, ast.Call):
        return None
    if call.keywords or len(call.args) != 1:
        return None
    if not isinstance(call.func, ast.Name) or call.func.id != "IsInteger":
        return None
    return ast.unparse(call.args[0])


def _integer_closure_candidate_id(base_candidate_id: int) -> int:
    """Derive a stable negative id for closure-derived candidates."""

    return -abs(int(base_candidate_id)) - 1


def _integer_target_tuple_candidate_id(
    base_candidate_id: int,
    target_integers: tuple[MPFloat, ...],
) -> int:
    """Derive a stable negative id for one explicit integer-target tuple."""

    encoded = abs(int(base_candidate_id)) + 1
    for target in target_integers:
        integer_value = int(mp.nint(target))
        sign_bit = 1 if integer_value < 0 else 0
        magnitude = abs(integer_value)
        encoded = encoded * 1_000_003 + magnitude * 2 + sign_bit
    return -encoded


def _build_hp_context(
    *,
    bundle: ProblemBundle,
    point: list[MPFloat],
    dps: int,
) -> dict[str, object]:
    """Build the high-precision evaluation context for one point."""

    return _build_solution_context_high_precision(
        bundle.spec,
        list(bundle.var_names),
        list(point),
        dict(bundle.base_context),
        int(dps),
    )


def build_integer_constraint_specs(
    *,
    bundle: ProblemBundle,
) -> tuple[IntegerConstraintSpec, ...]:
    """Return all top-level zero-target ``IsInteger`` constraints."""

    specs: list[IntegerConstraintSpec] = []
    for index, constraint_expression in enumerate(bundle.spec.constraints):
        if index >= len(bundle.targets) or not _is_zero_target(bundle.targets[index]):
            continue
        inner_expression = _extract_isinteger_inner_expression(constraint_expression)
        if inner_expression is None:
            continue
        specs.append(
            IntegerConstraintSpec(
                constraint_index=index,
                inner_expression=inner_expression,
            )
        )
    return tuple(specs)


def evaluate_integer_constraint_values(
    *,
    bundle: ProblemBundle,
    point: list[MPFloat],
    specs: tuple[IntegerConstraintSpec, ...],
    dps: int,
) -> tuple[MPFloat, ...] | None:
    """Evaluate top-level integer-constraint inner expressions at one point."""

    if not specs:
        return ()
    if len(point) != len(bundle.var_names):
        return None
    try:
        with mp.workdps(int(dps)):
            with high_precision_mode():
                context = _build_hp_context(bundle=bundle, point=point, dps=int(dps))
                values: list[MPFloat] = []
                for spec in specs:
                    raw_value = safe_eval_expr_hp(spec.inner_expression, context)
                    values.append(
                        mp.mpf(
                            to_mpf_value(
                                raw_value,
                                precision=int(dps),
                                context=f"integer_constraint_value:{spec.constraint_index}",
                            )
                        )
                    )
        return tuple(values)
    except Exception:
        return None


def build_integer_constraint_closures_from_targets(
    *,
    specs: tuple[IntegerConstraintSpec, ...],
    target_integers: tuple[MPFloat, ...],
) -> tuple[IntegerConstraintClosure, ...]:
    """Build explicit closure targets for top-level integer constraints."""

    if len(specs) != len(target_integers):
        raise ValueError("integer target count must match integer constraint count")
    closures: list[IntegerConstraintClosure] = []
    for spec, target in zip(specs, target_integers, strict=True):
        closures.append(
            IntegerConstraintClosure(
                constraint_index=spec.constraint_index,
                inner_expression=spec.inner_expression,
                target_integer=mp.mpf(mp.nint(target)),
            )
        )
    return tuple(closures)


def _build_integer_constraint_closures(
    *,
    bundle: ProblemBundle,
    point: list[MPFloat],
    dps: int,
) -> tuple[IntegerConstraintClosure, ...]:
    """Build nearest-integer closure targets for top-level IsInteger constraints."""

    specs = build_integer_constraint_specs(bundle=bundle)
    values = evaluate_integer_constraint_values(
        bundle=bundle,
        point=point,
        specs=specs,
        dps=int(dps),
    )
    if values is None:
        return ()
    return build_integer_constraint_closures_from_targets(
        specs=specs,
        target_integers=values,
    )


def _evaluate_integer_closure_residuals(
    *,
    bundle: ProblemBundle,
    point: list[MPFloat],
    closures: tuple[IntegerConstraintClosure, ...],
    dps: int,
) -> dict[int, MPFloat] | None:
    """Evaluate linearized residuals for IsInteger closures."""

    if not closures:
        return {}
    try:
        with mp.workdps(int(dps)):
            with high_precision_mode():
                context = _build_hp_context(bundle=bundle, point=point, dps=int(dps))
                overrides: dict[int, MPFloat] = {}
                for closure in closures:
                    raw_value = safe_eval_expr_hp(closure.inner_expression, context)
                    inner_value = mp.mpf(
                        to_mpf_value(
                            raw_value,
                            precision=int(dps),
                            context=f"integer_closure_residual:{closure.constraint_index}",
                        )
                    )
                    overrides[closure.constraint_index] = inner_value - closure.target_integer
        return overrides
    except Exception:
        return None


def _residual_vector_without_integer_constraints(
    bundle: ProblemBundle,
    evaluator: EvaluatorPort,
    point: list[MPFloat],
    dps: int,
    *,
    integer_constraint_indices: tuple[int, ...],
) -> list[MPFloat] | None:
    """Evaluate residuals with top-level integer constraints removed."""

    with mp.workdps(int(dps)):
        with high_precision_mode():
            hp_eval = evaluator.evaluate_hp_residual(point, precision=int(dps))
    if hp_eval.evaluation_status is not EvaluationStatus.OK:
        return None
    skipped = set(int(index) for index in integer_constraint_indices)
    residuals = [
        mp.mpf(value)
        for index, value in enumerate(hp_eval.residual_vector)
        if index not in skipped
    ]
    if not residuals:
        return None
    return residuals


def _smooth_zero_constraint_residuals(
    *,
    bundle: ProblemBundle,
    point: list[MPFloat],
    dps: int,
    residuals: list[MPFloat],
) -> list[MPFloat]:
    """Replace selected nonsmooth zero tests by equivalent smooth residuals.

    ``Distance(P, Q)`` and the public ``IsTangent`` predicate are both
    nonnegative (they contain an absolute value or a Euclidean norm).  Their
    zero sets are correct, but their derivative is zero/undefined at the
    solution, which makes finite-difference LM and Newton closure stop at a
    merely close point.  During local high-precision refinement only, use
    equivalent equations:

    * point--point distance zero -> ``(dx, dy)``;
    * line--circle tangency -> signed squared distance minus ``r**2``.

    The original evaluator remains the certification source; this helper only
    changes the residuals supplied to an optimization step.  Constraints that
    do not match these exact top-level forms are returned unchanged.
    """
    plans: dict[int, tuple[str, tuple[str, str]]] = {}
    for index, constraint_expression in enumerate(bundle.spec.constraints):
        if index >= len(residuals) or index >= len(bundle.targets):
            continue
        if not _is_zero_target(bundle.targets[index]):
            continue
        try:
            node = ast.parse(constraint_expression, mode="eval").body
        except (SyntaxError, TypeError, ValueError):
            continue
        if not isinstance(node, ast.Call) or node.keywords or len(node.args) != _BINARY_ARITY:
            continue
        if not isinstance(node.func, ast.Name):
            continue
        kind = node.func.id.lower()
        if kind not in {"distance", "istangent"}:
            continue
        plans[index] = (kind, (ast.unparse(node.args[0]), ast.unparse(node.args[1])))
    if not plans:
        return residuals

    try:
        with mp.workdps(int(dps)):
            with high_precision_mode():
                context = _build_hp_context(bundle=bundle, point=point, dps=int(dps))
                rewritten: list[MPFloat] = []
                for index, residual in enumerate(residuals):
                    plan = plans.get(index)
                    if plan is None:
                        rewritten.append(mp.mpf(residual))
                        continue
                    kind, (left_expr, right_expr) = plan
                    left = safe_eval_expr_hp(left_expr, context)
                    right = safe_eval_expr_hp(right_expr, context)
                    if kind == "distance":
                        if all(hasattr(value, "x") and hasattr(value, "y") for value in (left, right)):
                            rewritten.extend(
                                [
                                    mp.mpf(left.x) - mp.mpf(right.x),
                                    mp.mpf(left.y) - mp.mpf(right.y),
                                ]
                            )
                            continue
                    else:
                        line = circle = None
                        if (
                            hasattr(left, "a")
                            and hasattr(left, "b")
                            and hasattr(left, "c")
                            and hasattr(right, "center")
                            and hasattr(right, "radius")
                        ):
                            line, circle = left, right
                        elif (
                            hasattr(right, "a")
                            and hasattr(right, "b")
                            and hasattr(right, "c")
                            and hasattr(left, "center")
                            and hasattr(left, "radius")
                        ):
                            line, circle = right, left
                        if line is not None and circle is not None:
                            signed_distance = (
                                mp.mpf(line.a) * mp.mpf(circle.center.x)
                                + mp.mpf(line.b) * mp.mpf(circle.center.y)
                                + mp.mpf(line.c)
                            )
                            rewritten.append(
                                signed_distance * signed_distance
                                - mp.mpf(circle.radius) * mp.mpf(circle.radius)
                            )
                            continue
                    rewritten.append(mp.mpf(residual))
                return rewritten
    except Exception:
        # This is an optimization aid, never a second failure path for the
        # evaluator.  Keep the source residuals if a construction is not a
        # supported point/line/circle object.
        return residuals


def _normalize_findroot_point(root: object) -> list[MPFloat] | None:
    if isinstance(root, mp.matrix):
        values = [mp.mpf(root[index]) for index in range(len(root))]
        return values
    if isinstance(root, (list, tuple)):
        return [mp.mpf(value) for value in root]
    try:
        return [mp.mpf(root)]
    except (TypeError, ValueError):
        return None


def _select_rank_revealing_subsystem(
    jacobian: list[list[MPFloat]],
    *,
    dps: int,
) -> tuple[tuple[int, ...], tuple[int, ...]] | None:
    """Select a numerically independent square Jacobian submatrix.

    A geometric residual system often contains gauge freedoms (for example a
    global rotation) or redundant equations.  Requiring the full Jacobian to
    be square and nonsingular therefore rejects otherwise refinable points.
    Complete-pivot Gaussian elimination identifies a local coordinate chart:
    the returned rows are independent source residuals and the returned
    columns are variables that can solve those residuals while the remaining
    gauge coordinates stay fixed.

    The threshold is deliberately conservative relative to the centered
    finite-difference step used by ``compute_finite_difference_jacobian``.  A
    doubtful direction is treated as a gauge direction; the original full
    residual vector is still checked after closure, so this selection cannot
    relax certification.
    """

    if not jacobian or not jacobian[0]:
        return None
    row_count = len(jacobian)
    column_count = len(jacobian[0])
    if any(len(row) != column_count for row in jacobian):
        return None

    with mp.workdps(int(dps)):
        matrix = [[mp.mpf(value) for value in row] for row in jacobian]
        if any(not mp.isfinite(value) for row in matrix for value in row):
            return None
        scale = max(abs(value) for row in matrix for value in row)
        if scale == 0:
            return None

        # Centered differences use a step no smaller than roughly 1e-30 in
        # this refiner.  Keeping 25 relative digits separates the real small
        # pivots seen in geometry problems from differencing noise without
        # pretending that the numerical Jacobian is exact.
        relative_tolerance = mp.power(10, -min(25, max(12, int(dps) // 3)))
        pivot_tolerance = scale * relative_tolerance
        row_order = list(range(row_count))
        column_order = list(range(column_count))
        rank = 0

        for pivot_index in range(min(row_count, column_count)):
            pivot_row = pivot_index
            pivot_column = pivot_index
            pivot_abs = mp.mpf("0")
            for row in range(pivot_index, row_count):
                for column in range(pivot_index, column_count):
                    candidate_abs = abs(matrix[row][column])
                    if candidate_abs > pivot_abs:
                        pivot_abs = candidate_abs
                        pivot_row = row
                        pivot_column = column
            if pivot_abs <= pivot_tolerance:
                break

            if pivot_row != pivot_index:
                matrix[pivot_index], matrix[pivot_row] = matrix[pivot_row], matrix[pivot_index]
                row_order[pivot_index], row_order[pivot_row] = (
                    row_order[pivot_row],
                    row_order[pivot_index],
                )
            if pivot_column != pivot_index:
                for row in matrix:
                    row[pivot_index], row[pivot_column] = row[pivot_column], row[pivot_index]
                column_order[pivot_index], column_order[pivot_column] = (
                    column_order[pivot_column],
                    column_order[pivot_index],
                )

            pivot = matrix[pivot_index][pivot_index]
            for row in range(pivot_index + 1, row_count):
                factor = matrix[row][pivot_index] / pivot
                matrix[row][pivot_index] = mp.mpf("0")
                for column in range(pivot_index + 1, column_count):
                    matrix[row][column] -= factor * matrix[pivot_index][column]
            rank += 1

    if rank == 0:
        return None
    return tuple(row_order[:rank]), tuple(column_order[:rank])


def _run_rank_aware_findroot(
    *,
    evaluate_residuals: Callable[[list[MPFloat]], tuple[MPFloat, ...]],
    start_point: list[MPFloat],
    dps: int,
    target_residual: MPFloat,
    max_steps: int,
) -> list[MPFloat] | None:
    """Refine on a local full-rank chart of a residual manifold.

    Variables outside the selected Jacobian columns are held at their current
    values only for this Newton solve.  This removes coordinate/gauge
    singularities without adding a condition to the problem itself.
    """

    def jacobian_residual_fn(point: list[MPFloat], _dps: int) -> list[MPFloat] | None:
        try:
            return list(evaluate_residuals(point))
        except _ClosureDeadlineExceeded:
            raise
        except Exception:
            return None

    jacobian = compute_finite_difference_jacobian(
        point=start_point,
        dps=int(dps),
        residual_fn=jacobian_residual_fn,
    )
    if jacobian is None:
        return None
    subsystem = _select_rank_revealing_subsystem(jacobian, dps=int(dps))
    if subsystem is None:
        return None
    residual_indices, variable_indices = subsystem
    fixed_point = [mp.mpf(value) for value in start_point]

    def assemble_point(active_values: tuple[MPFloat, ...]) -> list[MPFloat]:
        point = [mp.mpf(value) for value in fixed_point]
        for variable_index, value in zip(variable_indices, active_values, strict=True):
            point[variable_index] = mp.mpf(value)
        return point

    def selected_residuals(*active_values: MPFloat) -> tuple[MPFloat, ...]:
        residuals = evaluate_residuals(assemble_point(tuple(active_values)))
        return tuple(residuals[index] for index in residual_indices)

    active_start = tuple(fixed_point[index] for index in variable_indices)
    try:
        with mp.workdps(int(dps)):
            if len(active_start) == 1:
                def scalar_residual(value: MPFloat) -> MPFloat:
                    return selected_residuals(mp.mpf(value))[0]

                root = mp.findroot(
                    scalar_residual,
                    active_start[0],
                    solver="secant",
                    tol=mp.mpf(target_residual),
                    maxsteps=min(int(max_steps), _RANK_AWARE_MAX_STEPS),
                )
            else:
                root = mp.findroot(
                    selected_residuals,
                    active_start,
                    solver="mnewton",
                    tol=mp.mpf(target_residual),
                    maxsteps=min(int(max_steps), _RANK_AWARE_MAX_STEPS),
                )
            normalized_active = _normalize_findroot_point(root)
    except (TypeError, ValueError, ZeroDivisionError, IndexError, _ClosureDeadlineExceeded):
        return None
    if normalized_active is None or len(normalized_active) != len(variable_indices):
        return None
    return assemble_point(tuple(normalized_active))


def _convert_problem_bounds(
    bundle: ProblemBundle,
) -> tuple[tuple[MPFloat | None, MPFloat | None], ...]:
    bounds = infer_problem_bounds(bundle)
    locks = infer_bound_expansion_locks(
        bundle.spec,
        bundle.var_names,
        bundle.base_context,
    )
    return tuple(
        (
            (
                boundary_float_to_mpf(lower, origin=BoundaryOrigin.LEGACY_BOUND)
                if lower_locked
                else None
            ),
            (
                boundary_float_to_mpf(upper, origin=BoundaryOrigin.LEGACY_BOUND)
                if upper_locked
                else None
            ),
        )
        for (lower, upper), (lower_locked, upper_locked) in zip(bounds, locks, strict=True)
    )


def _run_findroot_closure(
    *,
    evaluator: EvaluatorPort,
    start_point: list[MPFloat],
    bounds: tuple[tuple[MPFloat | None, MPFloat | None], ...],
    dps: int,
    target_residual: MPFloat,
    max_steps: int,
    residual_fn: Callable[[list[MPFloat], int], list[MPFloat] | None] | None = None,
    deadline_monotonic: float | None = None,
) -> tuple[list[MPFloat], MPFloat] | None:
    if len(start_point) == 0:
        return None

    def evaluate_residuals(point: list[MPFloat]) -> tuple[MPFloat, ...]:
        if deadline_monotonic is not None and time.monotonic() >= float(deadline_monotonic):
            raise _ClosureDeadlineExceeded
        if residual_fn is not None:
            with mp.workdps(int(dps)):
                with high_precision_mode():
                    values = residual_fn(point, int(dps))
            if values is None:
                raise ValueError("closure residual evaluation failed")
            return tuple(mp.mpf(value) for value in values)
        with mp.workdps(int(dps)):
            with high_precision_mode():
                hp_eval = evaluator.evaluate_hp_residual(point, precision=int(dps))
        if hp_eval.evaluation_status is not EvaluationStatus.OK:
            raise ValueError(f"findroot residual status={hp_eval.evaluation_status.value}")
        return tuple(mp.mpf(value) for value in hp_eval.residual_vector)

    def certify(point: list[MPFloat] | None) -> tuple[list[MPFloat], MPFloat] | None:
        if deadline_monotonic is not None and time.monotonic() >= float(deadline_monotonic):
            return None
        if point is None or len(point) != len(start_point):
            return None
        if not _point_within_bounds(point, bounds):
            return None
        with mp.workdps(int(dps)):
            with high_precision_mode():
                hp_eval = evaluator.evaluate_hp_residual(point, precision=int(dps))
        if hp_eval.evaluation_status is not EvaluationStatus.OK:
            return None
        residual_norm = _vector_norm([mp.mpf(value) for value in hp_eval.residual_vector])
        # ``mp.findroot`` can stop because its step became small even when the
        # residual is still far above the requested tolerance.  A rank-aware
        # chart changes only the Newton coordinates, never this certification
        # over every original source residual.
        if not mp.isfinite(residual_norm) or residual_norm > mp.mpf(target_residual):
            return None
        return point, residual_norm

    try:
        initial_residuals = evaluate_residuals([mp.mpf(value) for value in start_point])
    except (TypeError, ValueError, ZeroDivisionError, IndexError, _ClosureDeadlineExceeded):
        return None
    standard_point: list[MPFloat] | None = None

    if len(start_point) == 1:
        def evaluate_scalar_residuals(arg: MPFloat) -> tuple[MPFloat, ...]:
            return evaluate_residuals([mp.mpf(arg)])

        def scalar_residual(arg: MPFloat) -> MPFloat:
            residuals = evaluate_scalar_residuals(arg)
            if len(residuals) != 1:
                raise ValueError("scalar secant closure requires exactly one residual")
            return residuals[0]

        def overdetermined_scalar_residual(arg: MPFloat) -> tuple[MPFloat, ...]:
            return evaluate_scalar_residuals(arg)

        try:
            with mp.workdps(int(dps)):
                if len(initial_residuals) == 1:
                    root = mp.findroot(
                        scalar_residual,
                        mp.mpf(start_point[0]),
                        solver="secant",
                        tol=mp.mpf(target_residual),
                        maxsteps=int(max_steps),
                    )
                else:
                    # A one-variable problem may still have several fixed
                    # constraints.  Using residual_vector[0] here silently
                    # selected a constant constraint and made closure a no-op
                    # (or falsely accepted the unchanged point).  mpmath's
                    # multidimensional Newton path supports this overdetermined
                    # scalar case and lets the variable-dependent residual
                    # determine the root.
                    root = mp.findroot(
                        overdetermined_scalar_residual,
                        mp.mpf(start_point[0]),
                        solver="mnewton",
                        tol=mp.mpf(target_residual),
                        maxsteps=int(max_steps),
                    )
        except (TypeError, ValueError, ZeroDivisionError, IndexError, _ClosureDeadlineExceeded):
            root = None
        if root is not None:
            with mp.workdps(int(dps)):
                standard_point = _normalize_findroot_point(root)
    elif len(initial_residuals) >= len(start_point):
        def residuals(*args: MPFloat) -> tuple[MPFloat, ...]:
            point = [mp.mpf(value) for value in args]
            return evaluate_residuals(point)

        try:
            with mp.workdps(int(dps)):
                root = mp.findroot(
                    residuals,
                    tuple(start_point),
                    solver="mnewton",
                    tol=mp.mpf(target_residual),
                    maxsteps=int(max_steps),
                )
        except (TypeError, ValueError, ZeroDivisionError, IndexError, _ClosureDeadlineExceeded):
            root = None
        if root is not None:
            with mp.workdps(int(dps)):
                standard_point = _normalize_findroot_point(root)

    certified = certify(standard_point)
    if certified is not None:
        return certified

    # Underdetermined systems and square systems with a singular Jacobian are
    # closed on a local rank-revealing chart.  This is also a safe fallback
    # when full-system findroot returned a point that failed certification.
    try:
        rank_aware_point = _run_rank_aware_findroot(
            evaluate_residuals=evaluate_residuals,
            start_point=[mp.mpf(value) for value in start_point],
            dps=int(dps),
            target_residual=mp.mpf(target_residual),
            max_steps=int(max_steps),
        )
    except _ClosureDeadlineExceeded:
        return None
    return certify(rank_aware_point)


@dataclass(frozen=True)
class MpmathRefiner(LocalRefinerPort):
    """Compatibility/debug-only local refiner using staged LM at high precision."""

    config: RefinerConfig = RefinerConfig()

    def refine_candidates(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        candidates: tuple[FloatCandidate, ...],
        deadline_monotonic: float | None = None,
    ) -> RefinementBatchResult:
        bounds = _convert_problem_bounds(bundle)
        refined_list: list[RefinedCandidate] = []
        attempted_count = 0
        for candidate in candidates:
            if deadline_monotonic is not None and time.monotonic() >= float(deadline_monotonic):
                break
            attempted_count += 1
            refined_list.extend(
                self._refine_single_candidate(
                    bundle=bundle,
                    evaluator=evaluator,
                    candidate=candidate,
                    bounds=bounds,
                    deadline_monotonic=deadline_monotonic,
                )
            )
        refined = tuple(refined_list)
        ordered = tuple(sorted(refined, key=lambda candidate: candidate.residual_norm_hp))
        converged_count = sum(
            1 for candidate in ordered if candidate.refinement_status == TARGET_REACHED
        )
        return RefinementBatchResult(
            candidates=ordered,
            converged_count=converged_count,
            attempted_count=attempted_count,
            solver_name="mpmath_refiner",
            hard_feasible_count=sum(1 for candidate in ordered if candidate.hard_feasible),
            attempted_box_count=0,
        )

    def refine_candidate_with_integer_targets(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        candidate: FloatCandidate,
        target_integers: tuple[MPFloat, ...],
        start_point: tuple[MPFloat, ...] | None = None,
    ) -> RefinedCandidate | None:
        """Run the explicit integer-closure path for one audited target tuple."""

        specs = build_integer_constraint_specs(bundle=bundle)
        if not specs or len(specs) != len(target_integers):
            return None
        bounds = _convert_problem_bounds(bundle)
        if start_point is None:
            current = [
                boundary_float_to_mpf(value, origin=BoundaryOrigin.INITIAL_POINT)
                for value in candidate.x_float
            ]
        else:
            current = [mp.mpf(value) for value in start_point]
        closures = build_integer_constraint_closures_from_targets(
            specs=specs,
            target_integers=target_integers,
        )
        closure_status, closure_point, closure_answer_dps, closure_history = self._run_integer_closure_path(
            bundle=bundle,
            evaluator=evaluator,
            start_point=current,
            bounds=bounds,
            preserve_hard_feasibility=bool(candidate.hard_feasible),
            integer_closures=closures,
        )
        closure_point, closure_history, closure_status, closure_answer_dps = self._apply_post_lm_closure_polish(
            bundle=bundle,
            evaluator=evaluator,
            bounds=bounds,
            point=closure_point,
            phase_history=closure_history,
            stage_status=closure_status,
            answer_dps=closure_answer_dps,
        )
        return self._build_refined_candidate(
            bundle=bundle,
            candidate=candidate,
            evaluator=evaluator,
            point=closure_point,
            phase_history=closure_history,
            stage_status=closure_status,
            candidate_id=_integer_target_tuple_candidate_id(
                int(candidate.candidate_id),
                tuple(mp.mpf(target) for target in target_integers),
            ),
            answer_dps=closure_answer_dps,
        )

    def project_point_to_noninteger_constraint_manifold(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        start_point: tuple[MPFloat, ...],
        dps: int,
    ) -> ProjectedIntegerObservation | None:
        """Project a deterministic sample toward the non-integer manifold."""

        specs = build_integer_constraint_specs(bundle=bundle)
        if not specs:
            return None
        integer_constraint_indices = tuple(
            int(spec.constraint_index)
            for spec in specs
        )
        residual_fn = partial(
            _residual_vector_without_integer_constraints,
            bundle,
            evaluator,
            integer_constraint_indices=integer_constraint_indices,
        )
        bounds = _convert_problem_bounds(bundle)
        current = [mp.mpf(value) for value in start_point]
        stage_status, projected_point, projected_norm = self._run_stage(
            bundle=bundle,
            evaluator=evaluator,
            start_point=current,
            bounds=bounds,
            dps=int(dps),
            target_residual=mp.mpf(self.config.target_for_dps(int(dps))),
            preserve_hard_feasibility=False,
            residual_fn=residual_fn,
        )
        _ = stage_status
        projection_threshold = _closure_start_threshold(self.config, int(dps))
        if projected_norm > projection_threshold:
            return None
        hard_snapshot = _evaluate_hard_feasibility(
            evaluator,
            projected_point,
            int(dps),
        )
        if not hard_snapshot.hard_feasible:
            return None
        integer_values = evaluate_integer_constraint_values(
            bundle=bundle,
            point=projected_point,
            specs=specs,
            dps=int(dps),
        )
        if integer_values is None or len(integer_values) != len(specs):
            return None
        return ProjectedIntegerObservation(
            point=tuple(projected_point),
            integer_values=tuple(integer_values),
        )

    def _residual_vector_for_stage(
        self,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        point: list[MPFloat],
        dps: int,
        integer_closures: tuple[IntegerConstraintClosure, ...] = (),
        smooth_zero_constraints: bool = False,
    ) -> list[MPFloat] | None:
        with mp.workdps(int(dps)):
            with high_precision_mode():
                hp_eval = evaluator.evaluate_hp_residual(point, precision=int(dps))
        if hp_eval.evaluation_status is not EvaluationStatus.OK:
            return None
        residuals = [mp.mpf(value) for value in hp_eval.residual_vector]
        if not integer_closures:
            if smooth_zero_constraints:
                residuals = _smooth_zero_constraint_residuals(
                    bundle=bundle,
                    point=point,
                    dps=int(dps),
                    residuals=residuals,
                )
            return residuals
        overrides = _evaluate_integer_closure_residuals(
            bundle=bundle,
            point=point,
            closures=integer_closures,
            dps=int(dps),
        )
        if overrides is None:
            return None
        for closure in integer_closures:
            residuals[closure.constraint_index] = mp.mpf(overrides[closure.constraint_index])
        return residuals

    def _evaluate_answer(
        self,
        evaluator: EvaluatorPort,
        point: list[MPFloat],
        dps: int,
    ) -> MPFloat | None:
        with mp.workdps(int(dps)):
            with high_precision_mode():
                answer_eval = evaluator.evaluate_answer_hp(point, precision=int(dps))
        if answer_eval.evaluation_status is not EvaluationStatus.OK:
            return None
        return answer_eval.answer_hp

    def _run_stage(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        start_point: list[MPFloat],
        bounds: tuple[tuple[MPFloat | None, MPFloat | None], ...],
        dps: int,
        target_residual: MPFloat,
        preserve_hard_feasibility: bool,
        integer_closures: tuple[IntegerConstraintClosure, ...] = (),
        residual_fn: Callable[[list[MPFloat], int], list[MPFloat] | None] | None = None,
    ) -> tuple[str, list[MPFloat], MPFloat]:
        if residual_fn is None:
            residual_fn = partial(
                self._residual_vector_for_stage,
                bundle,
                evaluator,
                integer_closures=integer_closures,
                smooth_zero_constraints=True,
            )
        current = [mp.mpf(value) for value in start_point]
        current_vec = residual_fn(current, int(dps))
        if current_vec is None:
            return NON_FINITE_INITIAL, current, mp.inf
        current_norm = _vector_norm(current_vec)
        best = [mp.mpf(value) for value in current]
        best_norm = current_norm
        damping = mp.mpf(self.config.damping_initial)
        damping_min = mp.mpf(self.config.damping_min)
        damping_scale = mp.mpf(self.config.damping_scale)
        stage_tolerance = mp.mpf(self.config.stage_tolerance)
        stalled_count = 0
        line_failures = 0
        status = MAX_ITERS
        trial_filter = None
        if preserve_hard_feasibility:
            def trial_filter(trial: list[MPFloat], trial_dps: int) -> bool:
                return _evaluate_hard_feasibility(
                    evaluator,
                    trial,
                    trial_dps,
                    include_margins=False,
                ).hard_feasible
        for _ in range(int(self.config.max_stage_iters)):
            if best_norm <= target_residual:
                status = TARGET_REACHED
                break
            jacobian = compute_finite_difference_jacobian(
                point=current,
                dps=int(dps),
                residual_fn=residual_fn,
            )
            if jacobian is None:
                status = BRANCH_INSTABILITY
                break
            step = compute_levenberg_marquardt_step(
                jacobian=jacobian,
                residual_vector=current_vec,
                damping=damping,
            )
            trial, trial_vec, improved = run_line_search(
                point=current,
                current_norm=current_norm,
                step=step,
                dps=int(dps),
                max_steps=int(self.config.line_search_max_steps),
                residual_fn=residual_fn,
                bounds=bounds,
                trial_filter=trial_filter,
            )
            if (
                not improved
                and preserve_hard_feasibility
                and integer_closures
            ):
                trial, trial_vec, improved = run_line_search(
                    point=current,
                    current_norm=current_norm,
                    step=step,
                    dps=int(dps),
                    max_steps=int(self.config.line_search_max_steps),
                    residual_fn=residual_fn,
                    bounds=bounds,
                    trial_filter=None,
                )
            if improved and trial_vec is not None:
                trial_norm = _vector_norm(trial_vec)
                improvement = (current_norm - trial_norm) / max(
                    abs(current_norm),
                    mp.mpf("1e-30"),
                )
                current = [mp.mpf(value) for value in trial]
                current_vec = [mp.mpf(value) for value in trial_vec]
                current_norm = trial_norm
                if trial_norm < best_norm:
                    best = [mp.mpf(value) for value in current]
                    best_norm = trial_norm
                damping = max(damping_min, damping / damping_scale)
                line_failures = 0
                if improvement < stage_tolerance:
                    stalled_count += 1
                else:
                    stalled_count = 0
                if stalled_count >= int(self.config.stall_limit):
                    status = STALLED
                    break
            else:
                damping *= damping_scale
                line_failures += 1
                if line_failures >= int(self.config.line_search_failure_limit):
                    status = LINE_SEARCH_FAILED
                    break
        if status == MAX_ITERS and best_norm <= target_residual:
            status = TARGET_REACHED
        return status, best, best_norm

    def _build_refined_candidate(
        self,
        *,
        bundle: ProblemBundle,
        candidate: FloatCandidate,
        evaluator: EvaluatorPort,
        point: list[MPFloat],
        phase_history: tuple[str, ...],
        stage_status: str,
        candidate_id: int,
        answer_dps: int,
    ) -> RefinedCandidate:
        final_vector = self._residual_vector_for_stage(
            bundle=bundle,
            evaluator=evaluator,
            point=point,
            dps=int(answer_dps),
        )
        if final_vector is None:
            final_norm = mp.inf
        else:
            final_norm = _vector_norm(final_vector)
        hard_snapshot = _evaluate_hard_feasibility(
            evaluator,
            point,
            int(answer_dps),
        )
        answer = self._evaluate_answer(
            evaluator=evaluator,
            point=point,
            dps=int(answer_dps),
        )
        return RefinedCandidate(
            x_hp=tuple(point),
            residual_norm_hp=final_norm,
            answer_hp=answer,
            refinement_status=stage_status,
            phase_history=phase_history,
            source=candidate,
            candidate_id=int(candidate_id),
            hard_feasible=hard_snapshot.hard_feasible,
            hard_violation_tags=tuple(hard_snapshot.failure_tags),
            validity_margin_hp=hard_snapshot.min_margin,
        )


    def _direct_accept_candidate(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        candidate: FloatCandidate,
        point: list[MPFloat],
    ) -> RefinedCandidate | None:
        """Accept already-good high precision candidates without finite-difference LM.

        Phase C already defines a residual/hard-feasibility gate for accepted
        answers.  When Phase A has produced a point that passes the same gate at
        high precision, running a full staged finite-difference LM pass only
        burns time and can even destabilize near singular but already acceptable
        isolated candidates.  This shortcut is intentionally problem-agnostic:
        it depends only on the residual norm and hard feasibility, not on a case
        id or benchmark-specific failure mode.
        """
        raw_threshold = self.config.direct_accept_residual
        if raw_threshold is None:
            return None
        try:
            threshold = mp.mpf(raw_threshold)
        except Exception:
            return None
        if threshold <= mp.mpf("0"):
            return None
        scheduled_dps = max((int(stage) for stage in self.config.schedule_dps), default=120)
        direct_dps = max(int(self.config.direct_accept_dps), scheduled_dps)
        final_vector = self._residual_vector_for_stage(
            bundle=bundle,
            evaluator=evaluator,
            point=point,
            dps=direct_dps,
        )
        if final_vector is None:
            return None
        final_norm = _vector_norm(final_vector)
        if not mp.isfinite(final_norm) or final_norm >= threshold:
            return None
        hard_snapshot = _evaluate_hard_feasibility(
            evaluator,
            point,
            direct_dps,
        )
        if not hard_snapshot.hard_feasible:
            return None
        return self._build_refined_candidate(
            bundle=bundle,
            candidate=candidate,
            evaluator=evaluator,
            point=point,
            phase_history=(f"direct:{direct_dps}:{final_norm}",),
            stage_status="direct_evaluation",
            candidate_id=int(candidate.candidate_id),
            answer_dps=direct_dps,
        )

    def _apply_post_lm_closure_polish(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        bounds: tuple[tuple[MPFloat | None, MPFloat | None], ...],
        point: list[MPFloat],
        phase_history: tuple[str, ...],
        stage_status: str,
        answer_dps: int,
        deadline_monotonic: float | None = None,
    ) -> tuple[list[MPFloat], tuple[str, ...], str, int]:
        current = [mp.mpf(value) for value in point]
        history = list(phase_history)
        final_dps = int(max(self.config.schedule_dps))
        final_vector = self._residual_vector_for_stage(
            bundle=bundle,
            evaluator=evaluator,
            point=current,
            dps=final_dps,
        )
        if final_vector is None:
            return current, tuple(history), stage_status, answer_dps
        final_norm = _vector_norm(final_vector)
        hard_snapshot = _evaluate_hard_feasibility(
            evaluator,
            current,
            final_dps,
        )
        closure_threshold = _closure_start_threshold(self.config, final_dps)
        if (
            not hard_snapshot.hard_feasible
            or final_norm > closure_threshold
        ):
            return current, tuple(history), stage_status, answer_dps
        closure_stages = tuple(
            int(stage)
            for stage in self.config.closure_schedule_dps
            if int(stage) >= final_dps
        )
        closure_residual_fn = partial(
            self._residual_vector_for_stage,
            bundle,
            evaluator,
            smooth_zero_constraints=True,
        )
        for closure_dps in closure_stages:
            if deadline_monotonic is not None and time.monotonic() >= float(deadline_monotonic):
                break
            # ``findroot`` may spend dozens of iterations merely propagating
            # additional digits once a geometric branch is close to a root.
            # The staged LM budget is intentionally small, but reusing that
            # budget for closure truncated otherwise-correct high-precision
            # roots (especially at 250--500 dps).  Closure is entered only
            # after the residual is already below the polish threshold, so a
            # precision-scaled cap is safe and does not change the search/LM
            # budget.
            closure_max_steps = max(
                int(self.config.max_stage_iters),
                2 * int(closure_dps),
            )
            closed = _run_findroot_closure(
                evaluator=evaluator,
                start_point=current,
                bounds=bounds,
                dps=closure_dps,
                target_residual=mp.mpf(self.config.target_for_dps(closure_dps)),
                max_steps=closure_max_steps,
                residual_fn=closure_residual_fn,
                deadline_monotonic=deadline_monotonic,
            )
            if closed is None:
                continue
            closed_point, closed_norm = closed
            closed_hard_snapshot = _evaluate_hard_feasibility(
                evaluator,
                closed_point,
                closure_dps,
            )
            if not closed_hard_snapshot.hard_feasible:
                continue
            # A finite-precision evaluation can round both the current and
            # closed residual to exactly zero.  Requiring a *strictly* smaller
            # norm in that situation prevented promotion from 120 to 250+
            # dps, leaving an answer with only the digits available at the
            # first closure stage.  A certified closure at a higher precision
            # is useful even when the displayed residual is tied.
            if closed_norm >= final_norm and closure_dps <= answer_dps:
                continue
            current = closed_point
            final_vector = self._residual_vector_for_stage(
                bundle=bundle,
                evaluator=evaluator,
                point=current,
                dps=closure_dps,
            )
            final_norm = closed_norm
            answer_dps = closure_dps
            stage_status = TARGET_REACHED
            history.append(f"{closure_dps}:findroot:{closed_norm}")
        return current, tuple(history), stage_status, answer_dps

    def _run_integer_closure_path(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        start_point: list[MPFloat],
        bounds: tuple[tuple[MPFloat | None, MPFloat | None], ...],
        preserve_hard_feasibility: bool,
        integer_closures: tuple[IntegerConstraintClosure, ...],
    ) -> tuple[str, list[MPFloat], int, tuple[str, ...]]:
        current = [mp.mpf(value) for value in start_point]
        history: list[str] = []
        target_summary = ",".join(
            f"{closure.constraint_index}:{closure.target_integer}"
            for closure in integer_closures
        )
        history.append(f"{INTEGER_CLOSURE_PHASE}:targets:{target_summary}")
        stage_status = MAX_ITERS
        answer_dps = int(max(self.config.schedule_dps))
        for dps in self.config.schedule_dps:
            target = mp.mpf(self.config.target_for_dps(int(dps)))
            promotion_threshold = mp.mpf(self.config.promotion_threshold_for_dps(int(dps)))
            stage_status, current, stage_norm = self._run_stage(
                bundle=bundle,
                evaluator=evaluator,
                start_point=current,
                bounds=bounds,
                dps=int(dps),
                target_residual=target,
                preserve_hard_feasibility=preserve_hard_feasibility,
                integer_closures=integer_closures,
            )
            answer_dps = int(dps)
            history.append(f"{INTEGER_CLOSURE_PHASE}:{dps}:{stage_status}:{stage_norm}")
            if stage_norm <= target:
                continue
            if stage_norm <= promotion_threshold:
                history.append(f"{INTEGER_CLOSURE_PHASE}:{dps}:promote:{stage_norm}")
                continue
            if stage_status != TARGET_REACHED:
                break
        return stage_status, current, answer_dps, tuple(history)

    def _refine_single_candidate(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        candidate: FloatCandidate,
        bounds: tuple[tuple[MPFloat | None, MPFloat | None], ...],
        deadline_monotonic: float | None = None,
    ) -> tuple[RefinedCandidate, ...]:
        current = [
            boundary_float_to_mpf(value, origin=BoundaryOrigin.INITIAL_POINT)
            for value in candidate.x_float
        ]
        direct_candidate = self._direct_accept_candidate(
            bundle=bundle,
            evaluator=evaluator,
            candidate=candidate,
            point=current,
        )
        if direct_candidate is not None:
            # A low residual at the final evaluation precision is only a
            # numerical acceptance test.  It is not evidence that the
            # double-precision search point is the exact root.  In
            # particular, an ill-conditioned geometry can map a 1e-15
            # constraint residual to a much larger answer error.  The former
            # fast path returned here and therefore skipped every refinement
            # stage and closure polish.  Try the existing high-precision
            # closure first; if it cannot improve the point, fall through to
            # the normal staged LM path below.  The latter is monotone and
            # keeps the original point as its best iterate, so this preserves
            # the old stability behavior while ensuring that direct
            # acceptance never bypasses exactification work.
            polished_point, polished_history, polished_status, polished_answer_dps = (
                self._apply_post_lm_closure_polish(
                    bundle=bundle,
                    evaluator=evaluator,
                    bounds=bounds,
                    point=current,
                    phase_history=direct_candidate.phase_history,
                    stage_status=direct_candidate.refinement_status,
                    answer_dps=max(
                        int(self.config.direct_accept_dps),
                        int(max(self.config.schedule_dps)),
                    ),
                    deadline_monotonic=deadline_monotonic,
                )
            )
            if polished_status == TARGET_REACHED:
                return (
                    self._build_refined_candidate(
                        bundle=bundle,
                        candidate=candidate,
                        evaluator=evaluator,
                        point=polished_point,
                        phase_history=polished_history,
                        stage_status=polished_status,
                        candidate_id=int(candidate.candidate_id),
                        answer_dps=polished_answer_dps,
                    ),
                )
        history: list[str] = []
        stage_status = MAX_ITERS
        for dps in self.config.schedule_dps:
            target = mp.mpf(self.config.target_for_dps(int(dps)))
            promotion_threshold = mp.mpf(self.config.promotion_threshold_for_dps(int(dps)))
            stage_status, current, stage_norm = self._run_stage(
                bundle=bundle,
                evaluator=evaluator,
                start_point=current,
                bounds=bounds,
                dps=int(dps),
                target_residual=target,
                preserve_hard_feasibility=bool(candidate.hard_feasible),
            )
            history.append(f"{dps}:{stage_status}:{stage_norm}")
            if stage_norm <= target:
                continue
            if stage_norm <= promotion_threshold:
                history.append(f"{dps}:promote:{stage_norm}")
                continue
            if stage_status != TARGET_REACHED:
                break
        final_dps = int(max(self.config.schedule_dps))
        answer_dps = final_dps
        current, phase_history, stage_status, answer_dps = self._apply_post_lm_closure_polish(
            bundle=bundle,
            evaluator=evaluator,
            bounds=bounds,
            point=current,
            phase_history=tuple(history),
            stage_status=stage_status,
            answer_dps=answer_dps,
            deadline_monotonic=deadline_monotonic,
        )
        primary_candidate = self._build_refined_candidate(
            bundle=bundle,
            candidate=candidate,
            evaluator=evaluator,
            point=current,
            phase_history=phase_history,
            stage_status=stage_status,
            candidate_id=int(candidate.candidate_id),
            answer_dps=answer_dps,
        )
        results: list[RefinedCandidate] = [primary_candidate]
        if stage_status == TARGET_REACHED:
            return tuple(results)
        closures = _build_integer_constraint_closures(
            bundle=bundle,
            point=current,
            dps=final_dps,
        )
        if not closures:
            return tuple(results)
        closure_status, closure_point, closure_answer_dps, closure_history = self._run_integer_closure_path(
            bundle=bundle,
            evaluator=evaluator,
            start_point=current,
            bounds=bounds,
            preserve_hard_feasibility=primary_candidate.hard_feasible,
            integer_closures=closures,
        )
        closure_candidate = self._build_refined_candidate(
            bundle=bundle,
            candidate=candidate,
            evaluator=evaluator,
            point=closure_point,
            phase_history=tuple(history) + closure_history,
            stage_status=closure_status,
            candidate_id=_integer_closure_candidate_id(int(candidate.candidate_id)),
            answer_dps=closure_answer_dps,
        )
        if closure_candidate.residual_norm_hp < primary_candidate.residual_norm_hp:
            results.append(closure_candidate)
        return tuple(results)
