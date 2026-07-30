#!/usr/bin/env python3
"""Anonymous source-AST localization for the exact-angle rejection.

This scanner models only the base worker's `as_angle` call sites.  It emits
section/type aggregates and never emits source text, names, values, case IDs,
targets, descriptors, truth, or individual relation indices.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import scanner as repair_a_scanner


ANGLE = "ANGLE"
MAYBE_ANGLE = "MAYBE_ANGLE_AFTER_RUNTIME_INTEGER_SCALE"
PI = "PI_MULTIPLE"
RATIONAL = "RATIONAL"
QBAR = "QBAR"
UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RuntimeType:
    tag: str
    zero: str = "UNKNOWN"  # ZERO, NONZERO, or UNKNOWN


UNKNOWN_TYPE = RuntimeType(UNKNOWN)
ANGLE_TYPES = frozenset((ANGLE, MAYBE_ANGLE))


def _expression(value: object) -> ast.AST | None:
    if isinstance(value, str):
        source = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        source = repr(value)
    else:
        return None
    try:
        return ast.parse(source, mode="eval").body
    except SyntaxError:
        return None


def _fraction(node: ast.AST) -> Fraction | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        try:
            return Fraction(str(node.value))
        except (ValueError, ZeroDivisionError):
            return None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _fraction(node.operand)
        if value is None:
            return None
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left, right = _fraction(node.left), _fraction(node.right)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div) and right:
            return left / right
        if isinstance(node.op, ast.Pow) and right.denominator == 1:
            try:
                return left ** int(right)
            except (OverflowError, ZeroDivisionError):
                return None
    return None


def _zero_from_fraction(value: Fraction | None) -> str:
    return "UNKNOWN" if value is None else "ZERO" if value == 0 else "NONZERO"


def _algebraic_type(left: RuntimeType, right: RuntimeType, node: ast.AST) -> RuntimeType:
    if left.tag not in {RATIONAL, QBAR} or right.tag not in {RATIONAL, QBAR}:
        return UNKNOWN_TYPE
    tag = RATIONAL if left.tag == right.tag == RATIONAL else QBAR
    return RuntimeType(tag, _zero_from_fraction(_fraction(node)) if tag == RATIONAL else "UNKNOWN")


def _angle_operand_rejects(value: RuntimeType) -> str | None:
    if value.tag in ANGLE_TYPES | {PI}:
        return None
    if value.tag in {RATIONAL, QBAR} and value.zero == "ZERO":
        return None
    return "POSSIBLE_RUNTIME" if value.tag == QBAR and value.zero == "UNKNOWN" else "CERTAIN_SOURCE_TYPE"


class OccurrenceAnalyzer:
    def __init__(self) -> None:
        self.sites: Counter[str] = Counter()

    def _record(self, section: str, site_kind: str, left: RuntimeType, right: RuntimeType, *, selected: bool | None) -> None:
        left_rejects, right_rejects = _angle_operand_rejects(left), _angle_operand_rejects(right)
        rejection = left_rejects or right_rejects
        if rejection is None:
            return
        has_angle = left.tag in ANGLE_TYPES or right.tag in ANGLE_TYPES
        has_pi = left.tag == PI or right.tag == PI
        if has_angle:
            mechanism = "ANGLE_WITH_NONANGLE_SCALAR"
            repair_b = "NO_EXACT_QQBAR_TO_ANGLE_COERCION"
        elif has_pi:
            mechanism = "PI_WITH_ALGEBRAIC_SCALAR"
            repair_b = "PATCHED_PI_AFFINE_ARITHMETIC_ALREADY_COVERS"
        else:
            return
        selected_label = "SELECTED" if selected is True else "UNSELECTED" if selected is False else "NOT_RELATION_ROOT"
        self.sites[f"{section}|{site_kind}|{mechanism}|{rejection}|{selected_label}|{repair_b}"] += 1

    def infer(self, node: ast.AST, environment: Mapping[str, RuntimeType], section: str) -> RuntimeType:
        if isinstance(node, ast.Name):
            if node.id == "pi":
                return RuntimeType(PI, "NONZERO")
            return environment.get(node.id, UNKNOWN_TYPE)
        if isinstance(node, ast.Constant):
            value = _fraction(node)
            return RuntimeType(RATIONAL, _zero_from_fraction(value)) if value is not None else UNKNOWN_TYPE
        if isinstance(node, ast.Attribute) and node.attr in {"x", "y", "a", "b", "c"}:
            self.infer(node.value, environment, section)
            return RuntimeType(QBAR)
        if isinstance(node, ast.UnaryOp):
            value = self.infer(node.operand, environment, section)
            return value if isinstance(node.op, ast.UAdd) else RuntimeType(value.tag, value.zero) if isinstance(node.op, ast.USub) else UNKNOWN_TYPE
        if isinstance(node, ast.BinOp):
            left = self.infer(node.left, environment, section)
            right = self.infer(node.right, environment, section)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                if left.tag in ANGLE_TYPES | {PI} or right.tag in ANGLE_TYPES | {PI}:
                    self._record(section, "BINARY_ADD_SUB", left, right, selected=None)
                    if _angle_operand_rejects(left) is None and _angle_operand_rejects(right) is None:
                        return RuntimeType(MAYBE_ANGLE if MAYBE_ANGLE in {left.tag, right.tag} else ANGLE)
                    return UNKNOWN_TYPE
                return _algebraic_type(left, right, node)
            if isinstance(node.op, ast.Mult):
                if left.tag in ANGLE_TYPES or right.tag in ANGLE_TYPES:
                    angle_value, scalar_node, scalar = (
                        (left, node.right, right) if left.tag in ANGLE_TYPES else (right, node.left, left)
                    )
                    exact = _fraction(scalar_node)
                    if scalar.tag == RATIONAL and exact is not None and exact.denominator == 1:
                        return angle_value
                    if scalar.tag == QBAR:
                        return RuntimeType(MAYBE_ANGLE)
                    return UNKNOWN_TYPE
                if left.tag == PI and right.tag == RATIONAL or right.tag == PI and left.tag == RATIONAL:
                    return RuntimeType(PI)
                return _algebraic_type(left, right, node)
            if isinstance(node.op, ast.Div):
                if left.tag in ANGLE_TYPES:
                    exact = _fraction(node.right)
                    if right.tag == RATIONAL and exact is not None and abs(exact) == 1:
                        return left
                    if right.tag == QBAR:
                        return RuntimeType(MAYBE_ANGLE)
                    return UNKNOWN_TYPE
                if left.tag == PI and right.tag == RATIONAL:
                    return RuntimeType(PI)
                return _algebraic_type(left, right, node)
            if isinstance(node.op, ast.Pow):
                return _algebraic_type(left, right, node)
            return UNKNOWN_TYPE
        if isinstance(node, ast.Compare):
            first = self.infer(node.left, environment, section)
            for value in node.comparators:
                second = self.infer(value, environment, section)
                if first.tag in ANGLE_TYPES | {PI} or second.tag in ANGLE_TYPES | {PI}:
                    self._record(section, "COMPARISON", first, second, selected=None)
                first = second
            return RuntimeType("BOOL")
        if isinstance(node, ast.BoolOp):
            for value in node.values:
                self.infer(value, environment, section)
            return RuntimeType("BOOL")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            arguments = [self.infer(value, environment, section) for value in node.args]
            for keyword in node.keywords:
                self.infer(keyword.value, environment, section)
            name = node.func.id
            if name == "Angle":
                return RuntimeType(ANGLE)
            if name in {"AssumeEq", "AssumeNe", "AssumeLt", "AssumeLe", "AssumeGt", "AssumeGe"} and len(arguments) == 2:
                if arguments[0].tag in ANGLE_TYPES | {PI} or arguments[1].tag in ANGLE_TYPES | {PI}:
                    self._record(section, "LOWERED_COMPARISON", arguments[0], arguments[1], selected=None)
                return RuntimeType("BOOL")
            if name in {"min", "max"}:
                for index, left in enumerate(arguments):
                    for right in arguments[index + 1:]:
                        if left.tag in ANGLE_TYPES | {PI} or right.tag in ANGLE_TYPES | {PI}:
                            self._record(section, "MINMAX", left, right, selected=None)
                if arguments and all(value.tag in ANGLE_TYPES for value in arguments):
                    return RuntimeType(MAYBE_ANGLE if any(value.tag == MAYBE_ANGLE for value in arguments) else ANGLE)
                return UNKNOWN_TYPE
            if name in repair_a_scanner.POINT_CALLS or name == "Vector":
                return RuntimeType("POINT")
            if name in repair_a_scanner.LINE_CALLS:
                return RuntimeType("LINE")
            if name in repair_a_scanner.CIRCLE_CALLS:
                return RuntimeType("CIRCLE")
            if name == "Arc":
                return RuntimeType("ARC")
            if name in repair_a_scanner.QBAR_CALLS or name in {"sqrt", "abs"}:
                return RuntimeType(QBAR)
            return UNKNOWN_TYPE
        return UNKNOWN_TYPE

    def synthetic_relation_root(self, left: RuntimeType, right: RuntimeType, *, selected: bool) -> None:
        self._record("constraint_synthetic_root", "SYNTHETIC_SUB", left, right, selected=selected)


def scan(document: Mapping[str, Any]) -> dict[str, Any]:
    variables = document.get("variables")
    names = variables.get("names") if isinstance(variables, Mapping) else None
    construction = document.get("construction")
    constraints = document.get("constraints")
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise ValueError("malformed source variables")
    if not isinstance(construction, list) or not isinstance(constraints, list):
        raise ValueError("malformed source construction or constraints")
    analyzer = OccurrenceAnalyzer()
    environment: dict[str, RuntimeType] = {name: RuntimeType(QBAR) for name in names}
    for item in construction:
        if not isinstance(item, Mapping) or not isinstance(item.get("name"), str):
            raise ValueError("malformed construction")
        expression = _expression(item.get("expr"))
        inferred = UNKNOWN_TYPE if expression is None else analyzer.infer(expression, environment, "construction")
        if item["name"] in environment:
            raise ValueError("source name redefinition")
        environment[item["name"]] = inferred

    selected = set(repair_a_scanner.eligible_relation_indices(document, "scalar is not an exact angle expression"))
    selected_root_count = 0
    selected_rejecting_root_count = 0
    for index, item in enumerate(constraints):
        if not isinstance(item, Mapping):
            continue
        left_ast, right_ast = _expression(item.get("def")), _expression(item.get("value"))
        if left_ast is None or right_ast is None:
            continue
        left = analyzer.infer(left_ast, environment, "constraint_operand")
        right = analyzer.infer(right_ast, environment, "constraint_operand")
        is_selected = index in selected
        before = sum(analyzer.sites.values())
        analyzer.synthetic_relation_root(left, right, selected=is_selected)
        after = sum(analyzer.sites.values())
        selected_root_count += int(is_selected)
        selected_rejecting_root_count += int(is_selected and after > before)

    guards = document.get("guards") or []
    if isinstance(guards, list):
        for value in guards:
            node = _expression(value)
            if node is not None:
                analyzer.infer(node, environment, "guard")
    bounds = document.get("bounds")
    if isinstance(bounds, list):
        for pair in bounds:
            if isinstance(pair, (list, tuple)):
                for value in pair:
                    node = _expression(value)
                    if node is not None:
                        analyzer.infer(node, environment, "bound")
    answer = _expression(document.get("answer"))
    if answer is not None:
        analyzer.infer(answer, environment, "raw_answer")

    counts = dict(sorted(analyzer.sites.items()))
    angle_unreachable = sum(count for key, count in counts.items() if "NO_EXACT_QQBAR_TO_ANGLE_COERCION" in key)
    pi_already_covered = sum(count for key, count in counts.items() if "PATCHED_PI_AFFINE_ARITHMETIC_ALREADY_COVERS" in key)
    total = sum(counts.values())
    digest = hashlib.sha256(json.dumps(counts, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "candidate": "TYPED_SEMANTIC_EQUAL_QBAR_PI_AFFINE_V1",
        "failure_class": "scalar is not an exact angle expression",
        "anonymous_rejecting_occurrence_counts": counts,
        "anonymous_occurrence_signature_sha256": digest,
        "repair_a_selected_relation_root_count": selected_root_count,
        "repair_a_selected_actual_rejecting_root_count": selected_rejecting_root_count,
        "actual_rejecting_occurrence_count": total,
        "angle_scalar_occurrences_without_exact_qbar_coercion": angle_unreachable,
        "pi_affine_occurrences_already_covered_by_repair_a_worker": pi_already_covered,
        "source_text_names_values_case_truth_or_results_emitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    arguments = parser.parse_args()
    payload = arguments.source.read_bytes()
    if hashlib.sha256(payload).hexdigest() != arguments.source_sha256:
        raise SystemExit("source hash mismatch")
    document = json.loads(payload)
    if not isinstance(document, Mapping):
        raise SystemExit("source root is not an object")
    print(json.dumps(scan(document), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
