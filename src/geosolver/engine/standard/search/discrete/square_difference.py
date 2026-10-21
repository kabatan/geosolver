"""Finite seeds implied by a nonzero difference of two integer squares.

For one real coordinate, two integer lengths whose squared polynomials differ
by a nonzero constant imply (m-n)(m+n)=N. Enumerating divisor pairs finds their
possible integer lengths without assuming a heuristic coordinate search box.
These are only search seeds: original guards, refinement and final verification
decide whether a seed becomes a public answer.
"""

import ast
import math
from dataclasses import dataclass, replace
from fractions import Fraction
from functools import lru_cache
from itertools import combinations

from mpmath import mp

from geosolver.runtime.deadline import check_deadline


@dataclass(frozen=True)
class _Point:
    x: tuple
    y: tuple


def _trim(values):
    values = list(values)
    while len(values) > 1 and values[-1] == 0:
        values.pop()
    return tuple(values)


def _add(left, right, sign=1):
    return _trim(
        (left[i] if i < len(left) else 0) + sign * (right[i] if i < len(right) else 0)
        for i in range(max(len(left), len(right)))
    )


def _mul(left, right):
    values = [Fraction(0)] * (len(left) + len(right) - 1)
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            values[i + j] += a * b
    result = _trim(values)
    if len(result) > 3:
        raise ValueError("polynomial degree exceeds two")
    return result


class _Compiler:
    def __init__(self, variable, constructions):
        self.variable = variable
        self.definitions = dict(constructions)
        self.active = set()
        self.cache = {}

    def expression(self, source):
        return self.evaluate(ast.parse(source, mode="eval").body, source)

    def evaluate(self, node, source):
        check_deadline()
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return (Fraction(ast.get_source_segment(source, node)),)
        if isinstance(node, ast.Name):
            if node.id == self.variable:
                return (Fraction(0), Fraction(1))
            if node.id in self.cache:
                return self.cache[node.id]
            if node.id not in self.definitions or node.id in self.active:
                raise ValueError("unsupported name")
            self.active.add(node.id)
            try:
                value = self.expression(self.definitions[node.id])
                self.cache[node.id] = value
                return value
            finally:
                self.active.remove(node.id)
        if isinstance(node, ast.Attribute) and node.attr in {"x", "y"}:
            point = self.evaluate(node.value, source)
            if isinstance(point, _Point):
                return getattr(point, node.attr)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
            value = self.evaluate(node.operand, source)
            return value if isinstance(node.op, ast.UAdd) else tuple(-x for x in value)
        if isinstance(node, ast.BinOp):
            left, right = self.evaluate(node.left, source), self.evaluate(node.right, source)
            if not isinstance(left, tuple) or not isinstance(right, tuple):
                raise ValueError("arithmetic on a geometry object")
            if isinstance(node.op, ast.Add | ast.Sub):
                return _add(left, right, -1 if isinstance(node.op, ast.Sub) else 1)
            if isinstance(node.op, ast.Mult):
                return _mul(left, right)
            if isinstance(node.op, ast.Div) and len(right) == 1 and right[0]:
                return tuple(x / right[0] for x in left)
            if isinstance(node.op, ast.Pow) and len(right) == 1 and right[0] in (0, 1, 2):
                power = int(right[0])
                if power == 0:
                    return (Fraction(1),)
                if power == 1:
                    return left
                return _mul(left, left)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            if node.func.id in {"Point", "Vector"} and len(node.args) == 2:
                return _Point(*(self.evaluate(arg, source) for arg in node.args))
            if node.func.id == "Midpoint" and len(node.args) == 2:
                a, b = (self.evaluate(arg, source) for arg in node.args)
                if isinstance(a, _Point) and isinstance(b, _Point):
                    return _Point(
                        tuple(x / 2 for x in _add(a.x, b.x)),
                        tuple(x / 2 for x in _add(a.y, b.y)),
                    )
        raise ValueError("unsupported rational geometry expression")

    def square(self, source):
        node = ast.parse(source, mode="eval").body
        if isinstance(node, ast.Name) and node.id in self.definitions:
            # Scalar aliases retain their exact expression source.
            return self.square(self.definitions[node.id])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            if node.func.id == "Distance" and len(node.args) == 2:
                a, b = (self.evaluate(arg, source) for arg in node.args)
                if isinstance(a, _Point) and isinstance(b, _Point):
                    dx, dy = _add(a.x, b.x, -1), _add(a.y, b.y, -1)
                    return _add(_mul(dx, dx), _mul(dy, dy))
            if node.func.id == "sqrt" and len(node.args) == 1:
                return self.evaluate(node.args[0], source)
            if node.func.id in {"abs", "Abs"} and len(node.args) == 1:
                value = self.evaluate(node.args[0], source)
                return _mul(value, value)
        value = self.evaluate(node, source)
        if not isinstance(value, tuple):
            raise ValueError("integer condition is not scalar")
        return _mul(value, value)


def _square_root_points(polynomial, square):
    coefficients = list(polynomial) + [Fraction(0)] * (3 - len(polynomial))
    c, b, a = coefficients
    c -= square
    if a == 0:
        if b == 0:
            # An identity leaves a continuum; it cannot justify finite search.
            return None if c == 0 else ()
        value = float(-c / b)
        return (value,) if math.isfinite(value) and (value != 0 or c == 0) else None
    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        return ()
    with mp.workdps(80):

        def number(value):
            return mp.mpf(value.numerator) / value.denominator

        root = mp.sqrt(number(discriminant))
        if discriminant == 0:
            points = (float(-number(b) / (2 * number(a))),) * 2
        else:
            # The naive +/- formula loses the smaller root when b^2 dwarfs
            # 4ac, even when both roots are representable as Python floats.
            q = -(number(b) + (root if b >= 0 else -root)) / 2
            values = (q / number(a), number(c) / q)
            if any(value != 0 and float(value) == 0 for value in values):
                return None
            points = tuple(sorted(map(float, values)))
        # A finite enumeration may replace global search only when every
        # distinct algebraic root has a representable float search seed.
        if not all(math.isfinite(value) for value in points):
            return None
        if discriminant and points[0] == points[1]:
            return None
        return points


def _root_boxes(polynomial, roots):
    """Certify disjoint rational intervals with exact polynomial sign tests."""
    centers = {point: Fraction(point) for point in roots}
    boxes = []
    coefficients = list(polynomial) + [Fraction(0)] * (3 - len(polynomial))
    c, b, a = coefficients
    for point, square in sorted(roots.items()):
        center = centers[point]
        radius = max(Fraction(1), abs(center)) / 8
        for other in centers.values():
            if other != center:
                radius = min(radius, abs(center - other) / 8)
        left, right = center - radius, center + radius
        if a == 0:
            if b == 0 or not left <= -(c - square) / b <= right:
                return None
        elif b * b - 4 * a * (c - square) == 0:
            if not left <= -b / (2 * a) <= right:
                return None
        else:
            vertex = -b / (2 * a)
            fleft = a * left * left + b * left + c - square
            fright = a * right * right + b * right + c - square
            # Opposite signs plus no vertex prove exactly one root here.
            if left <= vertex <= right or fleft * fright > 0:
                return None
        boxes.append(((str(left), str(right)),))
    return tuple(boxes)


@lru_cache(maxsize=256)
def _finite_roots(variable, constructions, integer_expressions):
    compiler = _Compiler(variable, constructions)
    polynomials = []
    for expression in integer_expressions:
        try:
            value = compiler.square(expression)
            if isinstance(value, tuple):
                polynomials.append(value)
        except (ValueError, TypeError, SyntaxError, ArithmeticError, RecursionError):
            continue
    for first, second in combinations(polynomials, 2):
        difference = _add(first, second, -1)
        if len(difference) != 1 or difference[0] == 0 or difference[0].denominator != 1:
            continue
        constant = int(difference[0])
        # Bound optional integer work; unsupported magnitudes fall back to the
        # existing solver instead of truncating a divisor enumeration.
        magnitude = abs(constant)
        if magnitude > 10**12:
            continue
        roots = {}
        for lower in range(1, math.isqrt(magnitude) + 1):
            if lower % 256 == 0:
                check_deadline()
            if magnitude % lower:
                continue
            upper = magnitude // lower
            if (lower + upper) % 2:
                continue
            greater, smaller = (upper + lower) // 2, (upper - lower) // 2
            first_integer = greater if constant > 0 else smaller
            square = first_integer * first_integer
            try:
                points = _square_root_points(first, square)
            except (OverflowError, ValueError):
                return None
            if points is None:
                return None
            for point in points:
                if point in roots and roots[point] != square:
                    return None
                roots[point] = square
            if len(roots) > 128:
                return None
        boxes = _root_boxes(first, roots)
        if boxes is None:
            return None
        return tuple((value,) for value in sorted(roots)), constant, boxes
    return None


def _finite_roots_for_bundle(bundle):
    if len(bundle.var_names) != 1:
        return None
    from geosolver.engine.standard.refinement.mpmath_refiner import build_integer_constraint_specs

    specs = build_integer_constraint_specs(bundle=bundle)
    if len(specs) < 2:
        return None
    return _finite_roots(
        bundle.var_names[0],
        tuple((item.name, item.expr) for item in bundle.spec.construction),
        tuple(spec.inner_expression for spec in specs),
    )


def finite_integer_square_roots(bundle):
    """Return every root implied by a supported integer-square pair, or None."""
    data = _finite_roots_for_bundle(bundle)
    return None if data is None else data[:2]


def scan_integer_square_branches(*, bundle, evaluator, config, constraint_scales=None):
    from geosolver.engine.standard.contracts.candidate_record import SearchBatchResult
    from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
    from geosolver.engine.standard.search.scipy_multistart_backend import (
        _RESIDUAL_ACCEPT_FLOAT,
        _build_candidate,
        _SearchTelemetry,
    )

    discovered = _finite_roots_for_bundle(bundle)
    if discovered is None:
        return None
    points, difference, boxes = discovered
    telemetry = _SearchTelemetry()
    records = tuple(
        replace(
            _build_candidate(
                evaluator=evaluator,
                config=config,
                # A heuristic search box is not a mathematical condition.
                # Explicit bounds remain part of the original hard checks.
                bounds=[(-math.inf, math.inf)],
                values=point,
                origin_seed=int((config.seed_values or (0,))[0]),
                family_code=90,
                origin_start_point_index=index,
                telemetry=telemetry,
                constraint_scales=constraint_scales,
            ),
            origin_backend="integer_square_difference",
            originating_branch_box=boxes[index],
        )
        for index, point in enumerate(points)
    )
    selected = tuple(
        r
        for r in records
        if r.evaluation_status is EvaluationStatus.OK
        and r.guard_ok
        and r.hard_feasible
        and r.residual_norm_float < _RESIDUAL_ACCEPT_FLOAT
    )
    return SearchBatchResult(
        candidates=selected,
        all_records=records,
        guard_feasible_ledger=selected,
        evaluation_count=telemetry.evaluation_count,
        failure_ratio=telemetry.failure_count / max(1, telemetry.evaluation_count),
        evaluation_failure_count=telemetry.failure_count,
        search_diagnostics={
            "integer_square_difference": {
                "difference": difference,
                "finite_seed_count": len(points),
                "admissible_seed_count": len(selected),
                "all_finite_seeds_admissible": len(selected) == len(points),
            }
        },
    )
