#!/usr/bin/env python3
"""Aggregate-only static prevalence gate for area-quotient witnesses.

This is a gate scanner, not a solver arm.  It emits no paths, identifiers,
expressions, endpoints, targets, or individual outcomes.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from typing import Any, Mapping, Sequence


SCHEMA = "geotarget.barycentric-area-quotient-prevalence/v1"
APPROVED_RESULT_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results"
).resolve()
MAX_SOURCE_BYTES = 65_536
MAX_AST_NODES = 2_048
MAX_ENDPOINTS_PER_SOURCE = 64
MAX_RATIONAL_DENOMINATOR = 10_000
RATIONAL_TOLERANCE = 1.0e-10


class GateRejected(ValueError):
    pass


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def __add__(self, other):
        if not isinstance(other, Point):
            return NotImplemented
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        if not isinstance(other, Point):
            return NotImplemented
        return Point(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar):
        return Point(self.x * float(scalar), self.y * float(scalar))

    __rmul__ = __mul__

    def __truediv__(self, scalar):
        return Point(self.x / float(scalar), self.y / float(scalar))


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _approved_directory(path: Path) -> Path:
    if path.is_symlink():
        raise GateRejected("ROOT_IS_SYMLINK")
    resolved = path.resolve()
    try:
        resolved.relative_to(APPROVED_RESULT_ROOT)
    except ValueError as error:
        raise GateRejected("ROOT_OUTSIDE_APPROVED_RESULTS") from error
    if not resolved.is_dir():
        raise GateRejected("ROOT_NOT_DIRECTORY")
    return resolved


def _regular_json_files(root: Path) -> list[Path]:
    result = []
    for path in sorted(root.iterdir()):
        if path.is_symlink() or not path.is_file() or path.suffix != ".json":
            continue
        if stat.S_ISREG(path.lstat().st_mode):
            result.append(path)
    return result


def _call_name(node: ast.AST) -> str | None:
    return node.func.id if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else None


def _strip_scalar_shell(node: ast.AST) -> ast.AST:
    while isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        node = node.operand
    if isinstance(node, ast.Call) and _call_name(node) == "abs" and len(node.args) == 1:
        return _strip_scalar_shell(node.args[0])
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        left_area = any(_call_name(item) == "Area" for item in ast.walk(node.left))
        right_area = any(_call_name(item) == "Area" for item in ast.walk(node.right))
        if left_area and not right_area:
            return _strip_scalar_shell(node.left)
        if right_area and not left_area:
            return _strip_scalar_shell(node.right)
    return node


def _area_call(node: ast.AST) -> ast.Call | None:
    node = _strip_scalar_shell(node)
    return node if isinstance(node, ast.Call) and _call_name(node) == "Area" else None


def _direct_name_arguments(node: ast.Call) -> tuple[str, ...] | None:
    names = tuple(item.id for item in node.args if isinstance(item, ast.Name))
    return names if len(names) == len(node.args) else None


def _signature(area: ast.Call, *, direct: bool) -> str:
    width = len(area.args)
    if direct and width == 3:
        return "DIRECT_TRIANGLE_AREA"
    if direct and width > 3:
        return "DIRECT_POLYGON_AREA"
    if width == 3:
        return "COMPOSITE_TRIANGLE_AREA"
    return "COMPOSITE_POLYGON_AREA"


def _quotients(document: Mapping[str, Any]) -> list[tuple[ast.Call, str]]:
    answer = document.get("answer")
    if (
        document.get("task") != "solve"
        or document.get("post_process", "") not in (None, "")
        or not isinstance(answer, str)
        or len(answer) > 8_192
    ):
        return []
    try:
        root = ast.parse(answer, mode="eval")
    except (SyntaxError, ValueError):
        return []
    if sum(1 for _ in ast.walk(root)) > MAX_AST_NODES:
        return []
    result: list[tuple[ast.Call, str]] = []
    direct_node = _strip_scalar_shell(root.body)
    for node in ast.walk(root):
        if isinstance(node, ast.Call) and _call_name(node) == "Area" and len(node.args) >= 3:
            result.append((node, _signature(node, direct=node is direct_node)))
    return result


def _area(points: Sequence[Point]) -> float:
    if len(points) < 3 or not all(isinstance(point, Point) for point in points):
        raise GateRejected("AREA_ARGUMENTS_UNSUPPORTED")
    twice = sum(
        point.x * points[(index + 1) % len(points)].y
        - point.y * points[(index + 1) % len(points)].x
        for index, point in enumerate(points)
    )
    return abs(twice) / 2.0


class NumericAreaRuntime:
    def __init__(self, document: Mapping[str, Any], endpoint: Sequence[float]):
        names = document.get("variables", {}).get("names")
        if not isinstance(names, list) or len(names) != len(endpoint):
            raise GateRejected("ENDPOINT_DIMENSION_MISMATCH")
        self.document = document
        self.context: dict[str, Any] = {
            **dict(zip(names, map(float, endpoint), strict=True)),
            "pi": math.pi,
        }

    def eval(self, node: ast.AST):
        if isinstance(node, ast.Constant) and not isinstance(node.value, bool):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise GateRejected("LITERAL_UNSUPPORTED")
        if isinstance(node, ast.Name) and node.id in self.context:
            return self.context[node.id]
        if isinstance(node, ast.Attribute):
            value = self.eval(node.value)
            if isinstance(value, Point) and node.attr in {"x", "y"}:
                return getattr(value, node.attr)
            raise GateRejected("ATTRIBUTE_UNSUPPORTED")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = self.eval(node.operand)
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
                if abs(float(right)) <= 1.0e-14:
                    raise GateRejected("DIVISION_NEAR_ZERO")
                return left / right
            if isinstance(node.op, ast.Pow):
                return left**right
            raise GateRejected("BINARY_OPERATOR_UNSUPPORTED")
        if isinstance(node, (ast.Tuple, ast.List)):
            return tuple(self.eval(item) for item in node.elts)
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            raise GateRejected("CALL_UNSUPPORTED")
        name = node.func.id
        args = [self.eval(item) for item in node.args]
        if name == "Point" and len(args) == 2:
            return Point(float(args[0]), float(args[1]))
        if name in {"Midpoint", "MidPoint"} and len(args) == 2:
            return (args[0] + args[1]) / 2.0
        if name == "PointOnSegment" and len(args) == 3:
            return args[0] + (args[1] - args[0]) * float(args[2])
        if name == "Centroid" and args:
            points = args[0] if len(args) == 1 and isinstance(args[0], tuple) else args
            return sum(points[1:], points[0]) / float(len(points))
        if name == "Area":
            return _area(args)
        if name == "Distance" and len(args) == 2 and all(isinstance(item, Point) for item in args):
            return math.hypot(args[0].x - args[1].x, args[0].y - args[1].y)
        if name == "abs" and len(args) == 1:
            return abs(args[0])
        if name == "sqrt" and len(args) == 1 and args[0] >= 0:
            return math.sqrt(args[0])
        raise GateRejected("DSL_PRIMITIVE_UNSUPPORTED")

    def build(self) -> None:
        for item in self.document.get("construction", ()):
            self.context[str(item["name"])] = self.eval(
                ast.parse(str(item["expr"]), mode="eval").body
            )


def _rational_activation(
    document: Mapping[str, Any], endpoint: Sequence[float], quotient_nodes: Sequence[ast.Call]
) -> bool:
    try:
        runtime = NumericAreaRuntime(document, endpoint)
        runtime.build()
        for node in quotient_nodes:
            value = float(runtime.eval(node))
            if not math.isfinite(value):
                continue
            rational = Fraction(value).limit_denominator(MAX_RATIONAL_DENOMINATOR)
            if abs(value - float(rational)) <= RATIONAL_TOLERANCE * max(1.0, abs(value)):
                return True
    except (GateRejected, KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError):
        return False
    return False


def _endpoint_map(artifact_root: Path) -> dict[str, list[tuple[float, ...]]]:
    result: dict[str, list[tuple[float, ...]]] = {}
    for case_root in sorted(artifact_root.iterdir()):
        if case_root.is_symlink() or not case_root.is_dir():
            continue
        result_path = case_root / "RESULT.json"
        if result_path.is_symlink() or not result_path.is_file():
            continue
        try:
            terminal = json.loads(result_path.read_bytes())
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        source_sha = terminal.get("source_sha256") if isinstance(terminal, Mapping) else None
        if not isinstance(source_sha, str) or len(source_sha) != 64:
            continue
        endpoints = result.setdefault(source_sha, [])
        for plan_path in sorted(case_root.glob("reservoir-batch-*/hp/*/PLAN.json")):
            if len(endpoints) >= MAX_ENDPOINTS_PER_SOURCE:
                break
            if plan_path.is_symlink() or not plan_path.is_file():
                continue
            try:
                plan = json.loads(plan_path.read_bytes())
                endpoint = tuple(float(value) for value in plan["endpoint"])
            except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            if endpoint and all(math.isfinite(value) for value in endpoint):
                endpoints.append(endpoint)
    return result


def scan(source_root: Path, artifact_root: Path) -> dict[str, Any]:
    source_root = _approved_directory(source_root)
    artifact_root = _approved_directory(artifact_root)
    endpoints = _endpoint_map(artifact_root)
    scanned = matched = activated = malformed = 0
    signature_counts: dict[str, int] = {}
    activated_signature_counts: dict[str, int] = {}
    for source_path in _regular_json_files(source_root):
        payload = source_path.read_bytes()
        if len(payload) > MAX_SOURCE_BYTES:
            malformed += 1
            continue
        try:
            document = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            malformed += 1
            continue
        if not isinstance(document, Mapping):
            malformed += 1
            continue
        scanned += 1
        quotients = _quotients(document)
        if not quotients:
            continue
        matched += 1
        source_signatures = sorted({signature for _node, signature in quotients})
        for signature in source_signatures:
            signature_counts[signature] = signature_counts.get(signature, 0) + 1
        source_sha = _sha256(payload)
        quotient_nodes = [node for node, _signature_name in quotients]
        active = any(
            _rational_activation(document, endpoint, quotient_nodes)
            for endpoint in endpoints.get(source_sha, ())
        )
        if active:
            activated += 1
            for signature in source_signatures:
                activated_signature_counts[signature] = (
                    activated_signature_counts.get(signature, 0) + 1
                )
    signature_count = sum(count > 0 for count in signature_counts.values())
    decision = (
        "GO_IMPLEMENTATION"
        if matched >= 6 and signature_count >= 2 and activated >= 4
        else "STOP_PREVALENCE_GATE"
    )
    return {
        "schema_version": SCHEMA,
        "source_count_scanned": scanned,
        "malformed_or_resource_rejected_count": malformed,
        "static_area_quotient_source_count": matched,
        "static_signature_count": signature_count,
        "static_signature_counts": dict(sorted(signature_counts.items())),
        "endpoint_rational_area_activation_source_count": activated,
        "endpoint_activation_signature_counts": dict(
            sorted(activated_signature_counts.items())
        ),
        "static_source_gate_required": 6,
        "static_signature_gate_required": 2,
        "endpoint_activation_gate_required": 4,
        "individual_records_paths_ids_expressions_endpoints_targets_emitted": False,
        "truth_score_outcome_used": False,
        "authority_pass": False,
        "target_release": False,
        "decision": decision,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = scan(arguments.source_root, arguments.artifact_root)
    output_root = _approved_directory(arguments.output.parent)
    output = (output_root / arguments.output.name).resolve()
    if output.parent != output_root or output.suffix != ".json":
        raise GateRejected("OUTPUT_PATH_MALFORMED")
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
