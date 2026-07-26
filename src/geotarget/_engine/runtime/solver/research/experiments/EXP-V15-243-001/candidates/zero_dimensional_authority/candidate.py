"""Fail-closed exact authority lane for zero-variable v15 sources.

The empty tuple is the unique numerical configuration of a source whose
``variables.names`` list is empty.  There is nothing to optimize, but the
configuration is replayed through the unchanged source at high precision.
The target authority itself is *not* numerical recognition: the unchanged
source construction and target AST are evaluated exactly, and a primitive
square-free minimal polynomial plus rational isolator are derived directly.
The numerical 512/768/1024-bit lanes are only an implementation-parity audit.

This module deliberately has no access to a problem id, family, truth, known
target count, or benchmark outcome.  Eligibility depends only on the source
variable dimension and the supplied endpoint dimension.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
from typing import Callable, Mapping, Sequence


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
AUTHORITY_ADAPTER = (
    ROOT
    / "research/experiments/EXP-REAL61-008/"
    "hp_target_first_fallback_integration_v1/adapter.py"
)
SCHEMA = "geotarget.exp-v15-243-zero-dimensional-authority/v1"
COMPOSITION_SCHEMA = "geotarget.exp008-target-first-fallback-composition/v1"

AuthorityBackend = Callable[..., Mapping[str, object]]

# Operations whose scalar/coordinate outputs are algebraic whenever every
# input coordinate is algebraic.  Unknown operations fail closed.  Angle,
# inverse-trigonometric and arbitrary transcendental operations are
# intentionally absent.
ALGEBRAIC_CALLS = frozenset(
    {
        "Abs",
        "Area",
        "Center",
        "Circle",
        "CircleFromCenterAndPoint",
        "CircleThrough",
        "Circumcenter",
        "Circumcircle",
        "Distance",
        "Foot",
        "Homothety",
        "Incenter",
        "Intersect",
        "Intersection",
        "Line",
        "Midpoint",
        "Orthocenter",
        "ParallelLine",
        "PerpendicularFoot",
        "PerpendicularLine",
        "Point",
        "PointOnLine",
        "PointOnSegment",
        "Projection",
        "Radius",
        "Reflect",
        "Reflection",
        "Segment",
        "abs",
        "max",
        "min",
        "sqrt",
    }
)


class _ExactNumberTransformer(ast.NodeTransformer):
    """Turn every source numeric literal into an exact SymPy Rational."""

    def __init__(self, source: str) -> None:
        self.source = source

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if isinstance(node.value, bool) or not isinstance(
            node.value, (int, float)
        ):
            return node
        literal = ast.get_source_segment(self.source, node)
        if not isinstance(literal, str):
            return node
        replacement = ast.Call(
            func=ast.Name(id="ExactRational", ctx=ast.Load()),
            args=[ast.Constant(value=literal)],
            keywords=[],
        )
        return ast.copy_location(replacement, node)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def endpoint_float64_sha256(endpoint: Sequence[float]) -> str:
    payload = struct.pack(">I", len(endpoint)) + b"".join(
        struct.pack(">d", float(value)) for value in endpoint
    )
    return _sha256(payload)


def _load_authority_backend() -> AuthorityBackend:
    name = "geotarget_exp_v15_243_zero_dimensional_authority_backend"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached.build_target_authority_with_fallback
    specification = importlib.util.spec_from_file_location(
        name, AUTHORITY_ADAPTER
    )
    if specification is None or specification.loader is None:
        raise ImportError(AUTHORITY_ADAPTER)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module.build_target_authority_with_fallback


def _fail(
    *,
    status: str,
    source_sha256: str,
    endpoint_sha256: str,
    reasons: Sequence[str],
    eligible: bool,
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA,
        "status": status,
        "eligible": eligible,
        "authority_pass": False,
        "source_sha256": source_sha256,
        "endpoint_float64_sha256": endpoint_sha256,
        "exact_target_descriptor": None,
        "exact_authority_kind": None,
        "numeric_pslq_descriptor_used": False,
        "failure_reasons": list(reasons),
        "routing_audit": {
            "case_id_read": False,
            "family_read": False,
            "truth_read": False,
            "known_target_count_read": False,
            "target_value_used_for_routing": False,
            "only_source_dimension_and_endpoint_dimension_used": True,
        },
    }


def _source_dimension(source_payload: bytes) -> tuple[int | None, str | None]:
    try:
        document = json.loads(source_payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "SOURCE_NOT_JSON"
    if not isinstance(document, Mapping) or document.get("task") != "solve":
        return None, "SOURCE_NOT_SOLVE_PROBLEM"
    variables = document.get("variables")
    names = variables.get("names") if isinstance(variables, Mapping) else None
    if not isinstance(names, list) or not all(
        isinstance(name, str) and name for name in names
    ):
        return None, "SOURCE_VARIABLE_NAMES_MALFORMED"
    return len(names), None


def _rational_constant(node: ast.AST) -> Fraction | None:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(
            node.value, (int, float)
        ):
            return None
        return Fraction(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(
        node.op, (ast.UAdd, ast.USub)
    ):
        value = _rational_constant(node.operand)
        if value is None:
            return None
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left = _rational_constant(node.left)
        right = _rational_constant(node.right)
        if left is None or right is None:
            return None
        try:
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
        except (ZeroDivisionError, ValueError, OverflowError):
            return None
    return None


def _pi_multiple(node: ast.AST) -> Fraction | None:
    if isinstance(node, ast.Name) and node.id == "pi":
        return Fraction(1)
    if isinstance(node, ast.UnaryOp) and isinstance(
        node.op, (ast.UAdd, ast.USub)
    ):
        value = _pi_multiple(node.operand)
        if value is None:
            return None
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left_pi = _pi_multiple(node.left)
        right_pi = _pi_multiple(node.right)
        left_q = _rational_constant(node.left)
        right_q = _rational_constant(node.right)
        try:
            if isinstance(node.op, ast.Add):
                if left_pi is not None and right_pi is not None:
                    return left_pi + right_pi
            elif isinstance(node.op, ast.Sub):
                if left_pi is not None and right_pi is not None:
                    return left_pi - right_pi
            elif isinstance(node.op, ast.Mult):
                if left_pi is not None and right_q is not None:
                    return left_pi * right_q
                if right_pi is not None and left_q is not None:
                    return right_pi * left_q
            elif isinstance(node.op, ast.Div):
                if left_pi is not None and right_q is not None:
                    return left_pi / right_q
        except ZeroDivisionError:
            return None
    return None


def _algebraic_expression(node: ast.AST, algebraic_names: set[str]) -> bool:
    rational = _rational_constant(node)
    if rational is not None:
        return True
    pi_multiple = _pi_multiple(node)
    if pi_multiple == 0:
        return True
    if isinstance(node, ast.Name):
        return node.id in algebraic_names
    if isinstance(node, ast.Attribute):
        return _algebraic_expression(node.value, algebraic_names)
    if isinstance(node, ast.UnaryOp) and isinstance(
        node.op, (ast.UAdd, ast.USub)
    ):
        return _algebraic_expression(node.operand, algebraic_names)
    if isinstance(node, ast.BinOp):
        if not _algebraic_expression(node.left, algebraic_names):
            return False
        if isinstance(node.op, ast.Pow):
            exponent = _rational_constant(node.right)
            return exponent is not None
        return isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)) and (
            _algebraic_expression(node.right, algebraic_names)
        )
    if isinstance(node, (ast.List, ast.Tuple)):
        return all(
            _algebraic_expression(item, algebraic_names) for item in node.elts
        )
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return False
    operation = node.func.id
    if operation in {"sin", "cos"}:
        rational_argument = (
            _rational_constant(node.args[0]) if len(node.args) == 1 else None
        )
        return (
            len(node.args) == 1
            and not node.keywords
            and (
                _pi_multiple(node.args[0]) is not None
                or rational_argument == 0
            )
        )
    if operation == "PointOnCircle":
        return (
            len(node.args) == 2
            and not node.keywords
            and _algebraic_expression(node.args[0], algebraic_names)
            and _rational_constant(node.args[1]) is not None
        )
    if operation == "Rotate":
        return (
            2 <= len(node.args) <= 3
            and _algebraic_expression(node.args[0], algebraic_names)
            and _pi_multiple(node.args[1]) is not None
            and all(
                _algebraic_expression(argument, algebraic_names)
                for argument in node.args[2:]
            )
            and all(
                keyword.arg == "center"
                and _algebraic_expression(keyword.value, algebraic_names)
                for keyword in node.keywords
            )
        )
    if operation not in ALGEBRAIC_CALLS:
        return False
    return all(
        _algebraic_expression(argument, algebraic_names)
        for argument in node.args
    ) and all(
        keyword.arg is not None
        and _algebraic_expression(keyword.value, algebraic_names)
        for keyword in node.keywords
    )


def _target_is_certified_algebraic(source_payload: bytes) -> bool:
    """Conservatively certify algebraicity from source AST dependencies."""

    try:
        document = json.loads(source_payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(document, Mapping):
        return False
    construction = document.get("construction")
    answer = document.get("answer")
    if not isinstance(construction, list) or not isinstance(answer, str):
        return False
    algebraic_names: set[str] = set()
    for row in construction:
        if not isinstance(row, Mapping):
            continue
        name = row.get("name")
        expression = row.get("expr")
        if not isinstance(name, str) or not isinstance(expression, str):
            continue
        algebraic_names.discard(name)
        try:
            node = ast.parse(expression, mode="eval").body
        except SyntaxError:
            continue
        if _algebraic_expression(node, algebraic_names):
            algebraic_names.add(name)
    try:
        target_node = ast.parse(answer, mode="eval").body
    except SyntaxError:
        return False
    return _algebraic_expression(target_node, algebraic_names)


def _exact_context() -> tuple[dict[str, object], object, object]:
    geosolver_source = ROOT.parent / "geosolver/src"
    if str(geosolver_source) not in sys.path:
        sys.path.insert(0, str(geosolver_source))
    import sympy
    from geosolver._internal.autosolve.context import _get_geometry_context
    from geosolver.ir.compiler import ALLOWED_AST_NODES, validate_expr_safety

    context = dict(_get_geometry_context())
    context.update(
        {
            "ExactRational": sympy.Rational,
            "pi": sympy.pi,
            "sqrt": sympy.sqrt,
            "sin": sympy.sin,
            "cos": sympy.cos,
            "acos": sympy.acos,
            "abs": sympy.Abs,
            "min": sympy.Min,
            "max": sympy.Max,
        }
    )
    # Converting an exact object back to float/int would invalidate the proof.
    context.pop("float", None)
    context.pop("int", None)
    return context, (ALLOWED_AST_NODES, validate_expr_safety), sympy


def _exact_eval(
    expression: str,
    context: Mapping[str, object],
    validation: object,
) -> object:
    allowed_nodes, validate_expr_safety = validation
    validate_expr_safety(expression, where="zero-dimensional exact certificate")
    tree = ast.parse(expression, mode="eval")
    if any(type(node) not in allowed_nodes for node in ast.walk(tree)):
        raise ValueError("unsupported AST in exact certificate")
    transformed = _ExactNumberTransformer(expression).visit(tree)
    ast.fix_missing_locations(transformed)
    code = compile(transformed, "<zero-dimensional-exact>", "eval")
    return eval(code, {"__builtins__": {}}, dict(context))


def _exact_zero(value: object, sympy: object) -> bool:
    simplified = sympy.simplify(value)
    return bool(simplified == 0 or simplified.is_zero is True)


def _exact_relation(
    operation: str, left: object, right: object, sympy: object
) -> bool:
    difference = sympy.simplify(left - right)
    if operation == "AssumeEq":
        return _exact_zero(difference, sympy)
    if operation == "AssumeNe":
        return bool(difference.is_zero is False)
    relations = {
        "AssumeLt": sympy.StrictLessThan,
        "AssumeLe": sympy.LessThan,
        "AssumeGt": sympy.StrictGreaterThan,
        "AssumeGe": sympy.GreaterThan,
    }
    relation = relations[operation](left, right)
    return bool(relation is sympy.true)


def _exact_eval_source_node(
    source: str,
    node: ast.AST,
    context: Mapping[str, object],
    validation: object,
) -> object:
    """Evaluate an AST operand while preserving its original numeric lexemes.

    ``ast.unparse`` serializes the already-rounded Python value of a numeric
    constant.  It therefore turns, for example, ``1e-1000`` into ``0.0`` and
    ``1e1000`` into ``1e1000``'s in-memory infinity.  Exact certificates must
    instead reparse the original source segment so `_ExactNumberTransformer`
    sees the spelling authored in the DSL.
    """

    segment = ast.get_source_segment(source, node)
    if not isinstance(segment, str) or not segment.strip():
        raise ValueError("source segment unavailable for exact certificate")
    return _exact_eval(segment, context, validation)


def _exact_truth_value(value: object, sympy: object) -> bool | None:
    if value is True or value is sympy.true:
        return True
    if value is False or value is sympy.false:
        return False
    return None


def _exact_guard_node(
    expression: str,
    node: ast.AST,
    context: Mapping[str, object],
    validation: object,
    sympy: object,
) -> bool | None:
    """Evaluate the supported guard Boolean IR exactly, or return unknown."""

    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
        values = [
            _exact_guard_node(expression, child, context, validation, sympy)
            for child in node.values
        ]
        if any(value is None for value in values):
            return None
        concrete = [bool(value) for value in values]
        return all(concrete) if isinstance(node.op, ast.And) else any(concrete)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        value = _exact_guard_node(
            expression, node.operand, context, validation, sympy
        )
        return None if value is None else not value
    if isinstance(node, ast.Compare):
        try:
            value = _exact_eval_source_node(
                expression, node, context, validation
            )
        except Exception:
            return None
        return _exact_truth_value(value, sympy)
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return None

    operation = node.func.id
    if operation in {
        "AssumeEq",
        "AssumeNe",
        "AssumeLt",
        "AssumeLe",
        "AssumeGt",
        "AssumeGe",
    }:
        if len(node.args) < 2:
            return None
        try:
            left = _exact_eval_source_node(
                expression, node.args[0], context, validation
            )
            right = _exact_eval_source_node(
                expression, node.args[1], context, validation
            )
            return _exact_relation(operation, left, right, sympy)
        except Exception:
            return None
    if operation == "Assume":
        if not node.args:
            return None
        return _exact_guard_node(
            expression, node.args[0], context, validation, sympy
        )
    if operation in {"And", "Or"}:
        if not node.args or node.keywords:
            return None
        values = [
            _exact_guard_node(expression, child, context, validation, sympy)
            for child in node.args
        ]
        if any(value is None for value in values):
            return None
        concrete = [bool(value) for value in values]
        return all(concrete) if operation == "And" else any(concrete)
    if operation == "Not":
        if len(node.args) != 1 or node.keywords:
            return None
        value = _exact_guard_node(
            expression, node.args[0], context, validation, sympy
        )
        return None if value is None else not value
    if operation != "Bound" or len(node.args) < 2:
        return None

    try:
        value = _exact_eval_source_node(
            expression, node.args[0], context, validation
        )
        bounds_node = node.args[1]
        if not isinstance(bounds_node, (ast.Tuple, ast.List)) or len(
            bounds_node.elts
        ) != 2:
            return None
        lower = _exact_eval_source_node(
            expression, bounds_node.elts[0], context, validation
        )
        upper = _exact_eval_source_node(
            expression, bounds_node.elts[1], context, validation
        )
    except Exception:
        return None
    inclusive = True
    for keyword in node.keywords:
        if keyword.arg == "inclusive" and isinstance(
            keyword.value, ast.Constant
        ) and isinstance(keyword.value.value, bool):
            inclusive = keyword.value.value
        elif keyword.arg not in {"message", "rel_floor", "abs_floor"}:
            return None
    if not bool(sympy.StrictLessThan(lower, upper) is sympy.true):
        return False
    lower_relation = (
        sympy.GreaterThan(value, lower)
        if inclusive
        else sympy.StrictGreaterThan(value, lower)
    )
    upper_relation = (
        sympy.LessThan(value, upper)
        if inclusive
        else sympy.StrictLessThan(value, upper)
    )
    return bool(lower_relation is sympy.true and upper_relation is sympy.true)


def _exact_guard(
    expression: str,
    context: Mapping[str, object],
    validation: object,
    sympy: object,
) -> bool:
    tree = ast.parse(expression, mode="eval")
    return _exact_guard_node(
        expression, tree.body, context, validation, sympy
    ) is True


def _exact_source_conditions_certificate(
    source_payload: bytes,
) -> tuple[str, ...]:
    """Prove every zero-dimensional source equation and guard exactly."""

    try:
        document = json.loads(
            source_payload,
            parse_float=lambda text: Decimal(text),
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ("EXACT_SOURCE_JSON_UNAVAILABLE",)
    if not isinstance(document, Mapping):
        return ("EXACT_SOURCE_DOCUMENT_MALFORMED",)
    constraints = document.get("constraints")
    guards = document.get("guards")
    construction = document.get("construction")
    if not isinstance(constraints, list) or not isinstance(guards, list):
        return ("EXACT_SOURCE_CONDITIONS_MALFORMED",)
    if not constraints and not guards:
        return ()
    if not isinstance(construction, list):
        return ("EXACT_SOURCE_CONSTRUCTION_MALFORMED",)
    try:
        context, validation, sympy = _exact_context()
        for row in construction:
            if not isinstance(row, Mapping):
                return ("EXACT_CONSTRUCTION_UNPROVED",)
            name = row.get("name")
            expression = row.get("expr")
            if not isinstance(name, str) or not isinstance(expression, str):
                return ("EXACT_CONSTRUCTION_UNPROVED",)
            context[name] = _exact_eval(expression, context, validation)
        for constraint in constraints:
            if not isinstance(constraint, Mapping):
                return ("EXACT_CONSTRAINT_UNPROVED",)
            left_text = constraint.get("def")
            right_raw = constraint.get("value")
            if not isinstance(left_text, str):
                return ("EXACT_CONSTRAINT_UNPROVED",)
            if isinstance(right_raw, Decimal):
                right_text = str(right_raw)
            elif isinstance(right_raw, (str, int)) and not isinstance(
                right_raw, bool
            ):
                right_text = str(right_raw)
            else:
                return ("EXACT_CONSTRAINT_UNPROVED",)
            left = _exact_eval(left_text, context, validation)
            right = _exact_eval(right_text, context, validation)
            if not _exact_zero(left - right, sympy):
                return ("EXACT_CONSTRAINT_FALSE",)
        for guard in guards:
            if not isinstance(guard, str) or not _exact_guard(
                guard, context, validation, sympy
            ):
                return ("EXACT_GUARD_FALSE_OR_UNPROVED",)
    except Exception:
        return ("EXACT_SOURCE_CONDITIONS_UNPROVED",)
    return ()


def _exact_symbolic_target(
    source_payload: bytes,
) -> tuple[dict[str, object] | None, object | None, tuple[str, ...]]:
    """Evaluate the source target exactly and construct its root descriptor.

    No numerical approximation or PSLQ result participates in the returned
    polynomial or root selection.  Unsupported source operations, nonempty
    post-processing, non-real values, and values whose algebraicity cannot be
    proved all fail closed.
    """

    try:
        document = json.loads(source_payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, None, ("EXACT_TARGET_SOURCE_MALFORMED",)
    if not isinstance(document, Mapping):
        return None, None, ("EXACT_TARGET_SOURCE_MALFORMED",)
    construction = document.get("construction")
    answer = document.get("answer")
    post_process = document.get("post_process", "")
    if (
        not isinstance(construction, list)
        or not isinstance(answer, str)
        or not isinstance(post_process, str)
        or post_process.strip()
    ):
        return None, None, ("EXACT_TARGET_SOURCE_UNSUPPORTED",)

    try:
        context, validation, sympy = _exact_context()
        for row in construction:
            if not isinstance(row, Mapping):
                return None, None, ("EXACT_CONSTRUCTION_UNPROVED",)
            name = row.get("name")
            expression = row.get("expr")
            if not isinstance(name, str) or not isinstance(expression, str):
                return None, None, ("EXACT_CONSTRUCTION_UNPROVED",)
            context[name] = _exact_eval(expression, context, validation)
        value = sympy.simplify(_exact_eval(answer, context, validation))
    except Exception:
        return None, None, ("EXACT_TARGET_EVALUATION_UNSUPPORTED",)

    if (
        isinstance(value, bool)
        or getattr(value, "is_real", None) is not True
        or getattr(value, "is_algebraic", None) is not True
    ):
        return None, None, ("EXACT_TARGET_NOT_REAL_ALGEBRAIC",)

    try:
        symbol = sympy.Symbol("target")
        rational_polynomial = sympy.Poly(
            sympy.minpoly(value, symbol), symbol, domain=sympy.QQ
        )
        _, integer_polynomial = rational_polynomial.clear_denoms(convert=True)
        _, primitive = integer_polynomial.primitive()
        if primitive.LC() < 0:
            primitive = -primitive
        if (
            primitive.degree() < 1
            or primitive.is_sqf is not True
            or primitive.is_irreducible is not True
        ):
            return None, None, ("EXACT_MINPOLY_NOT_CERTIFIED",)
        coefficients = [int(coefficient) for coefficient in primitive.all_coeffs()]
    except Exception:
        return None, None, ("EXACT_MINPOLY_UNAVAILABLE",)

    try:
        if getattr(value, "is_Rational", False) is True:
            if primitive.degree() != 1:
                return None, None, ("EXACT_ROOT_ISOLATION_UNAVAILABLE",)
            root_index = 0
            margin = sympy.Rational(1, 10**100)
            left = value - margin
            right = value + margin
            isolator: dict[str, object] = {
                "kind": "OPEN_RATIONAL_INTERVAL",
                "left": str(left),
                "right": str(right),
                "real_root_index": root_index,
                "multiplicity": 1,
                "endpoint_policy": "OPEN",
                "normalization": "EXACT_RATIONAL_POINT_PLUS_MINUS_1E_100",
                "exact_rational_root": str(value),
                "radius": str(margin),
            }
        else:
            intervals = primitive.intervals(
                eps=sympy.Rational(1, 2**320)
            )
            matches: list[tuple[int, object, object, int]] = []
            for index, (interval, multiplicity) in enumerate(intervals):
                left_candidate, right_candidate = interval
                left_positive = sympy.simplify(
                    value - left_candidate
                ).is_positive
                right_positive = sympy.simplify(
                    right_candidate - value
                ).is_positive
                if left_positive is True and right_positive is True:
                    matches.append(
                        (
                            index,
                            left_candidate,
                            right_candidate,
                            int(multiplicity),
                        )
                    )
            if len(matches) != 1:
                return None, None, ("EXACT_ROOT_ISOLATION_UNAVAILABLE",)
            root_index, left, right, multiplicity = matches[0]
            if multiplicity != 1:
                return None, None, ("EXACT_ROOT_ISOLATION_UNAVAILABLE",)
            isolator = {
                "kind": "OPEN_RATIONAL_INTERVAL",
                "left": str(left),
                "right": str(right),
                "real_root_index": root_index,
                "multiplicity": multiplicity,
                "endpoint_policy": "OPEN",
                "normalization": "EXACT_REAL_ROOT_ISOLATION_320_BITS",
            }
    except Exception:
        return None, None, ("EXACT_ROOT_ISOLATION_UNAVAILABLE",)

    value_srepr = sympy.srepr(value).encode("utf-8")
    descriptor = {
        "authority_kind": "SOURCE_EXACT_SYMBOLIC_MINPOLY_ISOLATOR",
        "minimal_polynomial_high_to_low": coefficients,
        "exact_relation_low_to_high": list(reversed(coefficients)),
        "selected_real_root_index": root_index,
        "isolating_interval": isolator,
        "primitive": True,
        "square_free": True,
        "irreducible_over_Q": True,
        "exact_value_srepr_sha256": _sha256(value_srepr),
        "numeric_pslq_used": False,
    }
    return descriptor, value, ()


def preflight_zero_dimensional_source(
    source_payload: bytes, expected_source_sha256: str
) -> tuple[str, ...]:
    """Return structural/soundness failures before launching any HP child."""

    if _sha256(source_payload) != expected_source_sha256:
        return ("SOURCE_DIGEST_MISMATCH",)
    dimension, source_error = _source_dimension(source_payload)
    if source_error is not None:
        return (source_error,)
    if dimension != 0:
        return ("SOURCE_DIMENSION_NOT_ZERO",)
    if not _target_is_certified_algebraic(source_payload):
        return ("TARGET_NOT_CERTIFIED_ALGEBRAIC_FROM_SOURCE_AST",)
    condition_failures = _exact_source_conditions_certificate(source_payload)
    if condition_failures:
        return condition_failures
    return ()


def _numeric_replay_parity_audit(
    authority: Mapping[str, object],
    *,
    source_sha256: str,
    endpoint_sha256: str,
    exact_target: object,
) -> tuple[dict[str, object] | None, tuple[str, ...]]:
    """Audit unchanged-source replay without trusting numerical recognition.

    This intentionally ignores every PSLQ/minpoly field and does not require
    the composed numerical authority to claim success.  Its sole purpose is
    to show that the existing Float64 and 512/768/1024-bit implementations
    replay the same zero-dimensional source and numerically agree with the
    independently derived exact source value.
    """

    reasons: list[str] = []
    if authority.get("schema_version") != COMPOSITION_SCHEMA:
        reasons.append("REPLAY_SCHEMA_MISMATCH")
    outer_contract = authority.get("input_contract")
    if not isinstance(outer_contract, Mapping) or not all(
        outer_contract.get(field) is expected
        for field, expected in (
            ("same_source_bytes_both_attempts", True),
            ("same_float64_endpoint_both_attempts", True),
            ("source_or_problem_modified", False),
            ("bounds_added", False),
            ("gauge_or_symmetry_reduction", False),
        )
    ):
        reasons.append("REPLAY_OUTER_INPUT_CONTRACT_REJECTED")

    final = authority.get("final_result")
    if not isinstance(final, Mapping):
        return None, tuple(reasons + ["REPLAY_FINAL_RESULT_MISSING"])
    if final.get("source_raw_sha256") != source_sha256:
        reasons.append("REPLAY_SOURCE_DIGEST_MISMATCH")
    if final.get("endpoint_float64_sha256") != endpoint_sha256:
        reasons.append("REPLAY_ENDPOINT_DIGEST_MISMATCH")

    input_contract = final.get("input_contract")
    if not isinstance(input_contract, Mapping) or not all(
        input_contract.get(field) is expected
        for field, expected in (
            ("source_bytes_and_digest", True),
            ("bare_float64_endpoint", True),
            ("truth", False),
            ("known_target_count", False),
            ("case_id", False),
            ("family", False),
        )
    ):
        reasons.append("REPLAY_FINAL_INPUT_CONTRACT_REJECTED")

    transformations = final.get("problem_transformations")
    if not isinstance(transformations, Mapping) or not transformations or any(
        value is not False for value in transformations.values()
    ):
        reasons.append("REPLAY_SOURCE_TRANSFORMATION_REJECTED")

    float64_replay = final.get("float64_replay")
    if not isinstance(float64_replay, Mapping) or not all(
        float64_replay.get(field) is True
        for field in (
            "semantic_valid",
            "hard_feasible",
            "guard_ok",
            "intrinsic_domain_ok",
        )
    ):
        reasons.append("FLOAT64_SOURCE_REPLAY_REJECTED")
    else:
        try:
            residual = float(float64_replay.get("residual_inf"))
        except (TypeError, ValueError):
            residual = math.inf
        if not math.isfinite(residual):
            reasons.append("FLOAT64_SOURCE_REPLAY_NONFINITE")

    numerical = final.get("original_numerical_replay")
    lanes = numerical.get("lanes") if isinstance(numerical, Mapping) else None
    by_bits = {
        lane.get("bits"): lane
        for lane in lanes
        if isinstance(lane, Mapping)
    } if isinstance(lanes, list) else {}
    if (
        not isinstance(lanes, list)
        or len(lanes) != 3
        or set(by_bits) != {512, 768, 1024}
    ):
        reasons.append("HP_REPLAY_LANES_MISSING")
    else:
        try:
            _, _, sympy = _exact_context()
            for bits in (512, 768, 1024):
                lane = by_bits[bits]
                if (
                    lane.get("point") != []
                    or lane.get("finite") is not True
                    or lane.get("hard_feasible") is not True
                    or lane.get("guard_ok") is not True
                    or lane.get("intrinsic_domain_ok") is not True
                ):
                    reasons.append(f"HP_REPLAY_LANE_{bits}_REJECTED")
                    continue
                answer = lane.get("answer")
                if not isinstance(answer, str):
                    reasons.append(f"HP_REPLAY_LANE_{bits}_ANSWER_MISSING")
                    continue
                observed = sympy.Rational(answer)
                error = sympy.simplify(sympy.Abs(observed - exact_target))
                tolerance = sympy.Rational(1, 2 ** (bits // 2))
                if error != 0 and sympy.simplify(
                    tolerance - error
                ).is_positive is not True:
                    reasons.append(f"HP_REPLAY_LANE_{bits}_TARGET_MISMATCH")
        except Exception:
            reasons.append("HP_REPLAY_TARGET_PARITY_UNPROVED")

    if reasons:
        return None, tuple(reasons)
    return {
        "float64_source_replay": True,
        "high_precision_source_replay_bits": [512, 768, 1024],
        "high_precision_target_parity": True,
        "numerical_recognition_ignored": True,
        "numerical_minpoly_or_pslq_used": False,
        "composition_status_observed_only": authority.get("status"),
    }, ()


def run_zero_dimensional_authority(
    source_payload: bytes,
    expected_source_sha256: str,
    endpoint: Sequence[object],
    *,
    deadline_seconds: float = 8.0,
    primary_cap_seconds: float = 4.0,
    backend: AuthorityBackend | None = None,
) -> dict[str, object]:
    """Replay and exactify the unique empty configuration, or fail closed."""

    observed_source_sha256 = _sha256(source_payload)
    empty_endpoint_sha256 = endpoint_float64_sha256(())
    if observed_source_sha256 != expected_source_sha256:
        return _fail(
            status="FAIL_CLOSED",
            source_sha256=observed_source_sha256,
            endpoint_sha256=empty_endpoint_sha256,
            reasons=("SOURCE_DIGEST_MISMATCH",),
            eligible=False,
        )
    if isinstance(endpoint, (str, bytes, bytearray)) or not isinstance(
        endpoint, Sequence
    ):
        return _fail(
            status="INELIGIBLE_FAIL_CLOSED",
            source_sha256=observed_source_sha256,
            endpoint_sha256=empty_endpoint_sha256,
            reasons=("ENDPOINT_NOT_A_SEQUENCE",),
            eligible=False,
        )
    supplied_endpoint = tuple(endpoint)
    supplied_endpoint_sha256 = endpoint_float64_sha256(
        tuple(float(value) for value in supplied_endpoint)
        if all(
            not isinstance(value, bool) and isinstance(value, (int, float))
            for value in supplied_endpoint
        )
        else ()
    )
    dimension, source_error = _source_dimension(source_payload)
    if source_error is not None:
        return _fail(
            status="INELIGIBLE_FAIL_CLOSED",
            source_sha256=observed_source_sha256,
            endpoint_sha256=supplied_endpoint_sha256,
            reasons=(source_error,),
            eligible=False,
        )
    if dimension != 0 or supplied_endpoint:
        return _fail(
            status="INELIGIBLE_FAIL_CLOSED",
            source_sha256=observed_source_sha256,
            endpoint_sha256=supplied_endpoint_sha256,
            reasons=("SOURCE_OR_ENDPOINT_DIMENSION_NOT_ZERO",),
            eligible=False,
        )
    preflight_failures = preflight_zero_dimensional_source(
        source_payload, expected_source_sha256
    )
    if preflight_failures:
        return _fail(
            status="FAIL_CLOSED",
            source_sha256=observed_source_sha256,
            endpoint_sha256=empty_endpoint_sha256,
            reasons=preflight_failures,
            eligible=True,
        )
    if (
        not math.isfinite(deadline_seconds)
        or not math.isfinite(primary_cap_seconds)
        or deadline_seconds <= 0.0
        or primary_cap_seconds <= 0.0
        or primary_cap_seconds > deadline_seconds
    ):
        return _fail(
            status="FAIL_CLOSED",
            source_sha256=observed_source_sha256,
            endpoint_sha256=empty_endpoint_sha256,
            reasons=("INVALID_DEADLINE",),
            eligible=True,
        )

    descriptor, exact_target, exact_failures = _exact_symbolic_target(
        source_payload
    )
    if descriptor is None or exact_target is None:
        return _fail(
            status="FAIL_CLOSED",
            source_sha256=observed_source_sha256,
            endpoint_sha256=empty_endpoint_sha256,
            reasons=exact_failures or ("EXACT_TARGET_AUTHORITY_UNAVAILABLE",),
            eligible=True,
        )

    try:
        authority_backend = backend or _load_authority_backend()
        authority = authority_backend(
            source_payload,
            expected_source_sha256,
            (),
            deadline_seconds=deadline_seconds,
            primary_cap_seconds=primary_cap_seconds,
        )
    except Exception as error:  # The lane must never emit a target on failure.
        return _fail(
            status="FAIL_CLOSED",
            source_sha256=observed_source_sha256,
            endpoint_sha256=empty_endpoint_sha256,
            reasons=(f"AUTHORITY_EXCEPTION_{type(error).__name__.upper()}",),
            eligible=True,
        )
    if not isinstance(authority, Mapping):
        return _fail(
            status="FAIL_CLOSED",
            source_sha256=observed_source_sha256,
            endpoint_sha256=empty_endpoint_sha256,
            reasons=("AUTHORITY_RESULT_NOT_MAPPING",),
            eligible=True,
        )
    replay_audit, reasons = _numeric_replay_parity_audit(
        authority,
        source_sha256=observed_source_sha256,
        endpoint_sha256=empty_endpoint_sha256,
        exact_target=exact_target,
    )
    if replay_audit is None:
        return _fail(
            status="FAIL_CLOSED",
            source_sha256=observed_source_sha256,
            endpoint_sha256=empty_endpoint_sha256,
            reasons=reasons or ("AUTHORITY_REJECTED",),
            eligible=True,
        )
    authority_payload = json.dumps(
        authority,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return {
        "schema_version": SCHEMA,
        "status": "EXACT_SYMBOLIC_TARGET_READY",
        "eligible": True,
        "authority_pass": True,
        "source_sha256": observed_source_sha256,
        "endpoint_float64_sha256": empty_endpoint_sha256,
        "exact_target_descriptor": descriptor,
        "exact_authority_kind": (
            "SOURCE_EXACT_SYMBOLIC_MINPOLY_ISOLATOR"
        ),
        "numeric_pslq_descriptor_used": False,
        "numeric_replay_artifact_sha256": _sha256(authority_payload),
        "numeric_replay_audit": replay_audit,
        "failure_reasons": [],
        "source_certificates": {
            "target_algebraicity_from_source_ast": True,
            "target_evaluated_exactly_from_source_ast": True,
            "primitive_square_free_irreducible_minpoly": True,
            "exact_rational_root_isolator": True,
            "all_constraints_exactly_zero": True,
            "all_guards_exactly_true": True,
        },
        "routing_audit": {
            "case_id_read": False,
            "family_read": False,
            "truth_read": False,
            "known_target_count_read": False,
            "target_value_used_for_routing": False,
            "only_source_dimension_and_endpoint_dimension_used": True,
        },
    }


__all__ = [
    "AUTHORITY_ADAPTER",
    "COMPOSITION_SCHEMA",
    "SCHEMA",
    "endpoint_float64_sha256",
    "preflight_zero_dimensional_source",
    "run_zero_dimensional_authority",
]
