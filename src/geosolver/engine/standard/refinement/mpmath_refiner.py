"""Active mpmath-based staged local refiner for the research pipeline."""

from __future__ import annotations

import ast
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from fractions import Fraction
from functools import lru_cache, partial

from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import (
    FloatCandidate,
    RefinedCandidate,
    RefinementBatchResult,
)
from geosolver.engine.standard.contracts.evaluator_port import EvaluatorPort
from geosolver.engine.standard.contracts.local_refiner_port import LocalRefinerPort
from geosolver.engine.standard.contracts.problem_bundle import ProblemBundle
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.high_precision_expressions import (
    build_solution_context_high_precision,
    to_mpf_value,
)
from geosolver.engine.standard.evaluation.snapshots import uses_evaluation_store
from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import (
    BoundaryOrigin,
    boundary_float_to_mpf,
)
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.precision.type_guards.mp_types import MPFloat
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.problem.logical_equalities import evaluation_sources
from geosolver.runtime.deadline import (
    count_event,
    expired,
    retain_candidates,
    timed_phase,
    uses_deadline,
)

from .analytic_jacobian import derivative_plan, evaluate_jacobian
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
_WARM_NEWTON_MAX_STEPS = 12


class _ClosureDeadlineExceeded(RuntimeError):
    """Internal control signal for an optional closure that used its budget."""


def _problem_contains_call(spec: object, function_name: str) -> bool:
    """Return whether any user expression in ``spec`` calls ``function_name``.

    Angle residuals contain an absolute-value cusp at collinear configurations.
    The refiner uses this narrow syntactic signal to opt into the one-sided
    finite-difference fallback; all other problems retain centered differences.
    """
    texts: list[str] = []
    for construction in getattr(spec, "construction", ()) or ():
        expression = getattr(construction, "expr", None)
        if isinstance(expression, str):
            texts.append(expression)
    # Only expressions that contribute to the residual/objective are relevant
    # to this Jacobian.  Hard guards are checked separately and should not
    # alter the numerical derivative policy of an otherwise smooth system.
    for attribute in ("constraints",):
        for expression in getattr(spec, attribute, ()) or ():
            if isinstance(expression, str):
                texts.extend(evaluation_sources(expression, getattr(spec, "logical_plans", ())))
    # ``answer_expr`` is evaluated after refinement and is not part of the
    # residual Jacobian.  Including it here would change the finite-difference
    # policy for an otherwise smooth problem merely because its requested
    # output happens to be an angle.
    for attribute in ("objective_expr",):
        expression = getattr(spec, attribute, None)
        if isinstance(expression, str):
            texts.append(expression)

    return _expressions_contain_call(tuple(texts), function_name)


@lru_cache(maxsize=2048)
def _expressions_contain_call(texts: tuple[str, ...], function_name: str) -> bool:
    """An immutable expression property, never parse it at every LM step."""
    for expression in texts:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == function_name:
                return True
    return False


def _vector_norm(values: list[MPFloat]) -> MPFloat:
    return mp.sqrt(mp.fsum(value * value for value in values))


@dataclass(frozen=True)
class CandidateEvaluationSnapshot:
    """One completed evaluation of the original residual system and hard checks."""

    point: tuple
    precision: int
    evaluator: object
    residual_norm: object
    hard: object

    def matches(self, point, precision, evaluator):
        return (
            self.point == tuple(point)
            and self.precision == precision
            and self.evaluator is evaluator
        )


def _deferred_refined_candidate(
    *,
    candidate: FloatCandidate,
    point: list[MPFloat],
    candidate_id: int,
    answer_dps: int,
    phase_history: tuple[str, ...],
    integer_closures=(),
) -> RefinedCandidate:
    """Retain an iterate at a phase cutoff, never an unverified answer.

    Phase C must independently re-evaluate and verify this draft under the
    remaining solve budget. No further geometry evaluation belongs here.
    """
    count_event("refinement_deadline_drafts")
    return RefinedCandidate(
        x_hp=tuple(point),
        residual_norm_hp=mp.inf,
        answer_hp=None,
        refinement_status="deadline_reached",
        phase_history=(*phase_history, "final_evaluation_deferred"),
        source=candidate,
        candidate_id=int(candidate_id),
        coordinate_precision_dps=int(answer_dps),
        derivation_kind="integer_closure" if integer_closures else "",
        constraint_indices=tuple(c.constraint_index for c in integer_closures),
        target_integers=tuple(int(c.target_integer) for c in integer_closures),
    )


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
    except TimeoutError:
        raise
    except Exception:
        return False


def _extract_isinteger_inner_expression(constraint_expression: str) -> str | None:
    """Extract an integer-valued expression from a discrete numeric constraint.

    A prime constraint necessarily implies integrality, so it uses the same
    projection and closure machinery.  Primality itself is re-evaluated by the
    original ``IsPrime`` residual after projection.
    """

    from geosolver.engine.standard.problem.zero_test_source import zero_test_call

    call = zero_test_call(constraint_expression)
    if not isinstance(call, ast.Call):
        return None
    if call.keywords or len(call.args) != 1:
        return None
    if not isinstance(call.func, ast.Name) or call.func.id not in {"IsInteger", "IsPrime"}:
        return None
    return ast.get_source_segment(constraint_expression, call.args[0])


def _integer_closure_candidate_id(base_candidate_id: int) -> int:
    """Derive a stable negative id for closure-derived candidates."""

    return -abs(int(base_candidate_id)) - 1


def _integer_target_tuple_candidate_id(
    base_candidate_id: int,
    target_integers: tuple[MPFloat, ...],
) -> int:
    """Bounded display ID; only CandidateKey provides exact tuple identity."""

    import hashlib

    def encode_integer(value):
        integer = _nearest_integer(value)
        return (str(integer) if integer.bit_length() <= 1024 else hex(integer)).encode("ascii")

    encoded = encode_integer(base_candidate_id) + b":"
    encoded += b",".join(encode_integer(target) for target in target_integers)
    if len(encoded) > 128:
        encoded = hashlib.sha256(encoded).digest()
    return -int.from_bytes(b"\x01" + encoded, "big")


def _nearest_integer(value):
    """Do not round a stored high-precision integer at a lower ambient precision."""
    if isinstance(value, int):
        return value
    precision = max(mp.prec, getattr(value, "_mpf_", (0, 0, 0, 0))[3])
    with mp.workprec(precision):
        return int(mp.nint(value))


def _exact_integer_mpf(value):
    integer = _nearest_integer(value)
    return mp.mpf(integer, prec=max(mp.prec, integer.bit_length() + 1))


def _build_hp_context(
    *,
    bundle: ProblemBundle,
    point: list[MPFloat],
    dps: int,
) -> dict[str, object]:
    """Build the high-precision evaluation context for one point."""

    return build_solution_context_high_precision(
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
    """Return all top-level zero-target integer or prime constraints."""

    plan = getattr(bundle, "analysis_plan", None)
    return plan.integer_specs if plan is not None else _build_integer_specs(bundle=bundle)


def _build_integer_specs(*, bundle):
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
        with mp.workdps(int(dps)), high_precision_mode():
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
    except TimeoutError:
        raise
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
                target_integer=_exact_integer_mpf(target),
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


def _exact_answer_from_integer_closures(
    *,
    bundle: ProblemBundle,
    closures: tuple[IntegerConstraintClosure, ...],
    precision: int = 120,
) -> MPFloat | None:
    """Evaluate a small arithmetic answer exactly from integer variables.

    This deliberately handles only the closed form ``IsInteger(variable)``
    case and arithmetic over those variables.  Geometry calls, arbitrary
    expressions, and non-variable integer closures are left to the numerical
    answer evaluator; they do not provide enough evidence for an exact hint.
    """
    if not closures or bundle.spec.answer_expr is None:
        return None
    integer_bindings: dict[str, int] = {}
    variable_names = set(bundle.var_names)
    for closure in closures:
        try:
            node = ast.parse(closure.inner_expression, mode="eval").body
        except (SyntaxError, TypeError, ValueError):
            return None
        if not isinstance(node, ast.Name) or node.id not in variable_names:
            return None
        target = mp.mpf(closure.target_integer)
        if not mp.isfinite(target) or target != mp.nint(target):
            return None
        integer_bindings[node.id] = int(mp.nint(target))
    if not integer_bindings:
        return None

    try:
        answer_node = ast.parse(bundle.spec.answer_expr, mode="eval").body

        def evaluate(node: ast.AST) -> Fraction:
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, int)
                and not isinstance(node.value, bool)
            ):
                return Fraction(int(node.value))
            if isinstance(node, ast.Name) and node.id in integer_bindings:
                return Fraction(integer_bindings[node.id])
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
                value = evaluate(node.operand)
                return value if isinstance(node.op, ast.UAdd) else -value
            if isinstance(node, ast.BinOp):
                left = evaluate(node.left)
                right = evaluate(node.right)
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Mult):
                    return left * right
                if isinstance(node.op, ast.Div):
                    return left / right
                if isinstance(node.op, ast.Pow) and right.denominator == 1:
                    return left ** int(right)
            raise ValueError("answer is not arithmetic over integer variables")

        exact = evaluate(answer_node)
    except (ArithmeticError, SyntaxError, TypeError, ValueError, ZeroDivisionError):
        return None
    with mp.workdps(max(50, int(precision))):
        return mp.mpf(exact.numerator) / mp.mpf(exact.denominator)


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
        with mp.workdps(int(dps)), high_precision_mode():
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
    except TimeoutError:
        raise
    except Exception:
        return None


def _residual_vector_without_integer_constraints(
    evaluator: EvaluatorPort,
    point: list[MPFloat],
    dps: int,
    *,
    integer_constraint_indices: tuple[int, ...],
) -> list[MPFloat] | None:
    """Evaluate residuals with top-level integer constraints removed."""

    with mp.workdps(int(dps)), high_precision_mode():
        hp_eval = evaluator.evaluate_hp_residual(point, precision=int(dps))
    if hp_eval.evaluation_status is not EvaluationStatus.OK:
        return None
    skipped = set(int(index) for index in integer_constraint_indices)
    residuals = [
        mp.mpf(value) for index, value in enumerate(hp_eval.residual_vector) if index not in skipped
    ]
    if not residuals:
        return None
    return residuals


@lru_cache(maxsize=256)
def _zero_constraint_plans(constraints, targets):
    from geosolver.engine.standard.problem.zero_test_source import zero_test_call

    plans = {}
    for index, expression in enumerate(constraints):
        if index >= len(targets) or not _is_zero_target(targets[index]):
            continue
        node = zero_test_call(expression)
        if not isinstance(node, ast.Call) or node.keywords or len(node.args) != _BINARY_ARITY:
            continue
        if not isinstance(node.func, ast.Name):
            continue
        kind = node.func.id.lower()
        if kind in {"distance", "istangent"}:
            plans[index] = kind, tuple(ast.get_source_segment(expression, arg) for arg in node.args)
    return plans


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
    * circle--circle tangency -> the nearer signed inner/outer distance gap.

    The original evaluator remains the certification source; this helper only
    changes the residuals supplied to an optimization step.  Constraints that
    do not match these exact top-level forms are returned unchanged.
    """
    from geosolver.engine.standard.problem.tangency_contacts import distance_contact_sources

    equalities = tuple(
        zip(bundle.spec.constraints, (str(target) for target in bundle.targets), strict=True)
    )
    contact_sources = distance_contact_sources(
        tuple((item.name, item.expr) for item in bundle.spec.construction), equalities
    )
    from geosolver.engine.standard.problem.positive_radius_contacts import (
        positive_radius_contact_sources,
    )

    radius_deflations = positive_radius_contact_sources(
        tuple(bundle.var_names),
        tuple((item.name, item.expr) for item in bundle.spec.construction),
        equalities,
    )
    plans = _zero_constraint_plans(tuple(bundle.spec.constraints), tuple(bundle.targets))
    if not plans and not contact_sources and not radius_deflations:
        return residuals

    try:
        with mp.workdps(int(dps)), high_precision_mode():
            context = build_solution_context_high_precision(
                bundle.spec,
                list(bundle.var_names),
                point,
                bundle.base_context,
                int(dps),
                expressions=[expr for _, expressions in plans.values() for expr in expressions]
                + list(contact_sources.values())
                + list(radius_deflations),
            )
            rewritten: list[MPFloat] = []
            for index, residual in enumerate(residuals):
                contact_source = contact_sources.get(index)
                if contact_source is not None:
                    rewritten.append(mp.mpf(safe_eval_expr_hp(contact_source, context)))
                    continue
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
                    from geosolver.engine.standard.problem.tangency_contacts import (
                        contact_tangency_source,
                    )

                    contact_source = contact_tangency_source(
                        left_expr,
                        right_expr,
                        tuple((item.name, item.expr) for item in bundle.spec.construction),
                        tuple(
                            zip(
                                bundle.spec.constraints,
                                (str(target) for target in bundle.targets),
                                strict=True,
                            )
                        ),
                    )
                    if contact_source is not None:
                        rewritten.append(mp.mpf(safe_eval_expr_hp(contact_source, context)))
                        continue
                    left = getattr(left, "circle", left)
                    right = getattr(right, "circle", right)
                    if hasattr(left, "radius") and hasattr(right, "radius"):
                        from geosolver.geometry.mp.signed_tangency import signed_tangency

                        rewritten.append(signed_tangency(left, right))
                        continue
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
            # These are necessary consequences after dividing by a radius
            # proven nonzero by its original Circle construction domain.
            # Keep every original row as well as the auxiliary equations.
            rewritten.extend(
                mp.mpf(safe_eval_expr_hp(source, context)) for source in radius_deflations
            )
            return rewritten
    except TimeoutError:
        raise
    except Exception:
        # This is an optimization aid, never a second failure path for the
        # evaluator.  Keep the source residuals if a construction is not a
        # supported point/line/circle object.
        return residuals


def _normalize_findroot_point(root: object) -> list[MPFloat] | None:
    if isinstance(root, mp.matrix):
        values = [mp.mpf(root[index]) for index in range(len(root))]
        return values
    if isinstance(root, list | tuple):
        return [mp.mpf(value) for value in root]
    try:
        return [mp.mpf(root)]
    except (TypeError, ValueError):
        return None


def _select_rank_revealing_subsystem(
    jacobian: list[list[MPFloat]],
    *,
    dps: int,
    relative_tolerance: MPFloat | None = None,
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
        # Explicit error bounds (used by final verification) are already in
        # scaled units and must retain their original rank threshold.
        if relative_tolerance is None:
            # Equilibrate equations and coordinates before testing numerical rank.
            # Nonzero diagonal scaling preserves rank and avoids discarding an
            # independent equation merely because its units make it very small.
            for row in matrix:
                row_scale = max(abs(value) for value in row)
                if row_scale:
                    row[:] = [value / row_scale for value in row]
            for column in range(column_count):
                column_scale = max(abs(row[column]) for row in matrix)
                if column_scale:
                    for row in matrix:
                        row[column] /= column_scale
        scale = max(abs(value) for row in matrix for value in row)
        if scale == 0:
            return None

        # Centered differences use a step no smaller than roughly 1e-30 in
        # this refiner.  Keeping 25 relative digits separates the real small
        # pivots seen in geometry problems from differencing noise without
        # pretending that the numerical Jacobian is exact.
        if relative_tolerance is None:
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
    one_sided_at_cusp: bool = False,
    initial_jacobian: list[list[MPFloat]] | None = None,
    derivative_fn: Callable[[list[MPFloat]], list[list[MPFloat]] | None] | None = None,
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
        except TimeoutError:
            raise
        except Exception:
            return None

    jacobian = initial_jacobian
    if jacobian is None and derivative_fn is not None:
        jacobian = derivative_fn(start_point)
    if jacobian is None:
        jacobian = compute_finite_difference_jacobian(
            point=start_point,
            dps=int(dps),
            residual_fn=jacobian_residual_fn,
            one_sided_at_cusp=bool(one_sided_at_cusp),
        )
    if jacobian is None:
        return None
    subsystem = _select_rank_revealing_subsystem(jacobian, dps=int(dps))
    if subsystem is None:
        return None
    residual_indices, variable_indices = subsystem
    with mp.workdps(int(dps)):
        fixed_point = [+mp.mpf(value) for value in start_point]

    def assemble_point(active_values: tuple[MPFloat, ...]) -> list[MPFloat]:
        point = [mp.mpf(value) for value in fixed_point]
        for variable_index, value in zip(variable_indices, active_values, strict=True):
            point[variable_index] = mp.mpf(value)
        return point

    def selected_residuals(*active_values: MPFloat) -> tuple[MPFloat, ...]:
        residuals = evaluate_residuals(assemble_point(tuple(active_values)))
        return tuple(residuals[index] for index in residual_indices)

    def selected_jacobian(*active_values):
        values = derivative_fn(assemble_point(tuple(active_values)))
        if values is not None:
            return mp.matrix([[values[i][j] for j in variable_indices] for i in residual_indices])
        from mpmath.calculus.optimization import jacobian

        return jacobian(mp, selected_residuals, mp.matrix(active_values))

    options = {"J": selected_jacobian} if derivative_fn is not None else {}
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
                    # A redundant scalar equation must not reduce the ordinary
                    # precision-scaled scalar budget to the multivariate chart cap.
                    maxsteps=(
                        int(max_steps)
                        if len(start_point) == 1
                        else min(int(max_steps), _RANK_AWARE_MAX_STEPS)
                    ),
                )
            else:
                root = mp.findroot(
                    selected_residuals,
                    active_start,
                    **options,
                    solver="mnewton",
                    tol=mp.mpf(target_residual),
                    maxsteps=min(int(max_steps), _RANK_AWARE_MAX_STEPS),
                )
            normalized_active = _normalize_findroot_point(root)
    except (TypeError, ValueError, ZeroDivisionError, IndexError, _ClosureDeadlineExceeded):
        return None
    if normalized_active is None or len(normalized_active) != len(variable_indices):
        return None
    with mp.workdps(int(dps)):
        return assemble_point(tuple(normalized_active))


def _convert_problem_bounds(
    bundle: ProblemBundle,
) -> tuple[tuple[MPFloat | None, MPFloat | None], ...]:
    plan = getattr(bundle, "analysis_plan", None)
    precision = max(mp.dps, 530)
    return (
        plan.mathematical_bounds_at_precision(precision)
        if plan is not None
        else _convert_bounds_uncached(bundle, precision)
    )


def _convert_bounds_uncached(bundle, precision):
    from geosolver.engine.standard.interpreter.context.high_precision import (
        _get_high_precision_context,
    )
    from geosolver.problem.domain_bounds import mathematical_bounds

    domains = mathematical_bounds(bundle.spec)
    # Bounds are shared by all refinement stages, including the 500-digit
    # closure. Do not evaluate irrational limits through float or ambient dps.
    with mp.workdps(precision), high_precision_mode():
        context = _get_high_precision_context(mp.dps)
        return tuple(
            tuple(
                None if value is None else safe_eval_expr_hp(str(value), context)
                for value in (domains[name].lower, domains[name].upper)
            )
            for name in bundle.var_names
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
    one_sided_at_cusp: bool = False,
    solver_tolerance: MPFloat | None = None,
) -> tuple[list[MPFloat], MPFloat] | None:
    if len(start_point) == 0:
        return None
    tolerance = target_residual if solver_tolerance is None else solver_tolerance

    def evaluate_residuals(point: list[MPFloat]) -> tuple[MPFloat, ...]:
        if deadline_monotonic is not None and time.monotonic() >= float(deadline_monotonic):
            raise _ClosureDeadlineExceeded
        if residual_fn is not None:
            with mp.workdps(int(dps)), high_precision_mode():
                values = residual_fn(point, int(dps))
            if values is None:
                raise ValueError("closure residual evaluation failed")
            return tuple(values)
        with mp.workdps(int(dps)), high_precision_mode():
            hp_eval = evaluator.evaluate_hp_residual(point, precision=int(dps))
        if hp_eval.evaluation_status is not EvaluationStatus.OK:
            raise ValueError(f"findroot residual status={hp_eval.evaluation_status.value}")
        return tuple(hp_eval.residual_vector)

    def certify(point: list[MPFloat] | None) -> tuple[list[MPFloat], MPFloat] | None:
        if deadline_monotonic is not None and time.monotonic() >= float(deadline_monotonic):
            return None
        if point is None or len(point) != len(start_point):
            return None
        if not _point_within_bounds(point, bounds):
            return None
        with mp.workdps(int(dps)), high_precision_mode():
            hp_eval = evaluator.evaluate_hp_residual(point, precision=int(dps))
        if hp_eval.evaluation_status is not EvaluationStatus.OK:
            return None
        with mp.workdps(int(dps)):
            residual_norm = _vector_norm(list(hp_eval.residual_vector))
        # ``mp.findroot`` can stop because its step became small even when the
        # residual is still far above the requested tolerance.  A rank-aware
        # chart changes only the Newton coordinates, never this certification
        # over every original source residual.
        if not mp.isfinite(residual_norm) or residual_norm > mp.mpf(target_residual):
            return None
        return point, residual_norm

    # The incoming point can retain more bits than this closure's arithmetic.
    # Keep those bits if every original residual already meets the requested
    # target. Otherwise Newton must start at its own working precision: its
    # damping loop detects stagnation by exact equality of consecutive points.
    certified_start = certify(list(start_point))
    if certified_start is not None:
        return certified_start
    with mp.workdps(int(dps)):
        start_point = [+mp.mpf(value) for value in start_point]

    try:
        initial_residuals = evaluate_residuals(list(start_point))
    except (TypeError, ValueError, ZeroDivisionError, IndexError, _ClosureDeadlineExceeded):
        return None
    standard_point: list[MPFloat] | None = None
    native_residuals = residual_fn is None or (
        isinstance(residual_fn, partial)
        and getattr(residual_fn.func, "__name__", None) == "_residual_vector_for_stage"
        and not residual_fn.keywords.get("integer_closures")
    )
    plan = derivative_plan(getattr(evaluator, "bundle", None)) if native_residuals else None
    if plan is not None and (
        plan["rows"] != len(initial_residuals)
        or (
            plan["requires_smoothing"]
            and not (
                isinstance(residual_fn, partial)
                and residual_fn.keywords.get("smooth_zero_constraints")
            )
        )
    ):
        plan = None

    def analytic_values(point):
        if deadline_monotonic is not None and time.monotonic() >= float(deadline_monotonic):
            raise _ClosureDeadlineExceeded
        with high_precision_mode():
            return evaluate_jacobian(plan, point, int(dps))

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
                        tol=mp.mpf(tolerance),
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
                        tol=mp.mpf(tolerance),
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

        def closure_jacobian(*args):
            if deadline_monotonic is not None and time.monotonic() >= float(deadline_monotonic):
                raise _ClosureDeadlineExceeded
            values = analytic_values(list(args))
            if values is not None:
                return mp.matrix(values)
            from mpmath.calculus.optimization import jacobian

            return jacobian(mp, residuals, mp.matrix(args))

        options = {"J": closure_jacobian} if plan is not None else {}
        try:
            with mp.workdps(int(dps)):
                root = mp.findroot(
                    residuals,
                    tuple(start_point),
                    **options,
                    solver="mnewton",
                    tol=mp.mpf(tolerance),
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
            start_point=list(start_point),
            dps=int(dps),
            target_residual=tolerance,
            max_steps=int(max_steps),
            one_sided_at_cusp=bool(one_sided_at_cusp),
            derivative_fn=analytic_values if plan is not None else None,
        )
    except _ClosureDeadlineExceeded:
        return None
    return certify(rank_aware_point)


@dataclass(frozen=True)
class MpmathRefiner(LocalRefinerPort):
    """Production local refiner using staged LM and high-precision closure."""

    config: RefinerConfig = RefinerConfig()

    @timed_phase("refinement")
    @uses_deadline
    @uses_evaluation_store()
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
            if expired(deadline_monotonic):
                break
            attempted_count += 1
            try:
                completed = self._refine_single_candidate(
                    bundle=bundle,
                    evaluator=evaluator,
                    candidate=candidate,
                    bounds=bounds,
                    deadline_monotonic=deadline_monotonic,
                )
                refined_list.extend(completed)
                retain_candidates(completed)
            except TimeoutError:
                # Inner stages preserve their latest completed update. This
                # fallback covers a cutoff during the initial direct probe,
                # before any such update exists.
                draft = _deferred_refined_candidate(
                    candidate=candidate,
                    point=[
                        boundary_float_to_mpf(value, origin=BoundaryOrigin.INITIAL_POINT)
                        for value in candidate.x_float
                    ],
                    candidate_id=int(candidate.candidate_id),
                    answer_dps=int(mp.dps),
                    phase_history=(),
                )
                refined_list.append(draft)
                retain_candidates((draft,))
                break
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
        )

    @uses_evaluation_store()
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

        completion_snapshot = []
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
            current = list(start_point)
        closures = build_integer_constraint_closures_from_targets(
            specs=specs,
            target_integers=target_integers,
        )
        closure_status, closure_point, closure_answer_dps, closure_history = (
            self._run_integer_closure_path(
                bundle=bundle,
                evaluator=evaluator,
                start_point=current,
                bounds=bounds,
                preserve_hard_feasibility=bool(candidate.hard_feasible),
                integer_closures=closures,
            )
        )
        closure_point, closure_history, closure_status, closure_answer_dps = (
            self._apply_post_lm_closure_polish(
                completion_snapshot=completion_snapshot,
                bundle=bundle,
                evaluator=evaluator,
                bounds=bounds,
                point=closure_point,
                phase_history=closure_history,
                stage_status=closure_status,
                answer_dps=closure_answer_dps,
                integer_closures=closures,
            )
        )
        refined = self._build_refined_candidate(
            evaluation_snapshot=completion_snapshot[-1] if completion_snapshot else None,
            bundle=bundle,
            candidate=candidate,
            evaluator=evaluator,
            point=closure_point,
            phase_history=closure_history,
            stage_status=closure_status,
            candidate_id=_integer_target_tuple_candidate_id(
                int(candidate.candidate_id),
                target_integers,
            ),
            answer_dps=closure_answer_dps,
            integer_closures=closures,
        )
        # An explicit retry may revisit an automatic closure's parent/targets
        # from another start. It must not overwrite that candidate's evidence.
        return replace(refined, derivation_kind="integer_target_enumeration")

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
        integer_constraint_indices = tuple(int(spec.constraint_index) for spec in specs)
        residual_fn = partial(
            _residual_vector_without_integer_constraints,
            evaluator,
            integer_constraint_indices=integer_constraint_indices,
        )
        bounds = _convert_problem_bounds(bundle)
        current = list(start_point)
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
        if stage_status == "deadline_reached":
            return None
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

    @uses_evaluation_store()
    def _residual_vector_for_stage(
        self,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        point: list[MPFloat],
        dps: int,
        integer_closures: tuple[IntegerConstraintClosure, ...] = (),
        smooth_zero_constraints: bool = False,
    ) -> list[MPFloat] | None:
        from geosolver.runtime.deadline import expired

        if expired():
            return None
        with mp.workdps(int(dps)), high_precision_mode():
            hp_eval = evaluator.evaluate_hp_residual(point, precision=int(dps))
        if hp_eval.evaluation_status is not EvaluationStatus.OK:
            return None
        residuals = list(hp_eval.residual_vector)
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
        with mp.workdps(int(dps)), high_precision_mode():
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
        row_dependencies = None
        if residual_fn is None:
            plan = getattr(bundle, "analysis_plan", None)
            if plan is not None:
                row_dependencies = plan.residual_variable_dependencies
            residual_fn = partial(
                self._residual_vector_for_stage,
                bundle,
                evaluator,
                integer_closures=integer_closures,
                smooth_zero_constraints=True,
            )
        current = list(start_point)
        if expired():
            return "deadline_reached", current, mp.inf
        try:
            current_vec = residual_fn(current, int(dps))
        except TimeoutError:
            return "deadline_reached", current, mp.inf
        if current_vec is None:
            return "deadline_reached" if expired() else NON_FINITE_INITIAL, current, mp.inf
        current_norm = _vector_norm(current_vec)
        best = list(current)
        best_norm = current_norm
        damping = mp.mpf(self.config.damping_initial)
        damping_min = mp.mpf(self.config.damping_min)
        damping_scale = mp.mpf(self.config.damping_scale)
        stage_tolerance = mp.mpf(self.config.stage_tolerance)
        stalled_count = 0
        line_failures = 0
        current_jacobian = None
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
            if expired():
                return "deadline_reached", best, best_norm
            if best_norm <= target_residual:
                status = TARGET_REACHED
                break
            try:
                if current_jacobian is None:
                    current_jacobian = compute_finite_difference_jacobian(
                        point=current,
                        dps=int(dps),
                        residual_fn=residual_fn,
                        one_sided_at_cusp=_problem_contains_call(bundle.spec, "Angle"),
                        base_residual=current_vec,
                        row_dependencies=row_dependencies,
                    )
                jacobian = current_jacobian
                if jacobian is None:
                    status = "deadline_reached" if expired() else BRANCH_INSTABILITY
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
                if not improved and preserve_hard_feasibility and integer_closures:
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
            except TimeoutError:
                # A deadline can expire inside any residual/guard callback,
                # not just at the iteration boundary above.
                return "deadline_reached", best, best_norm
            if improved and trial_vec is not None:
                trial_norm = _vector_norm(trial_vec)
                improvement = (current_norm - trial_norm) / max(
                    abs(current_norm),
                    mp.mpf("1e-30"),
                )
                current = list(trial)
                current_vec = list(trial_vec)
                current_jacobian = None
                current_norm = trial_norm
                if trial_norm < best_norm:
                    best = list(current)
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
        integer_closures: tuple[IntegerConstraintClosure, ...] = (),
        evaluation_snapshot: CandidateEvaluationSnapshot | None = None,
    ) -> RefinedCandidate:
        if stage_status == "deadline_reached" or expired():
            return _deferred_refined_candidate(
                candidate=candidate,
                point=point,
                candidate_id=int(candidate_id),
                answer_dps=int(answer_dps),
                phase_history=phase_history,
                integer_closures=integer_closures,
            )
        try:
            if evaluation_snapshot is not None and evaluation_snapshot.matches(
                point, int(answer_dps), evaluator
            ):
                final_norm, hard_snapshot = (
                    evaluation_snapshot.residual_norm,
                    evaluation_snapshot.hard,
                )
                if final_norm is None:
                    vector = self._residual_vector_for_stage(
                        bundle=bundle,
                        evaluator=evaluator,
                        point=point,
                        dps=int(answer_dps),
                    )
                    final_norm = mp.inf if vector is None else _vector_norm(vector)
                count_event("refinement_snapshot_reuses")
            else:
                final_vector = self._residual_vector_for_stage(
                    bundle=bundle,
                    evaluator=evaluator,
                    point=point,
                    dps=int(answer_dps),
                )
                final_norm = mp.inf if final_vector is None else _vector_norm(final_vector)
                hard_snapshot = _evaluate_hard_feasibility(evaluator, point, int(answer_dps))
            answer = _exact_answer_from_integer_closures(
                bundle=bundle,
                closures=integer_closures,
                precision=max(120, int(answer_dps)),
            )
            if answer is None:
                answer = self._evaluate_answer(
                    evaluator=evaluator,
                    point=point,
                    dps=int(answer_dps),
                )
        except TimeoutError:
            return _deferred_refined_candidate(
                candidate=candidate,
                point=point,
                candidate_id=int(candidate_id),
                answer_dps=int(answer_dps),
                phase_history=phase_history,
                integer_closures=integer_closures,
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
            coordinate_precision_dps=int(answer_dps),
            answer_precision_dps=int(answer_dps),
            derivation_kind="integer_closure" if integer_closures else "",
            constraint_indices=tuple(c.constraint_index for c in integer_closures),
            target_integers=tuple(int(c.target_integer) for c in integer_closures),
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
        except TimeoutError:
            raise
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
            evaluation_snapshot=CandidateEvaluationSnapshot(
                tuple(point), direct_dps, evaluator, final_norm, hard_snapshot
            ),
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
        integer_closures: tuple[IntegerConstraintClosure, ...] = (),
        deadline_monotonic: float | None = None,
        completion_snapshot=None,
    ) -> tuple[list[MPFloat], tuple[str, ...], str, int]:
        current = list(point)
        history = list(phase_history)
        if stage_status == "deadline_reached" or expired(deadline_monotonic):
            return current, tuple(history), "deadline_reached", answer_dps
        final_dps = int(max(self.config.schedule_dps))
        try:
            final_vector = self._residual_vector_for_stage(
                bundle=bundle,
                evaluator=evaluator,
                point=current,
                dps=final_dps,
                integer_closures=integer_closures,
                smooth_zero_constraints=not bool(integer_closures),
            )
            if final_vector is None:
                if expired(deadline_monotonic):
                    stage_status = "deadline_reached"
                return current, tuple(history), stage_status, answer_dps
            final_norm = _vector_norm(final_vector)
            hard_snapshot = _evaluate_hard_feasibility(
                evaluator,
                current,
                final_dps,
            )
        except TimeoutError:
            return current, tuple(history), "deadline_reached", answer_dps
        if completion_snapshot is not None:
            completion_snapshot[:] = [
                CandidateEvaluationSnapshot(
                    tuple(current), final_dps, evaluator, None, hard_snapshot
                )
            ]
        closure_threshold = _closure_start_threshold(self.config, final_dps)
        if not hard_snapshot.hard_feasible or final_norm > closure_threshold:
            return current, tuple(history), stage_status, answer_dps
        closure_stages = tuple(
            int(stage) for stage in self.config.closure_schedule_dps if int(stage) >= final_dps
        )
        closure_residual_fn = partial(
            self._residual_vector_for_stage,
            bundle,
            evaluator,
            integer_closures=integer_closures,
            smooth_zero_constraints=not bool(integer_closures),
        )
        for closure_dps in closure_stages:
            if expired(deadline_monotonic):
                stage_status = "deadline_reached"
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
            try:
                closed = _run_findroot_closure(
                    evaluator=evaluator,
                    start_point=current,
                    bounds=bounds,
                    dps=closure_dps,
                    target_residual=mp.mpf(self.config.target_for_dps(closure_dps)),
                    max_steps=closure_max_steps,
                    residual_fn=closure_residual_fn,
                    deadline_monotonic=deadline_monotonic,
                    one_sided_at_cusp=_problem_contains_call(bundle.spec, "Angle"),
                )
                if closed is None:
                    if expired(deadline_monotonic):
                        stage_status = "deadline_reached"
                        break
                    continue
                closed_point, closed_norm = closed
                closed_hard_snapshot = _evaluate_hard_feasibility(
                    evaluator,
                    closed_point,
                    closure_dps,
                )
            except TimeoutError:
                # Keep the last *completed* precision, not an interrupted
                # closure's coordinates or an old objective at a new point.
                stage_status = "deadline_reached"
                break
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
            if completion_snapshot is not None:
                completion_snapshot[:] = [
                    CandidateEvaluationSnapshot(
                        tuple(closed_point), closure_dps, evaluator, None, closed_hard_snapshot
                    )
                ]
            current = closed_point
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
        current = list(start_point)
        history: list[str] = []
        target_summary = ",".join(
            f"{closure.constraint_index}:{closure.target_integer}" for closure in integer_closures
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
            if stage_status == "deadline_reached":
                break
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
        completion_snapshot = []
        with mp.workdps(max(200, int(max(self.config.schedule_dps)))):
            current = (
                [mp.mpf(value) for value in candidate.initial_point_decimal]
                if len(candidate.initial_point_decimal) == len(candidate.x_float)
                and candidate.initial_point_decimal
                else [
                    boundary_float_to_mpf(value, origin=BoundaryOrigin.INITIAL_POINT)
                    for value in candidate.x_float
                ]
            )
        direct_candidate = self._direct_accept_candidate(
            bundle=bundle,
            evaluator=evaluator,
            candidate=candidate,
            point=current,
        )
        if direct_candidate is not None:
            if direct_candidate.refinement_status == "deadline_reached":
                return (direct_candidate,)
            # A direct numerical acceptance is not an exactness certificate
            # when the problem contains explicit integer-valued constraints.
            # Close those constraints first so the answer is evaluated on the
            # certified integer branch (rather than, e.g., at 21 + 1e-85).
            try:
                integer_closures = _build_integer_constraint_closures(
                    bundle=bundle,
                    point=current,
                    dps=max(
                        int(self.config.direct_accept_dps),
                        int(max(self.config.schedule_dps)),
                    ),
                )
            except TimeoutError:
                return (direct_candidate,)
            if integer_closures:
                closure_status, closure_point, closure_answer_dps, closure_history = (
                    self._run_integer_closure_path(
                        bundle=bundle,
                        evaluator=evaluator,
                        start_point=current,
                        bounds=bounds,
                        preserve_hard_feasibility=bool(candidate.hard_feasible),
                        integer_closures=integer_closures,
                    )
                )
                (
                    polished_point,
                    polished_history,
                    polished_status,
                    polished_answer_dps,
                ) = self._apply_post_lm_closure_polish(
                    completion_snapshot=completion_snapshot,
                    bundle=bundle,
                    evaluator=evaluator,
                    bounds=bounds,
                    point=closure_point,
                    phase_history=closure_history,
                    stage_status=closure_status,
                    answer_dps=closure_answer_dps,
                    integer_closures=integer_closures,
                    deadline_monotonic=deadline_monotonic,
                )
                if polished_status in (TARGET_REACHED, "deadline_reached"):
                    return (
                        self._build_refined_candidate(
                            evaluation_snapshot=completion_snapshot[-1]
                            if completion_snapshot
                            else None,
                            bundle=bundle,
                            candidate=candidate,
                            evaluator=evaluator,
                            point=polished_point,
                            phase_history=polished_history,
                            stage_status=polished_status,
                            candidate_id=int(candidate.candidate_id),
                            answer_dps=polished_answer_dps,
                            integer_closures=integer_closures,
                        ),
                    )

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
                    completion_snapshot=completion_snapshot,
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
            if polished_status == "deadline_reached" or (
                polished_status == TARGET_REACHED and not integer_closures
            ):
                return (
                    self._build_refined_candidate(
                        evaluation_snapshot=completion_snapshot[-1]
                        if completion_snapshot
                        else None,
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
        # A float search point close to a regular root can usually gain the
        # first high-precision digits with undamped Newton rather than dozens
        # of damped LM/backtracking iterations. This is only a warm start:
        # every configured LM stage, closure and final verification still runs.
        # Failed or infeasible Newton attempts leave the original point intact.
        if (
            len(current) > 1
            and len(bundle.spec.constraints) >= len(current)
            and candidate.hard_feasible
            and not build_integer_constraint_specs(bundle=bundle)
            and not expired(deadline_monotonic)
        ):
            warm_dps = int(max(self.config.schedule_dps))
            warm_target = mp.mpf(self.config.target_for_dps(warm_dps))
            count_event("warm_newton_attempts")
            closed = _run_findroot_closure(
                evaluator=evaluator,
                start_point=current,
                bounds=bounds,
                dps=warm_dps,
                target_residual=warm_target,
                # mpmath checks a squared residual against tol. The returned
                # root must also meet the original unsquared residual target.
                solver_tolerance=warm_target * warm_target,
                max_steps=_WARM_NEWTON_MAX_STEPS,
                residual_fn=partial(
                    self._residual_vector_for_stage,
                    bundle,
                    evaluator,
                    smooth_zero_constraints=True,
                ),
                deadline_monotonic=deadline_monotonic,
                one_sided_at_cusp=_problem_contains_call(bundle.spec, "Angle"),
            )
            if closed is not None:
                warm_point, warm_norm = closed
                hard = _evaluate_hard_feasibility(evaluator, warm_point, warm_dps)
                if hard.hard_feasible:
                    current = warm_point
                    history.append(f"{warm_dps}:warm_newton:{warm_norm}")
                    count_event("warm_newton_successes")
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
                preserve_hard_feasibility=bool(candidate.hard_feasible),
            )
            history.append(f"{dps}:{stage_status}:{stage_norm}")
            answer_dps = int(dps)
            if stage_status == "deadline_reached":
                break
            if stage_norm <= target:
                continue
            if stage_norm <= promotion_threshold:
                history.append(f"{dps}:promote:{stage_norm}")
                continue
            if stage_status != TARGET_REACHED:
                break
        final_dps = int(max(self.config.schedule_dps))
        if stage_status != "deadline_reached":
            answer_dps = final_dps
        current, phase_history, stage_status, answer_dps = self._apply_post_lm_closure_polish(
            completion_snapshot=completion_snapshot,
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
            evaluation_snapshot=completion_snapshot[-1] if completion_snapshot else None,
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
        if primary_candidate.refinement_status == "deadline_reached":
            return tuple(results)
        try:
            closures = _build_integer_constraint_closures(
                bundle=bundle,
                point=current,
                dps=final_dps,
            )
        except TimeoutError:
            return tuple(results)
        if not closures:
            return tuple(results)
        closure_status, closure_point, closure_answer_dps, closure_history = (
            self._run_integer_closure_path(
                bundle=bundle,
                evaluator=evaluator,
                start_point=current,
                bounds=bounds,
                preserve_hard_feasibility=primary_candidate.hard_feasible,
                integer_closures=closures,
            )
        )
        closure_point, polished_closure_history, closure_status, closure_answer_dps = (
            self._apply_post_lm_closure_polish(
                completion_snapshot=completion_snapshot,
                bundle=bundle,
                evaluator=evaluator,
                bounds=bounds,
                point=closure_point,
                phase_history=phase_history + closure_history,
                stage_status=closure_status,
                answer_dps=closure_answer_dps,
                integer_closures=closures,
                deadline_monotonic=deadline_monotonic,
            )
        )
        closure_candidate = self._build_refined_candidate(
            evaluation_snapshot=completion_snapshot[-1] if completion_snapshot else None,
            bundle=bundle,
            candidate=candidate,
            evaluator=evaluator,
            point=closure_point,
            phase_history=polished_closure_history,
            stage_status=closure_status,
            candidate_id=_integer_closure_candidate_id(int(candidate.candidate_id)),
            answer_dps=closure_answer_dps,
            integer_closures=closures,
        )
        # Keep the closure-derived candidate even when both residuals round to
        # zero at the evaluator precision: it carries the exact arithmetic
        # answer obtained from the certified integer targets.
        if (
            closure_candidate.residual_norm_hp <= primary_candidate.residual_norm_hp
            or closure_candidate.answer_hp != primary_candidate.answer_hp
        ):
            results.append(closure_candidate)
        return tuple(results)
