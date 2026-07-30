#!/usr/bin/env python3
"""Aggregate-only source census for the operator-safe trig D0.

Rows may contain outcome-bearing sibling fields.  This module lexically
extracts only the top-level ``formulation`` value and never deserializes a full
row.  It emits aggregate counts only: no identity, source digest, expression,
target value, truth or per-case record is retained.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import sympy as sp


EXPECTED_DEVELOPMENT_SHA256 = (
    "c150bb352fc905dc4eead8a56ec50125d6dd2409d2de14ccd91a502836ea8511"
)
EXPECTED_FORMULATION_COUNT = 145


class SourceBoundaryError(ValueError):
    pass


def _skip_space(data: bytes, offset: int) -> int:
    while offset < len(data) and data[offset] in b" \t\r\n":
        offset += 1
    return offset


def _string_end(data: bytes, offset: int) -> int:
    if offset >= len(data) or data[offset] != ord('"'):
        raise SourceBoundaryError("expected JSON string")
    offset += 1
    while offset < len(data):
        if data[offset] == ord('"'):
            return offset + 1
        offset += 2 if data[offset] == ord("\\") else 1
    raise SourceBoundaryError("unterminated JSON string")


def _value_end(data: bytes, offset: int) -> int:
    offset = _skip_space(data, offset)
    if offset >= len(data):
        raise SourceBoundaryError("missing JSON value")
    if data[offset] == ord('"'):
        return _string_end(data, offset)
    if data[offset] in (ord("{"), ord("[")):
        stack = [data[offset]]
        offset += 1
        while offset < len(data) and stack:
            byte = data[offset]
            if byte == ord('"'):
                offset = _string_end(data, offset)
                continue
            if byte in (ord("{"), ord("[")):
                stack.append(byte)
            elif byte == ord("}"):
                if stack.pop() != ord("{"):
                    raise SourceBoundaryError("mismatched JSON container")
            elif byte == ord("]"):
                if stack.pop() != ord("["):
                    raise SourceBoundaryError("mismatched JSON container")
            offset += 1
        if stack:
            raise SourceBoundaryError("unterminated JSON container")
        return offset
    while offset < len(data) and data[offset] not in b",}] \t\r\n":
        offset += 1
    return offset


def formulation_bytes(row: bytes) -> bytes:
    """Extract a formulation while skipping every sibling value lexically."""

    offset = _skip_space(row, 0)
    if offset >= len(row) or row[offset] != ord("{"):
        raise SourceBoundaryError("row is not a JSON object")
    offset += 1
    found: bytes | None = None
    while True:
        offset = _skip_space(row, offset)
        if offset < len(row) and row[offset] == ord("}"):
            offset += 1
            break
        key_end = _string_end(row, offset)
        key = json.loads(row[offset:key_end])
        offset = _skip_space(row, key_end)
        if offset >= len(row) or row[offset] != ord(":"):
            raise SourceBoundaryError("missing property separator")
        start = _skip_space(row, offset + 1)
        end = _value_end(row, start)
        if key == "formulation":
            if found is not None:
                raise SourceBoundaryError("duplicate formulation property")
            found = row[start:end]
        offset = _skip_space(row, end)
        if offset < len(row) and row[offset] == ord(","):
            offset += 1
            continue
        if offset < len(row) and row[offset] == ord("}"):
            offset += 1
            break
        raise SourceBoundaryError("malformed top-level object")
    if _skip_space(row, offset) != len(row) or found is None:
        raise SourceBoundaryError("trailing bytes or missing formulation")
    return found


def _parse(text: object) -> ast.AST:
    return ast.parse(str(text), mode="eval").body


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _rational_literal(node: ast.AST) -> Fraction | None:
    if isinstance(node, ast.Constant) and not isinstance(node.value, bool):
        if isinstance(node.value, (int, float)):
            return Fraction(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _rational_literal(node.operand)
        if value is None:
            return None
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(
        node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)
    ):
        left, right = _rational_literal(node.left), _rational_literal(node.right)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        return None if right == 0 else left / right
    return None


def _phase_key(
    node: ast.AST, declared: frozenset[str], *, unit: str
) -> tuple[str, str, str, str] | None:
    symbols = {name: sp.Symbol(name, real=True) for name in declared}
    try:
        expression = sp.sympify(
            ast.unparse(node), locals={**symbols, "pi": sp.pi}, rational=True
        )
    except (TypeError, ValueError, SyntaxError, sp.SympifyError):
        return None
    variables = expression.free_symbols & set(symbols.values())
    if len(variables) != 1:
        return None
    variable = next(iter(variables))
    coefficient = sp.simplify(sp.diff(expression, variable))
    offset = sp.simplify(expression - coefficient * variable)
    if coefficient.free_symbols or offset.free_symbols:
        return None
    if unit == "radians":
        offset_pi = sp.simplify(offset / sp.pi)
        if coefficient.is_Rational is not True or offset_pi.is_Rational is not True:
            return None
        return variable.name, unit, str(sp.Rational(coefficient)), str(sp.Rational(offset_pi))
    if coefficient.is_Rational is not True or offset.is_Rational is not True:
        return None
    return variable.name, unit, str(sp.Rational(coefficient)), str(sp.Rational(offset))


def _bound_names(guards: list[ast.AST]) -> set[str]:
    names: set[str] = set()
    for root in guards:
        for node in ast.walk(root):
            if (
                _call_name(node) == "Bound"
                and len(node.args) == 2
                and isinstance(node.args[0], ast.Name)
                and isinstance(node.args[1], ast.Tuple)
                and len(node.args[1].elts) == 2
            ):
                # Endpoints may be rational multiples of pi. SymPy is used
                # only to prove they are finite constants; values are not kept.
                try:
                    endpoints = [
                        sp.sympify(ast.unparse(item), locals={"pi": sp.pi}, rational=True)
                        for item in node.args[1].elts
                    ]
                except (TypeError, ValueError, SyntaxError, sp.SympifyError):
                    continue
                if all(not item.free_symbols and item.is_finite is True for item in endpoints):
                    names.add(node.args[0].id)
    return names


def _is_distance(node: ast.AST, named_distances: frozenset[str]) -> bool:
    return (
        _call_name(node) == "Distance" and len(node.args) == 2
    ) or (isinstance(node, ast.Name) and node.id in named_distances)


def analyze_formulation(document: Mapping[str, Any]) -> dict[str, int | bool]:
    declared = frozenset(document.get("variables", {}).get("names", ()))
    construction_roots = [_parse(item["expr"]) for item in document.get("construction", ())]
    constraint_roots = [
        (_parse(item["def"]), _parse(item.get("value", 0)))
        for item in document.get("constraints", ())
    ]
    guard_roots = [_parse(text) for text in document.get("guards", ())]
    target_root = _parse(document.get("answer", "0"))
    named_distances = frozenset(
        str(item["name"])
        for item, root in zip(document.get("construction", ()), construction_roots, strict=True)
        if _call_name(root) == "Distance" and len(root.args) == 2
    )

    sites = [*construction_roots]
    sites.extend(node for pair in constraint_roots for node in pair)
    sites.append(target_root)
    raw_operators: dict[tuple[str, str, str, str], set[str]] = {}
    point_on_circle_groups: set[tuple[str, str, str, str]] = set()
    phase_name_nodes: set[int] = set()
    all_name_nodes: list[ast.Name] = []
    malformed_phase_calls = 0
    for root in sites:
        all_name_nodes.extend(node for node in ast.walk(root) if isinstance(node, ast.Name))
        for node in ast.walk(root):
            name = _call_name(node)
            if name in {"sin", "cos"}:
                if len(node.args) != 1:
                    malformed_phase_calls += 1
                    continue
                phase_name_nodes.update(
                    id(item) for item in ast.walk(node.args[0]) if isinstance(item, ast.Name)
                )
                key = _phase_key(node.args[0], declared, unit="radians")
                if key is None:
                    malformed_phase_calls += 1
                else:
                    raw_operators.setdefault(key, set()).add(name)
            elif name == "PointOnCircle":
                if len(node.args) < 2:
                    malformed_phase_calls += 1
                    continue
                phase_name_nodes.update(
                    id(item) for item in ast.walk(node.args[1]) if isinstance(item, ast.Name)
                )
                key = _phase_key(node.args[1], declared, unit="turns")
                if key is None:
                    malformed_phase_calls += 1
                else:
                    point_on_circle_groups.add(key)
    explicit_pairs = {key for key, operators in raw_operators.items() if operators == {"sin", "cos"}}
    all_groups = explicit_pairs | point_on_circle_groups
    phase_variables = {key[0] for key in all_groups}
    raw_escape_variables = {
        node.id
        for node in all_name_nodes
        if node.id in phase_variables and id(node) not in phase_name_nodes
    }
    bounded = _bound_names(guard_roots)
    finite_groups = {key for key in all_groups if key[0] in bounded}
    units_by_variable: dict[str, set[str]] = {}
    for key in all_groups:
        units_by_variable.setdefault(key[0], set()).add(key[1])
    mixed_units = any(len(units) > 1 for units in units_by_variable.values())
    d0_compatible = bool(
        len(finite_groups) == 1
        and len(all_groups) == 1
        and not raw_escape_variables
        and not mixed_units
        and malformed_phase_calls == 0
    )

    safe_literal_constraints = 0
    safe_distance_constraints = 0
    any_distance_constraint = False
    for left, right in constraint_roots:
        any_distance_constraint = any_distance_constraint or any(
            _call_name(node) == "Distance" for root in (left, right) for node in ast.walk(root)
        )
        left_distance = _is_distance(left, named_distances)
        right_distance = _is_distance(right, named_distances)
        left_literal, right_literal = _rational_literal(left), _rational_literal(right)
        if left_distance and right_distance:
            safe_distance_constraints += 1
        elif left_distance and right_literal is not None and right_literal > 0:
            safe_literal_constraints += 1
        elif right_distance and left_literal is not None and left_literal > 0:
            safe_literal_constraints += 1
    safe_total = safe_literal_constraints + safe_distance_constraints
    return {
        "explicit_pair": bool(explicit_pairs),
        "point_on_circle": bool(point_on_circle_groups),
        "any_exact_affine_trig": bool(all_groups),
        "finite_sheet_trig": bool(finite_groups),
        "d0_compatible_trig": d0_compatible,
        "mixed_units": mixed_units,
        "raw_phase_escape": bool(raw_escape_variables),
        "malformed_phase": malformed_phase_calls > 0,
        "any_distance_constraint": any_distance_constraint,
        "safe_distance_square": safe_total > 0,
        "safe_distance_literal_constraints": safe_literal_constraints,
        "safe_distance_distance_constraints": safe_distance_constraints,
    }


def census(path: Path) -> dict[str, object]:
    container_digest = hashlib.sha256()
    formulation_digest = hashlib.sha256()
    cases = Counter()
    constraints = Counter()
    count = 0
    with path.open("rb") as source:
        for raw_row in source:
            container_digest.update(raw_row)
            if not raw_row.strip():
                continue
            encoded = formulation_bytes(raw_row.rstrip(b"\r\n"))
            formulation_digest.update(len(encoded).to_bytes(8, "big"))
            formulation_digest.update(encoded)
            document = json.loads(encoded)
            if not isinstance(document, Mapping):
                raise SourceBoundaryError("formulation is not an object")
            result = analyze_formulation(document)
            for field in (
                "explicit_pair",
                "point_on_circle",
                "any_exact_affine_trig",
                "finite_sheet_trig",
                "d0_compatible_trig",
                "mixed_units",
                "raw_phase_escape",
                "malformed_phase",
                "any_distance_constraint",
                "safe_distance_square",
            ):
                cases[field] += int(bool(result[field]))
            constraints["distance_to_positive_literal"] += int(
                result["safe_distance_literal_constraints"]
            )
            constraints["distance_to_distance"] += int(
                result["safe_distance_distance_constraints"]
            )
            cases["d0_trig_and_safe_distance"] += int(
                bool(result["d0_compatible_trig"] and result["safe_distance_square"])
            )
            cases["any_operator_lowering_surface"] += int(
                bool(result["d0_compatible_trig"] or result["safe_distance_square"])
            )
            count += 1
    digest = container_digest.hexdigest()
    if digest != EXPECTED_DEVELOPMENT_SHA256:
        raise SourceBoundaryError(f"development source SHA-256 mismatch: {digest}")
    if count != EXPECTED_FORMULATION_COUNT:
        raise SourceBoundaryError(f"expected 145 formulations, observed {count}")
    return {
        "schema_version": "geotarget.exp-trig-lift-d0-static-census/v1",
        "authority": "TRUTH_BLIND_STATIC_SOURCE_ACTIVATION_ONLY",
        "custody": {
            "development_container_sha256": digest,
            "formulation_stream_sha256": formulation_digest.hexdigest(),
            "formulation_count": count,
            "row_objects_deserialized": False,
            "sibling_values_deserialized": False,
            "problem_ids_retained_or_reported": False,
            "source_target_ast_read_for_escape_analysis": True,
            "truth_scorer_result_loaded": False,
            "validation_or_sealed_access": False,
            "formal_solver_run": False,
        },
        "case_activation_counts": dict(sorted(cases.items())),
        "safe_distance_constraint_counts": dict(sorted(constraints.items())),
        "interpretation_limit": (
            "Counts prove only typed source-surface recognition. They do not prove that downstream "
            "geometry lowers to the D0 bivariate polynomial block, that every source root can be "
            "enumerated, or that any target is solved."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    result = census(arguments.dataset)
    arguments.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
