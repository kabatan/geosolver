"""Disposable barycentric signed-area quotient exact-witness proposal lane."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import itertools
import json
import math
from typing import Any, Mapping, Sequence

import sympy as sp


SCHEMA = "geotarget.barycentric-area-quotient-exact-witness/v1"
MAX_SOURCE_BYTES = 65_536
MAX_AST_NODES = 2_048
MAX_DENOMINATOR = 10_000
MAX_CF_CANDIDATES = 4
MAX_PROPOSALS = 64
MAX_ANCHORS = 12
MAX_ANCHOR_SIMPLEXES = 32
CF_TOLERANCE = 1.0e-8
FORBIDDEN_KEYS = frozenset(
    {"truth", "known_truth", "known_target", "expected_target", "score", "outcome"}
)


class WitnessRejected(ValueError):
    pass


@dataclass(frozen=True)
class Point:
    x: sp.Expr
    y: sp.Expr

    def __add__(self, other):
        if not isinstance(other, Point):
            return NotImplemented
        return Point(sp.expand(self.x + other.x), sp.expand(self.y + other.y))

    def __sub__(self, other):
        if not isinstance(other, Point):
            return NotImplemented
        return Point(sp.expand(self.x - other.x), sp.expand(self.y - other.y))

    def __mul__(self, scalar):
        scalar = sp.sympify(scalar)
        return Point(sp.expand(self.x * scalar), sp.expand(self.y * scalar))

    __rmul__ = __mul__

    def __truediv__(self, scalar):
        scalar = sp.sympify(scalar)
        if _zero(scalar):
            raise WitnessRejected("POINT_DIVISION_BY_ZERO")
        return Point(sp.cancel(self.x / scalar), sp.cancel(self.y / scalar))


@dataclass(frozen=True)
class PrejoinHold:
    untouched_baseline: object
    proposal_result: Mapping[str, Any]


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _zero(value: object) -> bool:
    expression = sp.simplify(sp.sympify(value))
    return expression == 0 or expression.is_zero is True


def _sign(value: object) -> int:
    expression = sp.simplify(sp.sympify(value))
    if _zero(expression):
        return 0
    if expression.is_positive is True or sp.ask(sp.Q.positive(expression)) is True:
        return 1
    if expression.is_negative is True or sp.ask(sp.Q.negative(expression)) is True:
        return -1
    raise WitnessRejected("EXACT_SIGN_UNDECIDED")


def _signed_double_area(first: Point, second: Point, third: Point) -> sp.Expr:
    return sp.expand(
        (second.x - first.x) * (third.y - first.y)
        - (second.y - first.y) * (third.x - first.x)
    )


def _area(points: Sequence[Point]) -> sp.Expr:
    if len(points) < 3 or not all(isinstance(point, Point) for point in points):
        raise WitnessRejected("AREA_ARGUMENTS_UNSUPPORTED")
    twice = sum(
        point.x * points[(index + 1) % len(points)].y
        - point.y * points[(index + 1) % len(points)].x
        for index, point in enumerate(points)
    )
    return sp.Abs(sp.expand(twice)) / 2


class ExactRuntime:
    """Small exact replay for the generated/proposal subset; never authority."""

    def __init__(self, document: Mapping[str, Any], raw_values: Mapping[str, Any]):
        names = document.get("variables", {}).get("names")
        if not isinstance(names, list) or set(names) != set(raw_values):
            raise WitnessRejected("RAW_ASSIGNMENT_VARIABLE_SET_MISMATCH")
        self.document = document
        self.context: dict[str, Any] = {
            **{name: sp.sympify(raw_values[name]) for name in names},
            "pi": sp.pi,
        }

    def eval(self, node: ast.AST):
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return sp.Rational(str(node.value))
            if node.value is None:
                return None
            raise WitnessRejected("LITERAL_UNSUPPORTED")
        if isinstance(node, ast.Name) and node.id in self.context:
            return self.context[node.id]
        if isinstance(node, ast.Attribute):
            value = self.eval(node.value)
            if isinstance(value, Point) and node.attr in {"x", "y"}:
                return getattr(value, node.attr)
            raise WitnessRejected("ATTRIBUTE_UNSUPPORTED")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Not)):
            value = self.eval(node.operand)
            if isinstance(node.op, ast.Not):
                return not bool(value)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp):
            left, right = self.eval(node.left), self.eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if _zero(right):
                    raise WitnessRejected("DIVISION_BY_ZERO")
                return left / right
            if isinstance(node.op, ast.Pow):
                exponent = sp.sympify(right)
                if exponent.is_Integer is not True or abs(int(exponent)) > 32:
                    raise WitnessRejected("POWER_UNSUPPORTED")
                return left ** int(exponent)
            raise WitnessRejected("BINARY_OPERATOR_UNSUPPORTED")
        if isinstance(node, (ast.Tuple, ast.List)):
            return tuple(self.eval(item) for item in node.elts)
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            values = [bool(self.eval(item)) for item in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise WitnessRejected("CHAINED_COMPARISON_UNSUPPORTED")
            difference = sp.sympify(self.eval(node.left)) - sp.sympify(
                self.eval(node.comparators[0])
            )
            sign = _sign(difference)
            operation = node.ops[0]
            return (
                (isinstance(operation, ast.Eq) and sign == 0)
                or (isinstance(operation, ast.NotEq) and sign != 0)
                or (isinstance(operation, ast.Gt) and sign > 0)
                or (isinstance(operation, ast.GtE) and sign >= 0)
                or (isinstance(operation, ast.Lt) and sign < 0)
                or (isinstance(operation, ast.LtE) and sign <= 0)
            )
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            raise WitnessRejected("CALL_UNSUPPORTED")
        name = node.func.id
        args = [self.eval(item) for item in node.args]
        keywords = {item.arg: self.eval(item.value) for item in node.keywords if item.arg}
        if name == "Point" and len(args) == 2:
            return Point(sp.sympify(args[0]), sp.sympify(args[1]))
        if name in {"Midpoint", "MidPoint"} and len(args) == 2:
            return (args[0] + args[1]) / 2
        if name == "PointOnSegment" and len(args) == 3:
            return args[0] + (args[1] - args[0]) * args[2]
        if name == "Centroid" and args:
            points = args[0] if len(args) == 1 and isinstance(args[0], tuple) else args
            return sum(points[1:], points[0]) / len(points)
        if name == "Area":
            return _area(args)
        if name == "Distance" and len(args) == 2 and all(isinstance(item, Point) for item in args):
            return sp.sqrt((args[0].x - args[1].x) ** 2 + (args[0].y - args[1].y) ** 2)
        if name == "abs" and len(args) == 1:
            return sp.Abs(args[0])
        if name == "sqrt" and len(args) == 1 and _sign(args[0]) >= 0:
            return sp.sqrt(args[0])
        if name in {"AssumeEq", "AssumeNe", "AssumeGt", "AssumeGe", "AssumeLt", "AssumeLe"} and len(args) == 2:
            sign = _sign(sp.sympify(args[0]) - sp.sympify(args[1]))
            return {
                "AssumeEq": sign == 0,
                "AssumeNe": sign != 0,
                "AssumeGt": sign > 0,
                "AssumeGe": sign >= 0,
                "AssumeLt": sign < 0,
                "AssumeLe": sign <= 0,
            }[name]
        if name == "Bound" and len(args) == 2 and len(args[1]) == 2:
            lower, upper = args[1]
            inclusive = keywords.get("inclusive", True)
            if not isinstance(inclusive, bool):
                raise WitnessRejected("BOUND_INCLUSIVE_MALFORMED")
            lower_ok = True if lower is None else _sign(args[0] - lower) >= (0 if inclusive else 1)
            upper_ok = True if upper is None else _sign(upper - args[0]) >= (0 if inclusive else 1)
            return lower_ok and upper_ok
        raise WitnessRejected("DSL_PRIMITIVE_UNSUPPORTED")

    def build(self) -> None:
        for item in self.document.get("construction", ()):
            self.context[str(item["name"])] = self.eval(
                ast.parse(str(item["expr"]), mode="eval").body
            )

    def verify(self) -> tuple[bool, sp.Expr | None]:
        try:
            self.build()
            for item in self.document.get("constraints", ()):
                left = self.eval(ast.parse(str(item["def"]), mode="eval").body)
                right = self.eval(ast.parse(str(item.get("value", 0)), mode="eval").body)
                if not _zero(sp.sympify(left) - sp.sympify(right)):
                    return False, None
            names = self.document.get("variables", {}).get("names", [])
            bounds = self.document.get("bounds")
            if bounds is not None:
                for name, pair in zip(names, bounds, strict=True):
                    if _sign(self.context[name] - sp.Rational(str(pair[0]))) < 0:
                        return False, None
                    if _sign(sp.Rational(str(pair[1])) - self.context[name]) < 0:
                        return False, None
            for guard in self.document.get("guards", ()):
                if not bool(self.eval(ast.parse(str(guard), mode="eval").body)):
                    return False, None
            target = self.eval(ast.parse(str(self.document["answer"]), mode="eval").body)
            return True, sp.simplify(target)
        except (WitnessRejected, SyntaxError, TypeError, ValueError, KeyError):
            return False, None


def _source_contract(document: Mapping[str, Any], endpoint: Sequence[float]) -> tuple[str, ...]:
    if not isinstance(document, Mapping):
        raise WitnessRejected("SOURCE_NOT_MAPPING")
    if any(str(key).lower() in FORBIDDEN_KEYS for key in document):
        raise WitnessRejected("FORBIDDEN_TRUTH_OR_OUTCOME_INPUT")
    if document.get("task") != "solve" or document.get("post_process", "") not in (None, ""):
        raise WitnessRejected("TASK_OR_POST_PROCESS_UNSUPPORTED")
    projection = {
        key: document.get(key)
        for key in (
            "task",
            "variables",
            "bounds",
            "construction",
            "constraints",
            "guards",
            "answer",
            "post_process",
        )
    }
    if len(_canonical_bytes(projection)) > MAX_SOURCE_BYTES:
        raise WitnessRejected("SOURCE_BYTE_CAP")
    _audit_source_ast(projection)
    names = document.get("variables", {}).get("names")
    if (
        not isinstance(names, list)
        or len(names) != 2
        or len(set(names)) != 2
        or len(endpoint) != 2
        or not all(isinstance(name, str) and name for name in names)
        or not all(math.isfinite(float(value)) for value in endpoint)
    ):
        raise WitnessRejected("DIRECT_TWO_COORDINATE_ENDPOINT_REQUIRED")
    return tuple(names)


def _small_integer(node: ast.AST) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(
        node.value, bool
    ):
        return int(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _small_integer(node.operand)
        if value is not None:
            return value if isinstance(node.op, ast.UAdd) else -value
    return None


def _audit_source_ast(document: Mapping[str, Any]) -> None:
    expressions = []
    for item in document.get("construction") or ():
        if not isinstance(item, Mapping) or not isinstance(item.get("expr"), str):
            raise WitnessRejected("CONSTRUCTION_MALFORMED")
        expressions.append(item["expr"])
    for item in document.get("constraints") or ():
        if not isinstance(item, Mapping) or not isinstance(item.get("def"), str):
            raise WitnessRejected("CONSTRAINT_MALFORMED")
        expressions.extend((item["def"], str(item.get("value", 0))))
    guards = document.get("guards") or ()
    if not isinstance(guards, Sequence) or isinstance(guards, (str, bytes)):
        raise WitnessRejected("GUARDS_MALFORMED")
    expressions.extend(guards)
    if not isinstance(document.get("answer"), str):
        raise WitnessRejected("RAW_TARGET_NOT_STRING")
    expressions.append(document["answer"])
    total_nodes = 0
    for text in expressions:
        if not isinstance(text, str) or len(text) > 8_192:
            raise WitnessRejected("EXPRESSION_CHARACTER_CAP")
        try:
            root = ast.parse(text, mode="eval")
        except (SyntaxError, ValueError) as error:
            raise WitnessRejected("EXPRESSION_SYNTAX_REJECTED") from error
        nodes = list(ast.walk(root))
        total_nodes += len(nodes)
        if total_nodes > MAX_AST_NODES:
            raise WitnessRejected("SOURCE_AST_NODE_CAP")
        for node in nodes:
            if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(
                node.value, bool
            ):
                if abs(int(node.value)).bit_length() > 256:
                    raise WitnessRejected("INTEGER_LITERAL_BIT_CAP")
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
                exponent = _small_integer(node.right)
                if exponent is None or abs(exponent) > 32:
                    raise WitnessRejected("POWER_CAP_OR_NONLITERAL_EXPONENT")


def _area_point_names(document: Mapping[str, Any]) -> set[str]:
    answer = document.get("answer")
    if not isinstance(answer, str):
        raise WitnessRejected("RAW_TARGET_NOT_STRING")
    root = ast.parse(answer, mode="eval")
    if sum(1 for _ in ast.walk(root)) > MAX_AST_NODES:
        raise WitnessRejected("TARGET_AST_CAP")
    result = set()
    for node in ast.walk(root):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Area"
            and len(node.args) >= 3
        ):
            result.update(item.id for item in node.args if isinstance(item, ast.Name))
    if not result:
        raise WitnessRejected("RAW_TARGET_HAS_NO_AREA_SITE")
    return result


def _direct_free_point(
    document: Mapping[str, Any], names: tuple[str, ...], area_names: set[str]
) -> tuple[str, tuple[str, str]]:
    matches = []
    for item in document.get("construction", ()):
        name = item.get("name") if isinstance(item, Mapping) else None
        if not isinstance(name, str) or name not in area_names:
            continue
        try:
            node = ast.parse(str(item["expr"]), mode="eval").body
        except (SyntaxError, KeyError):
            continue
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Point"
            and len(node.args) == 2
            and all(isinstance(argument, ast.Name) for argument in node.args)
        ):
            coordinates = tuple(argument.id for argument in node.args)
            if set(coordinates) == set(names):
                matches.append((name, coordinates))
    if len(matches) != 1:
        raise WitnessRejected("EXACTLY_ONE_DIRECT_FREE_AREA_POINT_REQUIRED")
    return matches[0]


def _exact_anchor_context(
    document: Mapping[str, Any], free_name: str
) -> dict[str, Point]:
    runtime = ExactRuntime(
        {**document, "variables": {"names": []}},
        {},
    )
    anchors: dict[str, Point] = {}
    for item in document.get("construction", ()):
        name = str(item.get("name"))
        if name == free_name:
            continue
        try:
            value = runtime.eval(ast.parse(str(item["expr"]), mode="eval").body)
        except (WitnessRejected, SyntaxError, KeyError, TypeError, ValueError):
            continue
        runtime.context[name] = value
        if isinstance(value, Point) and not value.x.free_symbols and not value.y.free_symbols:
            anchors[name] = value
    return anchors


def _anchor_simplices(
    anchors: Mapping[str, Point], area_names: set[str]
) -> tuple[tuple[Point, Point, Point], ...]:
    if len(anchors) > MAX_ANCHORS:
        raise WitnessRejected("ANCHOR_CAP")
    ordered = sorted(
        anchors,
        key=lambda name: (
            name not in area_names,
            sp.srepr(anchors[name].x),
            sp.srepr(anchors[name].y),
        ),
    )
    result = []
    for names in itertools.combinations(ordered, 3):
        points = tuple(anchors[name] for name in names)
        if _zero(_signed_double_area(*points)):
            continue
        result.append(points)
        if len(result) > MAX_ANCHOR_SIMPLEXES:
            raise WitnessRejected("ANCHOR_SIMPLEX_CAP")
    if not result:
        raise WitnessRejected("NONDEGENERATE_EXACT_ANCHOR_SIMPLEX_NOT_FOUND")
    return tuple(result)


def _numeric_point(document: Mapping[str, Any], endpoint: Sequence[float], free_name: str) -> Point:
    names = document["variables"]["names"]
    runtime = ExactRuntime(document, dict(zip(names, map(sp.Float, endpoint), strict=True)))
    runtime.build()
    point = runtime.context.get(free_name)
    if not isinstance(point, Point):
        raise WitnessRejected("FREE_POINT_NUMERIC_REPLAY_FAILED")
    return point


def _continued_fraction_candidates(value: float) -> tuple[Fraction, ...]:
    if not math.isfinite(value):
        raise WitnessRejected("BARYCENTRIC_QUOTIENT_NOT_FINITE")
    exact = Fraction.from_float(value)
    numerator, denominator = exact.numerator, exact.denominator
    terms = []
    while denominator:
        quotient, remainder = divmod(numerator, denominator)
        terms.append(quotient)
        numerator, denominator = denominator, remainder
    convergents: list[Fraction] = []
    p0, p1, q0, q1 = 0, 1, 1, 0
    for term in terms:
        p0, p1 = p1, term * p1 + p0
        q0, q1 = q1, term * q1 + q0
        if q1 > MAX_DENOMINATOR:
            break
        candidate = Fraction(p1, q1)
        if abs(float(candidate) - value) <= CF_TOLERANCE * max(1.0, abs(value)):
            convergents.append(candidate)
    limited = exact.limit_denominator(MAX_DENOMINATOR)
    if abs(float(limited) - value) <= CF_TOLERANCE * max(1.0, abs(value)):
        convergents.append(limited)
    unique = sorted(set(convergents), key=lambda item: (abs(float(item) - value), item.denominator))
    if not unique:
        raise WitnessRejected("NO_BOUNDED_CF_QUOTIENT")
    return tuple(unique[:MAX_CF_CANDIDATES])


def _exact_value(value: sp.Expr) -> dict[str, Any]:
    value = sp.simplify(value)
    if value.is_Rational is True:
        rational = sp.Rational(value)
        return {"kind": "Rational", "numerator": int(rational.p), "denominator": int(rational.q)}
    return {"kind": "ExactExpression", "text": str(value), "srepr": sp.srepr(value)}


def propose(document: Mapping[str, Any], endpoint: Sequence[float]) -> dict[str, Any]:
    try:
        names = _source_contract(document, endpoint)
        area_names = _area_point_names(document)
        free_name, coordinate_order = _direct_free_point(document, names, area_names)
        anchors = _exact_anchor_context(document, free_name)
        free = _numeric_point(document, endpoint, free_name)
        proposals = []
        for first, second, third in _anchor_simplices(anchors, area_names):
            denominator = float(sp.N(_signed_double_area(first, second, third), 30))
            if not math.isfinite(denominator) or abs(denominator) <= 1.0e-14:
                continue
            alpha_value = float(sp.N(_signed_double_area(free, second, third), 30)) / denominator
            beta_value = float(sp.N(_signed_double_area(first, free, third), 30)) / denominator
            alpha_candidates = _continued_fraction_candidates(alpha_value)
            beta_candidates = _continued_fraction_candidates(beta_value)
            for alpha, beta in itertools.product(alpha_candidates, beta_candidates):
                gamma = Fraction(1) - alpha - beta
                exact_point = (
                    first * sp.Rational(alpha.numerator, alpha.denominator)
                    + second * sp.Rational(beta.numerator, beta.denominator)
                    + third * sp.Rational(gamma.numerator, gamma.denominator)
                )
                raw = {
                    coordinate_order[0]: exact_point.x,
                    coordinate_order[1]: exact_point.y,
                }
                accepted, target = ExactRuntime(document, raw).verify()
                if not accepted or target is None:
                    continue
                proposal = {
                    "raw_coordinate_assignment": {
                        name: _exact_value(raw[name]) for name in names
                    },
                    "free_point": {
                        "x": _exact_value(exact_point.x),
                        "y": _exact_value(exact_point.y),
                    },
                    "barycentric_weights": [
                        _exact_value(sp.Rational(value.numerator, value.denominator))
                        for value in (alpha, beta, gamma)
                    ],
                    "raw_target_exact_proposal": _exact_value(target),
                    "untouched_source_raw_target_replay_pass": True,
                    "authority_pass": False,
                    "target_release": False,
                }
                proposals.append(proposal)
                if len(proposals) > MAX_PROPOSALS:
                    raise WitnessRejected("PROPOSAL_CAP")
        unique = {_sha256(proposal): proposal for proposal in proposals}
        proposals = [unique[key] for key in sorted(unique)]
        if not proposals:
            raise WitnessRejected("NO_CF_PROPOSAL_PASSED_UNTOUCHED_REPLAY")
        for ordinal, proposal in enumerate(proposals):
            proposal["proposal_ordinal"] = ordinal
            proposal["proposal_sha256"] = _sha256(proposal)
        barycentric_signature = _sha256(
            [proposal["barycentric_weights"] for proposal in proposals]
        )
        return {
            "schema_version": SCHEMA,
            "status": "PROPOSAL_READY_HOLD",
            "proposal_count": len(proposals),
            "barycentric_signature_sha256": barycentric_signature,
            "proposals": proposals,
            "routing_used_raw_target_structure": True,
            "routing_used_raw_target_numeric_value": False,
            "routing_used_case_id_family_truth_outcome": False,
            "untouched_source_raw_target_replay_required": True,
            "canonical_external_authority_still_required": True,
            "target_set_completeness_claim": False,
            "authority_pass": False,
            "target_release": False,
            "baseline_fallback_required": True,
        }
    except Exception as error:
        return {
            "schema_version": SCHEMA,
            "status": "NOT_APPLICABLE_BASELINE_FALLBACK",
            "reason": str(error) if isinstance(error, WitnessRejected) else f"UNEXPECTED:{type(error).__name__}",
            "proposal_count": 0,
            "proposals": [],
            "routing_used_case_id_family_truth_outcome": False,
            "authority_pass": False,
            "target_release": False,
            "baseline_fallback_required": True,
        }


def prejoin_or_baseline(
    document: Mapping[str, Any], endpoint: Sequence[float], untouched_baseline: object
) -> object:
    try:
        result = propose(document, endpoint)
    except Exception:
        return untouched_baseline
    if result.get("status") != "PROPOSAL_READY_HOLD":
        return untouched_baseline
    return PrejoinHold(untouched_baseline, result)


__all__ = [
    "ExactRuntime",
    "Point",
    "PrejoinHold",
    "WitnessRejected",
    "prejoin_or_baseline",
    "propose",
]
