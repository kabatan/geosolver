"""Integer segment displacements in a fixed-length parallel-side construction.

A fixed squared length has finitely many integer displacement vectors. When
AB and CD are parallel, fixing BC=d forces B onto the rational line through A
in direction D-A-d. Sample that integer line instead of a four-dimensional
box. A canonical unit lattice witness is only a proposal. An unresolved
displacement keeps the ordinary backend; no placement scale list is sampled.
The original evaluator and final verifier accept every resulting seed.
"""

import ast
import math
from dataclasses import dataclass, replace
from fractions import Fraction
from functools import lru_cache

from geosolver.engine.standard.problem.zero_test_source import rational_constant, zero_test_call
from geosolver.engine.standard.search.discrete.square_difference import _add, _Compiler, _Point
from geosolver.problem.expression_source import annotate_source, source_expression
from geosolver.runtime.deadline import check_deadline


def _parse(source):
    return annotate_source(ast.parse(source, mode="eval"), source).body


def _call(node, name, count):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
        and len(node.args) == count
        and not node.keywords
    )


def _integer_line(a, direction):
    """Return one integer point and a primitive integer step, or None."""
    p, q = direction[1], -direction[0]
    r = p * a[0] + q * a[1]
    denominator = math.lcm(p.denominator, q.denominator, r.denominator)
    p, q, r = (int(value * denominator) for value in (p, q, r))
    g = math.gcd(p, q)
    if not g or r % g:
        return None
    # Extended Euclid, including signed/zero coefficients.
    old_r, new_r, old_s, new_s, old_t, new_t = abs(p), abs(q), 1, 0, 0, 1
    while new_r:
        quotient = old_r // new_r
        old_r, new_r = new_r, old_r - quotient * new_r
        old_s, new_s = new_s, old_s - quotient * new_s
        old_t, new_t = new_t, old_t - quotient * new_t
    x = old_s * (1 if p >= 0 else -1) * (r // g)
    y = old_t * (1 if q >= 0 else -1) * (r // g)
    return (x, y), (q // g, -p // g)


@dataclass(frozen=True)
class IntegerSegmentPlan:
    branches: tuple
    excluded_displacements: int
    total_displacements: int


@lru_cache(maxsize=128)
def _segment_branches(variables, constructions, constraints, targets, guards, answer):
    if len(variables) != 4:
        return None
    definitions = {name: _parse(source) for name, source in constructions}

    def resolve(node):
        seen = set()
        while isinstance(node, ast.Name) and node.id in definitions:
            if node.id in seen:
                raise ValueError("cyclic construction")
            seen.add(node.id)
            node = definitions[node.id]
        return node

    def point(node):
        node = resolve(node)
        if not _call(node, "Point", 2):
            raise ValueError("unsupported point")
        if all(isinstance(arg, ast.Name) and arg.id in variables for arg in node.args):
            return tuple(arg.id for arg in node.args)
        compiler = _Compiler("__unused_coordinate", constructions)
        result = compiler.expression(source_expression(node))
        if not isinstance(result, _Point) or len(result.x) != 1 or len(result.y) != 1:
            raise ValueError("nonconstant anchor")
        return result.x[0], result.y[0]

    def segment(node):
        node = resolve(node)
        if not (_call(node, "Line", 2) or _call(node, "Distance", 2)):
            raise ValueError("unsupported segment")
        return tuple(point(arg) for arg in node.args)

    integers = set()
    for source, target in zip(constraints, targets, strict=True):
        if str(target) != "0":
            continue
        call = zero_test_call(source)
        if _call(call, "IsInteger", 1) and isinstance(call.args[0], ast.Name):
            integers.add(call.args[0].id)
    if set(variables) != integers:
        return None

    def invariant_answer(node, parallel_segments):
        node = resolve(node)
        if _call(node, "Slope", 1):
            return set(segment(node.args[0])) in parallel_segments
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return True
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
            return invariant_answer(node.operand, parallel_segments)
        if isinstance(node, ast.BinOp) and isinstance(
            node.op, ast.Add | ast.Sub | ast.Mult | ast.Div | ast.Pow
        ):
            return invariant_answer(node.left, parallel_segments) and invariant_answer(
                node.right, parallel_segments
            )
        return False

    answer_node = _parse(answer)
    distance_pairs = []
    for left, right in zip(constraints, targets, strict=True):
        try:
            a, b = _parse(left), _parse(str(right))
            if _call(resolve(a), "Distance", 2) and _call(resolve(b), "Distance", 2):
                distance_pairs.append((segment(a), segment(b)))
        except (ValueError, TypeError, SyntaxError):
            continue
    for source, target in zip(constraints, targets, strict=True):
        if str(target) != "0":
            continue
        call = zero_test_call(source)
        if not _call(call, "Parallel", 2):
            continue
        first, second = (segment(arg) for arg in call.args)
        # Every accepted target depends only on slopes of these parallel
        # lines and rational scalar operations. Fixing BC=d fixes their
        # direction D-A-d; the remaining line parameter affects placement
        # witnesses but cannot change this target.
        if not invariant_answer(answer_node, (set(first), set(second))):
            continue
        pairs = []
        for line in (first, second):
            moving = [p for p in line if all(isinstance(v, str) for v in p)]
            fixed = [p for p in line if all(isinstance(v, Fraction) for v in p)]
            if len(moving) != 1 or len(fixed) != 1:
                break
            pairs.append((fixed[0], moving[0]))
        if len(pairs) != 2:
            continue
        (a, b), (d, c) = pairs
        if set(b + c) != set(variables):
            continue
        if not any(
            (set(u) == {a, d} and set(v) == {b, c}) or (set(v) == {a, d} and set(u) == {b, c})
            for u, v in distance_pairs
        ):
            continue
        squared = sum((x - y) ** 2 for x, y in zip(a, d, strict=True))
        if squared.denominator != 1 or not 0 < squared <= 10**6:
            continue
        branches = []
        excluded_displacements = total_displacements = 0

        def impossible(displacement, direction, a=a, b=b, c=c, d=d):
            # Zero direction leaves the parallel-side equation unconstrained;
            # only a guard depending directly on the fixed BC/AD directions
            # can discharge that case. Other branches lie on B=A+k*direction.
            definitions_for_line = tuple(
                (name, f"({origin})+__lattice_parameter*({delta})")
                for name, origin, delta in zip(
                    b + c,
                    a + tuple(a[i] + displacement[i] for i in range(2)),
                    direction + direction,
                    strict=True,
                )
            )
            compiler = _Compiler("__lattice_parameter", constructions + definitions_for_line)
            for source in guards:
                guard = _parse(source)
                if not _call(guard, "AssumeNe", 2):
                    continue
                left, right = guard.args
                resolved = resolve(left)
                if _call(resolved, "Parallel", 2):
                    # Parallel uses unit normals, while the polynomial below
                    # is an unnormalized determinant. Their zero sets agree;
                    # comparison with a nonzero RHS does not survive scaling.
                    # In the zero-direction family a variable RHS also cannot
                    # be evaluated at the arbitrary representative B=A.
                    try:
                        if rational_constant(right) != 0:
                            continue
                    except (ValueError, ArithmeticError):
                        continue
                    lines = tuple(segment(arg) for arg in resolved.args)
                    if direction == (0, 0) and {frozenset(line) for line in lines} != {
                        frozenset((b, c)),
                        frozenset((a, d)),
                    }:
                        continue
                    endpoints = [resolve(arg).args for arg in resolved.args]
                    (p, q), (r, t) = [
                        [source_expression(point) for point in line] for line in endpoints
                    ]
                    left = _parse(
                        f"(({q}).x-({p}).x)*(({t}).y-({r}).y)-(({q}).y-({p}).y)*(({t}).x-({r}).x)",
                    )
                elif direction == (0, 0):
                    continue
                try:
                    difference = _add(
                        compiler.expression(source_expression(left)),
                        compiler.expression(source_expression(right)),
                        -1,
                    )
                    if difference == (0,):
                        return True
                except (ValueError, TypeError, ArithmeticError, RecursionError):
                    continue
            return False

        for dx in range(-math.isqrt(squared.numerator), math.isqrt(squared.numerator) + 1):
            check_deadline()
            dy2 = int(squared) - dx * dx
            dy = math.isqrt(dy2)
            if dy * dy != dy2:
                continue
            for signed_dy in sorted({dy, -dy}):
                displacement = (dx, signed_dy)
                direction = tuple(d[i] - a[i] - displacement[i] for i in range(2))
                total_displacements += 1
                if impossible(displacement, direction):
                    excluded_displacements += 1
                    continue
                line = _integer_line(a, direction)
                if line is None:
                    # A nonzero rational line with no lattice points is also
                    # impossible. The zero direction remains unenumerated.
                    if any(direction):
                        excluded_displacements += 1
                    else:
                        branches.append(())
                    continue
                origin, step = line
                # The exact integer-line construction supplies one canonical
                # origin and primitive step. Use its unit witness only; do not
                # tune additional placements to observed problem instances.
                # Failure of original guards leaves this displacement partial,
                # so scan_integer_segments cannot claim complete coverage.
                bv = tuple(origin[i] + step[i] for i in range(2))
                cv = tuple(bv[i] + displacement[i] for i in range(2))
                values = dict(zip(b + c, bv + cv, strict=True))
                point_values = tuple(float(values[name]) for name in variables)
                if any(
                    not math.isfinite(value) or Fraction(value) != values[name]
                    for name, value in zip(variables, point_values, strict=True)
                ):
                    # Rounded integer coordinates cannot serve as an exact
                    # witness for displacement completeness.
                    return None
                branches.append((point_values,))
        return IntegerSegmentPlan(tuple(branches), excluded_displacements, total_displacements)
    return None


def integer_segment_branches(bundle):
    try:
        return _segment_branches(
            tuple(bundle.var_names),
            tuple((item.name, item.expr) for item in bundle.spec.construction),
            tuple(bundle.spec.constraints),
            tuple(str(value) for value in bundle.spec.v),
            tuple(bundle.spec.guards),
            bundle.spec.answer_expr,
        )
    except (ValueError, TypeError, SyntaxError, ArithmeticError, RecursionError):
        return None


def scan_integer_segments(*, bundle, evaluator, config, constraint_scales=None):
    from geosolver.engine.standard.contracts.candidate_record import SearchBatchResult
    from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
    from geosolver.engine.standard.search.scipy_multistart_backend import (
        _RESIDUAL_ACCEPT_FLOAT,
        _build_candidate,
        _SearchTelemetry,
    )

    plan = integer_segment_branches(bundle)
    if plan is None:
        return None
    telemetry = _SearchTelemetry()
    records, selected = [], []
    for branch_index, points in enumerate(plan.branches):
        for point in points:
            check_deadline()
            candidate = replace(
                _build_candidate(
                    evaluator=evaluator,
                    config=config,
                    bounds=[(-math.inf, math.inf)] * len(point),
                    values=point,
                    origin_seed=int((config.seed_values or (0,))[0]),
                    family_code=91,
                    origin_start_point_index=branch_index,
                    telemetry=telemetry,
                    constraint_scales=constraint_scales,
                ),
                origin_backend="integer_segment_displacements",
                originating_branch_box=tuple(
                    (str(Fraction(value) - Fraction(1, 4)), str(Fraction(value) + Fraction(1, 4)))
                    for value in point
                ),
            )
            records.append(candidate)
            if (
                candidate.evaluation_status is EvaluationStatus.OK
                and candidate.guard_ok
                and candidate.hard_feasible
                and candidate.residual_norm_float < _RESIDUAL_ACCEPT_FLOAT
            ):
                selected.append(candidate)
                break
    return SearchBatchResult(
        candidates=tuple(selected),
        all_records=tuple(records),
        guard_feasible_ledger=tuple(selected),
        evaluation_count=telemetry.evaluation_count,
        evaluation_failure_count=telemetry.failure_count,
        failure_ratio=telemetry.failure_count / max(1, telemetry.evaluation_count),
        search_diagnostics={
            "integer_segment_displacements": {
                "displacement_count": plan.total_displacements,
                "excluded_displacement_count": plan.excluded_displacements,
                "admissible_count": len(selected),
                "all_displacements_covered": len(selected) + plan.excluded_displacements
                == plan.total_displacements,
            }
        },
    )
