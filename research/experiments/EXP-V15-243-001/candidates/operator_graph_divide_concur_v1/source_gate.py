#!/usr/bin/env python3
"""Conservative source-only gate for closed divide-and-concur projectors."""

from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping


MIN_FACTORS = 3
MAX_FACTORS = 16
MAX_INCIDENCE = 64
MAX_ARITY = 4
MAX_SHEET_PRODUCT = 8


class UnknownProjector(ValueError):
    pass


@dataclass(frozen=True)
class Entity:
    kind: str
    dependencies: frozenset[str]
    fixed_payload: object | None = None


@dataclass(frozen=True)
class Factor:
    kind: str
    dependencies: frozenset[str]
    sheets: int = 1
    typed_inverse: bool = True
    collapse_defined: bool = True


def _parse(value: object) -> ast.AST:
    if isinstance(value, str):
        source = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        source = repr(value)
    else:
        raise UnknownProjector("NONSCALAR_SOURCE_EXPRESSION")
    try:
        return ast.parse(source, mode="eval").body
    except SyntaxError as error:
        raise UnknownProjector("INVALID_SOURCE_EXPRESSION") from error


def _fraction(node: ast.AST) -> Fraction:
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return Fraction(node.value)
    if isinstance(node, ast.Constant) and isinstance(node.value, float):
        return Fraction(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _fraction(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left, right = _fraction(node.left), _fraction(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div) and right:
            return left / right
    raise UnknownProjector("NONRATIONAL_FIXED_SCALAR")


def _dependencies(node: ast.AST, entities: Mapping[str, Entity], variables: frozenset[str]) -> frozenset[str]:
    if isinstance(node, ast.Name):
        if node.id in variables:
            return frozenset((node.id,))
        if node.id in entities:
            return entities[node.id].dependencies
        if node.id == "pi":
            return frozenset()
        raise UnknownProjector("UNBOUND_SOURCE_NAME")
    if isinstance(node, ast.Constant):
        _fraction(node)
        return frozenset()
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return _dependencies(node.operand, entities, variables)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        return _dependencies(node.left, entities, variables) | _dependencies(node.right, entities, variables)
    if isinstance(node, ast.Attribute) and node.attr in {"x", "y"}:
        return _dependencies(node.value, entities, variables)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in {"CoordinateX", "CoordinateY"} and len(node.args) == 1 and not node.keywords:
            return _dependencies(node.args[0], entities, variables)
    raise UnknownProjector("OPAQUE_OR_MOVING_SCALAR_EXPRESSION")


def _direct_name(node: ast.AST) -> str | None:
    return node.id if isinstance(node, ast.Name) else None


def _call(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name


def _fixed_point(node: ast.AST, entities: Mapping[str, Entity]) -> tuple[Fraction, Fraction] | None:
    if isinstance(node, ast.Name):
        entity = entities.get(node.id)
        if entity is not None and entity.kind == "POINT" and isinstance(entity.fixed_payload, tuple):
            return entity.fixed_payload
    return None


def _entity(node: ast.AST, entities: Mapping[str, Entity], kind: str) -> Entity:
    if not isinstance(node, ast.Name) or node.id not in entities or entities[node.id].kind != kind:
        raise UnknownProjector(f"EXPECTED_TYPED_{kind}")
    return entities[node.id]


def _bound_call(node: ast.AST) -> tuple[str, Fraction, Fraction] | None:
    if not _call(node, "Bound") or node.keywords or len(node.args) != 2:
        return None
    name = _direct_name(node.args[0])
    interval = node.args[1]
    if name is None or not isinstance(interval, (ast.Tuple, ast.List)) or len(interval.elts) != 2:
        raise UnknownProjector("MALFORMED_NONSTRICT_BOUND")
    lower, upper = _fraction(interval.elts[0]), _fraction(interval.elts[1])
    if lower >= upper:
        raise UnknownProjector("EMPTY_OR_ZERO_WIDTH_BOUND")
    return name, lower, upper


def _bounds(document: Mapping[str, Any], variables: frozenset[str]) -> dict[str, tuple[Fraction, Fraction]]:
    result: dict[str, tuple[Fraction, Fraction]] = {}
    raw_bounds = document.get("bounds")
    if raw_bounds is not None:
        if not isinstance(raw_bounds, Mapping):
            raise UnknownProjector("NONMAPPING_BOUNDS")
        for name, interval in raw_bounds.items():
            if name not in variables or not isinstance(interval, (list, tuple)) or len(interval) != 2:
                raise UnknownProjector("MALFORMED_SOURCE_BOUND")
            lower, upper = _fraction(_parse(interval[0])), _fraction(_parse(interval[1]))
            if lower >= upper:
                raise UnknownProjector("EMPTY_OR_ZERO_WIDTH_BOUND")
            result[name] = (lower, upper)
    guards = document.get("guards") or []
    if not isinstance(guards, list):
        raise UnknownProjector("MALFORMED_GUARDS")
    for value in guards:
        node = _parse(value)
        bound = _bound_call(node)
        if bound is None:
            raise UnknownProjector("STRICT_OR_OPAQUE_GUARD")
        name, lower, upper = bound
        if name not in variables or name in result and result[name] != (lower, upper):
            raise UnknownProjector("BOUND_NAME_OR_TIE_UNKNOWN")
        result[name] = (lower, upper)
    return result


def _sheet_count(bound: tuple[Fraction, Fraction]) -> int:
    width = bound[1] - bound[0]
    return (width.numerator + width.denominator - 1) // width.denominator + 1


def _periodic_phase_variable(node: ast.AST, variables: frozenset[str]) -> str | None:
    # The explicit sin/cos graph uses period-one phase 2*pi*t.
    factors: list[ast.AST] = []
    def collect(value: ast.AST) -> None:
        if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Mult):
            collect(value.left)
            collect(value.right)
        else:
            factors.append(value)
    collect(node)
    has_two = any(isinstance(value, ast.Constant) and value.value == 2 for value in factors)
    has_pi = any(isinstance(value, ast.Name) and value.id == "pi" for value in factors)
    names = [value.id for value in factors if isinstance(value, ast.Name) and value.id in variables]
    return names[0] if has_two and has_pi and len(names) == 1 and len(factors) == 3 else None


def _sincos_point(node: ast.Call, variables: frozenset[str], bounds: Mapping[str, tuple[Fraction, Fraction]]) -> tuple[str, int] | None:
    if not (_call(node, "Point") and not node.keywords and len(node.args) == 2):
        return None
    first, second = node.args
    pairs = ((first, second), (second, first))
    for cosine, sine in pairs:
        if _call(cosine, "cos") and _call(sine, "sin") and len(cosine.args) == len(sine.args) == 1:
            if ast.dump(cosine.args[0], include_attributes=False) != ast.dump(sine.args[0], include_attributes=False):
                continue
            variable = _periodic_phase_variable(cosine.args[0], variables)
            if variable is not None and variable in bounds:
                return variable, _sheet_count(bounds[variable])
    return None


def _direct_coordinate_dependencies(node: ast.AST, variables: frozenset[str]) -> frozenset[str]:
    name = _direct_name(node)
    if name in variables:
        return frozenset((name,))
    _fraction(node)
    return frozenset()


def _line_payload(first: tuple[Fraction, Fraction], second: tuple[Fraction, Fraction]) -> tuple[Fraction, Fraction, Fraction]:
    if first == second:
        raise UnknownProjector("DEGENERATE_FIXED_LINE")
    a = first[1] - second[1]
    b = second[0] - first[0]
    c = first[0] * second[1] - second[0] * first[1]
    return a, b, c


def _fixed_radius_squared(node: ast.AST, entities: Mapping[str, Entity]) -> Fraction:
    try:
        value = _fraction(node)
        if value <= 0:
            raise UnknownProjector("ZERO_OR_NEGATIVE_RADIUS")
        return value * value
    except UnknownProjector:
        pass
    if _call(node, "Distance") and not node.keywords and len(node.args) == 2:
        first, second = _fixed_point(node.args[0], entities), _fixed_point(node.args[1], entities)
        if first is None or second is None or first == second:
            raise UnknownProjector("MOVING_OR_ZERO_FIXED_DISTANCE_RADIUS")
        return (first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2
    if _call(node, "sqrt") and not node.keywords and len(node.args) == 1:
        value = _fraction(node.args[0])
        if value <= 0:
            raise UnknownProjector("ZERO_OR_NEGATIVE_RADIUS")
        return value
    if _call(node, "abs") and not node.keywords and len(node.args) == 1:
        value = _fraction(node.args[0])
        if value == 0:
            raise UnknownProjector("ZERO_OR_NEGATIVE_RADIUS")
        return value * value
    raise UnknownProjector("MOVING_OR_OPAQUE_CIRCLE_RADIUS")


def _intersect_discriminant(line: tuple[Fraction, Fraction, Fraction], circle: tuple[tuple[Fraction, Fraction], Fraction]) -> int:
    a, b, c = line
    (cx, cy), radius_squared = circle
    left = (a * cx + b * cy + c) ** 2
    right = radius_squared * (a**2 + b**2)
    return -1 if left < right else 0 if left == right else 1


def _build_entities(
    document: Mapping[str, Any],
    variables: frozenset[str],
    bounds: Mapping[str, tuple[Fraction, Fraction]],
) -> tuple[dict[str, Entity], list[Factor]]:
    construction = document.get("construction")
    if not isinstance(construction, list):
        raise UnknownProjector("MALFORMED_CONSTRUCTION")
    entities: dict[str, Entity] = {}
    graph_factors: list[Factor] = []
    for item in construction:
        if not isinstance(item, Mapping) or not isinstance(item.get("name"), str):
            raise UnknownProjector("MALFORMED_CONSTRUCTION")
        name = item["name"]
        if name in variables or name in entities:
            raise UnknownProjector("SOURCE_NAME_REDEFINITION")
        node = _parse(item.get("expr"))
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            raise UnknownProjector("OPAQUE_CONSTRUCTION")
        call = node.func.id
        if call == "Point":
            sincos = _sincos_point(node, variables, bounds)
            if sincos is not None:
                variable, sheets = sincos
                graph_factors.append(Factor("SINCOS", frozenset((variable,)), sheets))
                entities[name] = Entity("POINT", frozenset((variable,)))
                continue
            if node.keywords or len(node.args) != 2:
                raise UnknownProjector("MALFORMED_POINT")
            # A closed point collapse is available only for direct scalar
            # coordinates.  Composite coordinate expressions are fail-closed.
            first_dependencies = _direct_coordinate_dependencies(node.args[0], variables)
            second_dependencies = _direct_coordinate_dependencies(node.args[1], variables)
            dependencies = first_dependencies | second_dependencies
            if first_dependencies and first_dependencies == second_dependencies:
                raise UnknownProjector("TIED_POINT_COORDINATES")
            payload = None
            if not dependencies:
                payload = (_fraction(node.args[0]), _fraction(node.args[1]))
            entities[name] = Entity("POINT", dependencies, payload)
        elif call == "Line":
            if node.keywords or len(node.args) != 2:
                raise UnknownProjector("MALFORMED_LINE")
            first, second = _entity(node.args[0], entities, "POINT"), _entity(node.args[1], entities, "POINT")
            if first.dependencies or second.dependencies or not isinstance(first.fixed_payload, tuple) or not isinstance(second.fixed_payload, tuple):
                raise UnknownProjector("MOVING_LINE")
            entities[name] = Entity("LINE", frozenset(), _line_payload(first.fixed_payload, second.fixed_payload))
        elif call == "Circle":
            if node.keywords or len(node.args) != 2:
                raise UnknownProjector("MALFORMED_CIRCLE")
            center = _entity(node.args[0], entities, "POINT")
            if center.dependencies or not isinstance(center.fixed_payload, tuple):
                raise UnknownProjector("MOVING_CIRCLE")
            radius_squared = _fixed_radius_squared(node.args[1], entities)
            entities[name] = Entity("CIRCLE", frozenset(), (center.fixed_payload, radius_squared))
        elif call == "PointOnLine":
            if node.keywords or len(node.args) != 2:
                raise UnknownProjector("MALFORMED_POINT_ON_LINE")
            line = _entity(node.args[0], entities, "LINE")
            if line.dependencies or line.fixed_payload is None:
                raise UnknownProjector("MOVING_POINT_ON_LINE_AXIS")
            parameter = _direct_name(node.args[1])
            if parameter not in variables:
                raise UnknownProjector("NONINVERTIBLE_POINT_ON_LINE_PARAMETER")
            dependencies = frozenset((parameter,))
            graph_factors.append(Factor("POINT_ON_LINE", dependencies))
            entities[name] = Entity("POINT", dependencies)
        elif call == "PointOnCircle":
            if node.keywords or len(node.args) != 2:
                raise UnknownProjector("MALFORMED_POINT_ON_CIRCLE")
            circle = _entity(node.args[0], entities, "CIRCLE")
            phase = _direct_name(node.args[1])
            if circle.dependencies or circle.fixed_payload is None or phase not in variables or phase not in bounds:
                raise UnknownProjector("MOVING_OR_INFINITE_SHEET_POINT_ON_CIRCLE")
            sheets = _sheet_count(bounds[phase])
            graph_factors.append(Factor("POINT_ON_CIRCLE", frozenset((phase,)), sheets))
            entities[name] = Entity("POINT", frozenset((phase,)))
        elif call == "Intersect":
            if len(node.args) != 2 or set(keyword.arg for keyword in node.keywords) != {"n"}:
                raise UnknownProjector("AMBIGUOUS_OR_UNTYPED_INTERSECT")
            first_name, second_name = _direct_name(node.args[0]), _direct_name(node.args[1])
            if first_name not in entities or second_name not in entities:
                raise UnknownProjector("UNTYPED_INTERSECT_OPERAND")
            first, second = entities[first_name], entities[second_name]
            line, circle = (first, second) if (first.kind, second.kind) == ("LINE", "CIRCLE") else (second, first) if (first.kind, second.kind) == ("CIRCLE", "LINE") else (None, None)
            if line is None or line.dependencies or circle.dependencies:
                raise UnknownProjector("MOVING_OR_WRONG_TYPED_INTERSECT")
            selector = _fraction(node.keywords[0].value)
            if selector.denominator != 1 or selector not in (0, 1):
                raise UnknownProjector("AMBIGUOUS_INTERSECT_SELECTOR")
            discriminant = _intersect_discriminant(line.fixed_payload, circle.fixed_payload)
            if discriminant == 0:
                raise UnknownProjector("TANGENT_INTERSECT")
            if discriminant > 0:
                raise UnknownProjector("EMPTY_INTERSECT")
            entities[name] = Entity("POINT", frozenset())
        else:
            raise UnknownProjector("OPAQUE_CONSTRUCTION")
    return entities, graph_factors


def _is_zero(node: ast.AST) -> bool:
    try:
        return _fraction(node) == 0
    except UnknownProjector:
        return False


def _constraint_factor(node_left: ast.AST, node_right: ast.AST, entities: Mapping[str, Entity], variables: frozenset[str]) -> Factor:
    left_name, right_name = _direct_name(node_left), _direct_name(node_right)
    if left_name in variables and right_name in variables:
        return Factor("EQ", frozenset((left_name, right_name)))
    if left_name in variables:
        try:
            _fraction(node_right)
            return Factor("PIN", frozenset((left_name,)))
        except UnknownProjector:
            pass
    if right_name in variables:
        try:
            _fraction(node_left)
            return Factor("PIN", frozenset((right_name,)))
        except UnknownProjector:
            pass
    call_node = node_left if isinstance(node_left, ast.Call) and _is_zero(node_right) else node_right if isinstance(node_right, ast.Call) and _is_zero(node_left) else None
    if call_node is None or not isinstance(call_node.func, ast.Name) or call_node.keywords:
        raise UnknownProjector("OPAQUE_OR_NONPROJECTABLE_EQUALITY")
    call = call_node.func.id
    if call == "OnSegment" and len(call_node.args) == 3:
        point = _entity(call_node.args[0], entities, "POINT")
        first = _entity(call_node.args[1], entities, "POINT")
        second = _entity(call_node.args[2], entities, "POINT")
        if first.dependencies or second.dependencies or first.fixed_payload == second.fixed_payload:
            raise UnknownProjector("MOVING_OR_DEGENERATE_SEGMENT")
        return Factor("ON_SEGMENT", point.dependencies)
    if call in {"OnLine", "PointOnLine"} and len(call_node.args) == 2:
        point = _entity(call_node.args[0], entities, "POINT")
        line = _entity(call_node.args[1], entities, "LINE")
        if line.dependencies or line.fixed_payload is None:
            raise UnknownProjector("MOVING_LINE_FACTOR")
        return Factor("POINT_ON_LINE", point.dependencies)
    if call in {"OnCircle", "PointOnCircle"} and len(call_node.args) == 2:
        point = _entity(call_node.args[0], entities, "POINT")
        circle = _entity(call_node.args[1], entities, "CIRCLE")
        if circle.dependencies or circle.fixed_payload is None or circle.fixed_payload[1] <= 0:
            raise UnknownProjector("MOVING_OR_ZERO_RADIUS_CIRCLE_FACTOR")
        return Factor("POINT_ON_CIRCLE", point.dependencies)
    raise UnknownProjector("OPAQUE_OR_UNSUPPORTED_FACTOR")


def _cycle_rank(factors: list[Factor]) -> tuple[int, Counter[str]]:
    active_variables = sorted(set().union(*(factor.dependencies for factor in factors)))
    adjacency: dict[str, set[str]] = defaultdict(set)
    for index, factor in enumerate(factors):
        factor_name = f"F{index}"
        adjacency.setdefault(factor_name, set())
        for variable in factor.dependencies:
            variable_name = f"V:{variable}"
            adjacency[factor_name].add(variable_name)
            adjacency[variable_name].add(factor_name)
    visited: set[str] = set()
    components = 0
    for node in adjacency:
        if node in visited:
            continue
        components += 1
        stack = [node]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            stack.extend(adjacency[current] - visited)
    edges = sum(len(factor.dependencies) for factor in factors)
    rank = edges - len(adjacency) + components
    degrees = Counter(variable for factor in factors for variable in factor.dependencies)
    return max(0, rank), degrees


def scan(document: Mapping[str, Any], source_sha256: str) -> dict[str, Any]:
    base = {
        "candidate": "OPERATOR_GRAPH_DIVIDE_CONCUR_V1",
        "source_sha256": source_sha256,
        "truth_case_family_target_or_result_used": False,
    }
    try:
        if document.get("task") != "solve" or document.get("post_process") not in (None, ""):
            raise UnknownProjector("NOT_DIRECT_SOLVE_OR_POST_PROCESS")
        variables_node = document.get("variables")
        names = variables_node.get("names") if isinstance(variables_node, Mapping) else None
        constraints = document.get("constraints")
        if (
            not isinstance(names, list)
            or not names
            or not all(isinstance(name, str) and name for name in names)
            or len(set(names)) != len(names)
            or not isinstance(constraints, list)
        ):
            raise UnknownProjector("MALFORMED_SOURCE")
        variables = frozenset(names)
        bounds = _bounds(document, variables)
        entities, factors = _build_entities(document, variables, bounds)
        source_factor_total = len(factors) + len(constraints)
        for item in constraints:
            if not isinstance(item, Mapping) or "def" not in item or "value" not in item:
                raise UnknownProjector("MALFORMED_CONSTRAINT")
            factors.append(_constraint_factor(_parse(item["def"]), _parse(item["value"]), entities, variables))
        closed_factor_count = len(factors)
        incidence = sum(len(factor.dependencies) for factor in factors)
        maximum_arity = max((len(factor.dependencies) for factor in factors), default=0)
        sheet_product = math.prod(factor.sheets for factor in factors)
        cycle_rank, degrees = _cycle_rank(factors)
        shared_degree = max(degrees.values(), default=0)
        kinds = Counter(factor.kind for factor in factors)
        typed_inverse = all(factor.typed_inverse for factor in factors)
        collapse = all(factor.collapse_defined for factor in factors)
        gates = {
            "closed_equals_total": closed_factor_count == source_factor_total,
            "factor_count_3_to_16": MIN_FACTORS <= closed_factor_count <= MAX_FACTORS,
            "incidence_at_most_64": incidence <= MAX_INCIDENCE,
            "arity_at_most_4": maximum_arity <= MAX_ARITY,
            "shared_degree_at_least_2": shared_degree >= 2,
            "cycle_rank_at_least_1": cycle_rank >= 1,
            "projector_kinds_at_least_2": len(kinds) >= 2,
            "sheet_product_at_most_8": sheet_product <= MAX_SHEET_PRODUCT,
            "typed_inverse_and_collapse": typed_inverse and collapse,
        }
        fingerprint_payload = {
            "factor_kinds": sorted(kinds.items()),
            "arity_multiset": sorted(len(factor.dependencies) for factor in factors),
            "sheet_multiset": sorted(factor.sheets for factor in factors),
            "degree_multiset": sorted(degrees.values()),
            "cycle_rank": cycle_rank,
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {
            **base,
            "eligible": all(gates.values()),
            "decision": "STATIC_GATE_PASS" if all(gates.values()) else "HOLD_STATIC_GATE",
            "anonymous_structural_fingerprint_sha256": fingerprint,
            "factor_total": source_factor_total,
            "closed_factor_count": closed_factor_count,
            "factor_kind_counts": dict(sorted(kinds.items())),
            "incidence_count": incidence,
            "maximum_factor_arity": maximum_arity,
            "shared_variable_degree": shared_degree,
            "cycle_rank": cycle_rank,
            "sheet_product": sheet_product,
            "typed_inverse_and_collapse": typed_inverse and collapse,
            "dimensionless_replica_normalization": True,
            "factor_duplication_total_weight": 1,
            "runtime_unknown_full_attempt_fallback": [
                "moving", "opaque", "ambiguous", "tangent", "tie",
                "zero_radius", "strict_boundary",
            ],
            "static_gates": gates,
        }
    except (UnknownProjector, KeyError, TypeError, ZeroDivisionError) as error:
        return {
            **base,
            "eligible": False,
            "decision": "UNKNOWN_FULL_ATTEMPT_FALLBACK",
            "unknown_reason": str(error),
            "closed_factor_count": 0,
            "factor_total": None,
            "static_gates": {},
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    arguments = parser.parse_args()
    payload = arguments.source.read_bytes()
    observed = hashlib.sha256(payload).hexdigest()
    if observed != arguments.source_sha256:
        raise SystemExit("source SHA-256 mismatch")
    document = json.loads(payload)
    if not isinstance(document, Mapping):
        raise SystemExit("source root is not an object")
    print(json.dumps(scan(document, observed), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
