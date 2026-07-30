"""Aggregate-only static interval-gate audit over formulation bytes.

The reader projects only solver-visible formulation fields.  Identity, answer,
truth, Gold, scorer, and every unknown field value are skipped lexically and
are never passed to a JSON decoder.  No case-level record is returned.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys
from typing import Any, Callable, Iterable, Mapping


HERE = Path(__file__).resolve().parent
DEFAULT_FORMULATIONS = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/results/"
    "current-baseline-development145-180s-seed0-20260722-v2/inputs"
)

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from interval_rescue import Const, Expr, Problem, RescueConfig, Var, applicability  # noqa: E402


Decoder = Callable[[bytes], Any]
_WHITESPACE = frozenset(b" \t\r\n")
_HEX = frozenset(b"0123456789abcdefABCDEF")
_SCALAR_CONSTANTS = {"pi": math.pi, "e": math.e}
_TRANSCENDENTAL = {
    "acos",
    "asin",
    "atan",
    "atan2",
    "cos",
    "exp",
    "log",
    "sin",
    "sqrt",
    "tan",
}
_NONSMOOTH = {"Abs", "Max", "Min", "abs", "max", "min"}


class ProjectionError(ValueError):
    """Malformed formulation bytes at the safe projection boundary."""


class TranslationError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _space(payload: bytes, index: int) -> int:
    while index < len(payload) and payload[index] in _WHITESPACE:
        index += 1
    return index


def _string_end(payload: bytes, index: int) -> int:
    if index >= len(payload) or payload[index] != ord('"'):
        raise ProjectionError("JSON string expected")
    index += 1
    while index < len(payload):
        byte = payload[index]
        if byte == ord('"'):
            return index + 1
        if byte < 0x20:
            raise ProjectionError("control byte in JSON string")
        if byte == ord("\\"):
            index += 1
            if index >= len(payload):
                raise ProjectionError("truncated JSON escape")
            escaped = payload[index]
            if escaped == ord("u"):
                if index + 4 >= len(payload) or any(
                    item not in _HEX for item in payload[index + 1 : index + 5]
                ):
                    raise ProjectionError("invalid JSON unicode escape")
                index += 4
            elif escaped not in b'"\\/bfnrt':
                raise ProjectionError("invalid JSON escape")
        index += 1
    raise ProjectionError("unterminated JSON string")


def _value_end(payload: bytes, index: int) -> int:
    index = _space(payload, index)
    if index >= len(payload):
        raise ProjectionError("JSON value expected")
    first = payload[index]
    if first == ord('"'):
        return _string_end(payload, index)
    if first == ord("{"):
        cursor = _space(payload, index + 1)
        if cursor < len(payload) and payload[cursor] == ord("}"):
            return cursor + 1
        while True:
            cursor = _string_end(payload, cursor)
            cursor = _space(payload, cursor)
            if cursor >= len(payload) or payload[cursor] != ord(":"):
                raise ProjectionError("JSON object colon expected")
            cursor = _value_end(payload, cursor + 1)
            cursor = _space(payload, cursor)
            if cursor >= len(payload):
                raise ProjectionError("unterminated JSON object")
            if payload[cursor] == ord("}"):
                return cursor + 1
            if payload[cursor] != ord(","):
                raise ProjectionError("JSON object comma expected")
            cursor = _space(payload, cursor + 1)
    if first == ord("["):
        cursor = _space(payload, index + 1)
        if cursor < len(payload) and payload[cursor] == ord("]"):
            return cursor + 1
        while True:
            cursor = _value_end(payload, cursor)
            cursor = _space(payload, cursor)
            if cursor >= len(payload):
                raise ProjectionError("unterminated JSON array")
            if payload[cursor] == ord("]"):
                return cursor + 1
            if payload[cursor] != ord(","):
                raise ProjectionError("JSON array comma expected")
            cursor = _space(payload, cursor + 1)
    for literal in (b"true", b"false", b"null"):
        if payload.startswith(literal, index):
            return index + len(literal)
    cursor = index
    while cursor < len(payload) and payload[cursor] not in b" \t\r\n,]}":
        cursor += 1
    if cursor == index:
        raise ProjectionError("invalid JSON scalar")
    return cursor


def _decode(payload: bytes, start: int, end: int, decoder: Decoder) -> Any:
    return decoder(payload[start:end])


def _object_slices(payload: bytes, start: int, end: int, decoder: Decoder):
    cursor = _space(payload, start)
    if cursor >= end or payload[cursor] != ord("{"):
        raise ProjectionError("JSON object expected")
    cursor = _space(payload, cursor + 1)
    if cursor < end and payload[cursor] == ord("}"):
        return
    while cursor < end:
        key_start = cursor
        key_end = _string_end(payload, key_start)
        key = _decode(payload, key_start, key_end, decoder)
        if not isinstance(key, str):
            raise ProjectionError("JSON key is not a string")
        cursor = _space(payload, key_end)
        if cursor >= end or payload[cursor] != ord(":"):
            raise ProjectionError("JSON object colon expected")
        value_start = _space(payload, cursor + 1)
        value_end = _value_end(payload, value_start)
        yield key, value_start, value_end
        cursor = _space(payload, value_end)
        if cursor >= end:
            raise ProjectionError("unterminated JSON object")
        if payload[cursor] == ord("}"):
            if cursor + 1 != end:
                raise ProjectionError("trailing bytes after JSON object")
            return
        if payload[cursor] != ord(","):
            raise ProjectionError("JSON object comma expected")
        cursor = _space(payload, cursor + 1)
    raise ProjectionError("unterminated JSON object")


def _array_slices(payload: bytes, start: int, end: int):
    cursor = _space(payload, start)
    if cursor >= end or payload[cursor] != ord("["):
        raise ProjectionError("JSON array expected")
    cursor = _space(payload, cursor + 1)
    if cursor < end and payload[cursor] == ord("]"):
        return
    while cursor < end:
        value_start = cursor
        value_end = _value_end(payload, value_start)
        yield value_start, value_end
        cursor = _space(payload, value_end)
        if cursor >= end:
            raise ProjectionError("unterminated JSON array")
        if payload[cursor] == ord("]"):
            if cursor + 1 != end:
                raise ProjectionError("trailing bytes after JSON array")
            return
        if payload[cursor] != ord(","):
            raise ProjectionError("JSON array comma expected")
        cursor = _space(payload, cursor + 1)
    raise ProjectionError("unterminated JSON array")


def _project_object(
    payload: bytes,
    start: int,
    end: int,
    allowed: frozenset[str],
    decoder: Decoder,
) -> dict[str, tuple[int, int]]:
    selected: dict[str, tuple[int, int]] = {}
    for key, value_start, value_end in _object_slices(payload, start, end, decoder):
        if key in allowed:
            if key in selected:
                raise ProjectionError(f"duplicate selected key {key}")
            selected[key] = (value_start, value_end)
    return selected


def _decode_string_array(payload: bytes, span: tuple[int, int], decoder: Decoder) -> list[str]:
    values = []
    for start, end in _array_slices(payload, *span):
        value = _decode(payload, start, end, decoder)
        if not isinstance(value, str):
            raise ProjectionError("string array contains a non-string")
        values.append(value)
    return values


def project_formulation(payload: bytes, decoder: Decoder = json.loads) -> dict[str, object]:
    """Project allowed formulation fields without decoding skipped values."""

    root_start = _space(payload, 0)
    root_end = _value_end(payload, root_start)
    if _space(payload, root_end) != len(payload):
        raise ProjectionError("trailing formulation bytes")
    root = _project_object(
        payload,
        root_start,
        root_end,
        frozenset({"task", "variables", "bounds", "construction", "constraints", "guards"}),
        decoder,
    )
    projected: dict[str, object] = {}
    if "task" in root:
        task = _decode(payload, *root["task"], decoder)
        if not isinstance(task, str):
            raise ProjectionError("task must be a string")
        projected["task"] = task
    variables_span = root.get("variables")
    if variables_span is not None:
        variables = _project_object(
            payload, *variables_span, frozenset({"names"}), decoder
        )
        if "names" in variables:
            projected["variables"] = {
                "names": _decode_string_array(payload, variables["names"], decoder)
            }
    if "bounds" in root:
        bounds = _decode(payload, *root["bounds"], decoder)
        if bounds is not None and not isinstance(bounds, list):
            raise ProjectionError("bounds must be an array or null")
        projected["bounds"] = bounds

    construction: list[dict[str, object]] = []
    if "construction" in root:
        for start, end in _array_slices(payload, *root["construction"]):
            item = _project_object(
                payload, start, end, frozenset({"name", "expr"}), decoder
            )
            decoded = {
                key: _decode(payload, *span, decoder) for key, span in item.items()
            }
            construction.append(decoded)
    projected["construction"] = construction

    constraints: list[object] = []
    if "constraints" in root:
        for start, end in _array_slices(payload, *root["constraints"]):
            first = payload[_space(payload, start)]
            if first == ord("{"):
                item = _project_object(
                    payload, start, end, frozenset({"def", "value"}), decoder
                )
                constraints.append(
                    {key: _decode(payload, *span, decoder) for key, span in item.items()}
                )
            else:
                constraints.append(_decode(payload, start, end, decoder))
    projected["constraints"] = constraints
    projected["guards"] = (
        _decode_string_array(payload, root["guards"], decoder)
        if "guards" in root
        else []
    )
    return projected


def _expression_texts(document: Mapping[str, object]) -> Iterable[str]:
    for item in document.get("construction", []):
        if isinstance(item, Mapping) and isinstance(item.get("expr"), str):
            yield item["expr"]
    for item in document.get("constraints", []):
        if isinstance(item, str):
            yield item
        elif isinstance(item, Mapping):
            for key in ("def", "value"):
                value = item.get(key)
                if isinstance(value, str):
                    yield value
    for item in document.get("guards", []):
        if isinstance(item, str):
            yield item


def _call_name(node: ast.Call) -> str | None:
    return node.func.id if isinstance(node.func, ast.Name) else None


def expression_taxonomy(document: Mapping[str, object]) -> tuple[Counter[str], set[str], int]:
    occurrences: Counter[str] = Counter()
    exposures: set[str] = set()
    total_nodes = 0
    for source in _expression_texts(document):
        try:
            tree = ast.parse(source, mode="eval")
        except (SyntaxError, ValueError):
            occurrences["parse-failure"] += 1
            exposures.add("parse-failure")
            continue
        for node in ast.walk(tree):
            total_nodes += 1
            category: str | None = None
            if isinstance(node, ast.Add):
                category = "arithmetic-add"
            elif isinstance(node, ast.Sub):
                category = "arithmetic-sub"
            elif isinstance(node, ast.Mult):
                category = "arithmetic-mul"
            elif isinstance(node, ast.Div):
                category = "arithmetic-div"
            elif isinstance(node, ast.Pow):
                category = "arithmetic-pow"
            elif isinstance(node, ast.Call):
                name = _call_name(node)
                if name in _TRANSCENDENTAL:
                    category = "transcendental-call"
                elif name in _NONSMOOTH:
                    category = "nonsmooth-call"
                else:
                    category = "geometry-or-opaque-call"
            elif isinstance(node, (ast.Compare, ast.BoolOp, ast.IfExp)):
                category = "branch-or-comparison"
            elif isinstance(node, (ast.Attribute, ast.Lambda, ast.Subscript)):
                category = "opaque-syntax"
            if category is not None:
                occurrences[category] += 1
                exposures.add(category)
    return occurrences, exposures, total_nodes


def _scalar_source(value: object) -> str:
    if isinstance(value, bool):
        raise TranslationError("unsupported-boolean-expression")
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return repr(float(value))
    if isinstance(value, str):
        return value
    raise TranslationError("unsupported-constraint-value")


class ScalarTranslator:
    def __init__(self, names: list[str], construction: list[object]) -> None:
        self.variables = {name: Var(index) for index, name in enumerate(names)}
        self.sources: dict[str, str] = {}
        for item in construction:
            if not isinstance(item, Mapping):
                raise TranslationError("malformed-construction")
            name, source = item.get("name"), item.get("expr")
            if not isinstance(name, str) or not isinstance(source, str) or name in self.sources:
                raise TranslationError("malformed-construction")
            self.sources[name] = source
        self.cache: dict[str, Expr] = {}
        self.active: set[str] = set()
        self.closure_nodes = 0

    def translate_source(self, source: str) -> Expr:
        try:
            tree = ast.parse(source, mode="eval")
        except (SyntaxError, ValueError) as error:
            raise TranslationError("unsupported-expression-parse") from error
        self.closure_nodes += sum(1 for _ in ast.walk(tree))
        return self._node(tree.body)

    def _resolve(self, name: str) -> Expr:
        if name in self.variables:
            return self.variables[name]
        if name in _SCALAR_CONSTANTS:
            return Const(_SCALAR_CONSTANTS[name])
        if name in self.cache:
            return self.cache[name]
        source = self.sources.get(name)
        if source is None:
            raise TranslationError("unsupported-unresolved-symbol")
        if name in self.active:
            raise TranslationError("unsupported-construction-cycle")
        self.active.add(name)
        try:
            value = self.translate_source(source)
        finally:
            self.active.remove(name)
        self.cache[name] = value
        return value

    def _node(self, node: ast.AST) -> Expr:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise TranslationError("unsupported-literal")
            value = float(node.value)
            if not math.isfinite(value):
                raise TranslationError("unsupported-nonfinite-literal")
            return Const(value)
        if isinstance(node, ast.Name):
            return self._resolve(node.id)
        if isinstance(node, ast.UnaryOp):
            value = self._node(node.operand)
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.UAdd):
                return value
            raise TranslationError("unsupported-unary-op")
        if isinstance(node, ast.BinOp):
            left = self._node(node.left)
            right = self._node(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                if not isinstance(node.right, ast.Constant) or isinstance(node.right.value, bool):
                    raise TranslationError("unsupported-power")
                exponent = node.right.value
                if not isinstance(exponent, int) or not 0 <= exponent <= 6:
                    raise TranslationError("unsupported-power")
                return left**exponent
            raise TranslationError("unsupported-binary-op")
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in _TRANSCENDENTAL:
                raise TranslationError("unsupported-transcendental-op")
            if name in _NONSMOOTH:
                raise TranslationError("unsupported-nonsmooth-op")
            raise TranslationError("unsupported-geometry-or-opaque-op")
        if isinstance(node, (ast.Compare, ast.BoolOp, ast.IfExp)):
            raise TranslationError("unsupported-branch-or-comparison")
        raise TranslationError("unsupported-expression-node")


def _bounds(document: Mapping[str, object], dimension: int) -> tuple[str, tuple[tuple[float, float], ...] | None]:
    raw = document.get("bounds")
    if raw is None:
        return "absent", None
    if not isinstance(raw, list) or len(raw) != dimension:
        return "malformed", None
    bounds = []
    for pair in raw:
        if not isinstance(pair, list) or len(pair) != 2:
            return "malformed", None
        try:
            lower, upper = float(pair[0]), float(pair[1])
        except (TypeError, ValueError):
            return "malformed", None
        if not (math.isfinite(lower) and math.isfinite(upper) and lower < upper):
            return "malformed", None
        bounds.append((lower, upper))
    return "finite-ordered", tuple(bounds)


def _dimension_band(dimension: int) -> str:
    if dimension <= 0:
        return "0"
    if dimension <= 2:
        return str(dimension)
    if dimension <= 4:
        return "3-4"
    if dimension <= 8:
        return "5-8"
    return "9+"


@dataclass(frozen=True)
class StaticDecision:
    accepted: bool
    reason: str
    dimension: int
    residual_dimension: int
    bound_class: str
    maximum_width: float | None
    volume: float | None
    closure_nodes: int


def static_decision(
    document: Mapping[str, object],
    config: RescueConfig = RescueConfig(),
) -> StaticDecision:
    variables = document.get("variables")
    names = variables.get("names") if isinstance(variables, Mapping) else None
    constraints = document.get("constraints")
    if document.get("task") != "solve" or not isinstance(names, list):
        return StaticDecision(False, "malformed-formulation", -1, -1, "unknown", None, None, 0)
    dimension = len(names)
    residual_dimension = len(constraints) if isinstance(constraints, list) else -1
    bound_class, bounds = _bounds(document, dimension)
    maximum_width = max((upper - lower for lower, upper in bounds), default=None) if bounds else None
    volume = math.prod(upper - lower for lower, upper in bounds) if bounds else None
    if not 1 <= dimension <= config.max_dimension:
        reason = "dimension-outside-cap"
    elif residual_dimension != dimension:
        reason = "nonsquare-system"
    elif bounds is None:
        reason = "explicit-finite-bounds-unavailable"
    elif maximum_width is None or maximum_width > config.max_box_width:
        reason = "box-width-cap"
    elif volume is None or volume > config.max_box_volume:
        reason = "box-volume-cap"
    elif document.get("guards"):
        reason = "strict-guard-interior-not-proved"
    else:
        try:
            translator = ScalarTranslator(names, list(document.get("construction", [])))
            residuals = []
            assert isinstance(constraints, list)
            for item in constraints:
                if isinstance(item, Mapping):
                    left = translator.translate_source(_scalar_source(item.get("def")))
                    right = translator.translate_source(_scalar_source(item.get("value", 0)))
                else:
                    left = translator.translate_source(_scalar_source(item))
                    right = Const(0.0)
                residuals.append(left - right)
            gate = applicability(Problem(tuple(residuals), bounds), config)
            reason = "applicable" if gate.applicable else gate.reason
            return StaticDecision(
                gate.applicable,
                reason,
                dimension,
                residual_dimension,
                bound_class,
                maximum_width,
                volume,
                translator.closure_nodes,
            )
        except TranslationError as error:
            reason = error.reason
    return StaticDecision(
        False,
        reason,
        dimension,
        residual_dimension,
        bound_class,
        maximum_width,
        volume,
        0,
    )


def _closure_digest(count: int, total_bytes: int, xor_value: int, sum_value: int) -> str:
    payload = struct.pack(">QQ", count, total_bytes) + xor_value.to_bytes(32, "big") + sum_value.to_bytes(32, "big")
    return hashlib.sha256(payload).hexdigest()


def audit_directory(
    directory: Path,
    *,
    expected_count: int = 145,
    config: RescueConfig = RescueConfig(),
) -> dict[str, object]:
    """Return corpus aggregates only; never construct a case row or ID list."""

    if not directory.is_dir():
        raise ProjectionError("formulation directory is unavailable")
    rejection: Counter[str] = Counter()
    dimensions: Counter[str] = Counter()
    residual_dimensions: Counter[str] = Counter()
    bound_classes: Counter[str] = Counter()
    width_bands: Counter[str] = Counter()
    volume_bands: Counter[str] = Counter()
    op_occurrences: Counter[str] = Counter()
    op_case_exposures: Counter[str] = Counter()
    count = total_bytes = xor_value = sum_value = eligible_closure_nodes = 0

    with os.scandir(directory) as entries:
        for entry in entries:
            if not entry.is_file(follow_symlinks=False) or not entry.name.endswith(".json"):
                continue
            with open(entry.path, "rb") as handle:
                payload = handle.read()
            digest = int.from_bytes(hashlib.sha256(payload).digest(), "big")
            count += 1
            total_bytes += len(payload)
            xor_value ^= digest
            sum_value = (sum_value + digest) % (1 << 256)
            document = project_formulation(payload)
            occurrences, exposures, _nodes = expression_taxonomy(document)
            op_occurrences.update(occurrences)
            op_case_exposures.update(exposures)
            decision = static_decision(document, config)
            rejection[decision.reason] += 1
            dimensions[_dimension_band(decision.dimension)] += 1
            residual_dimensions[_dimension_band(decision.residual_dimension)] += 1
            bound_classes[decision.bound_class] += 1
            if decision.maximum_width is not None:
                width_bands[
                    "<=1" if decision.maximum_width <= 1 else "(1,4]" if decision.maximum_width <= 4 else ">4"
                ] += 1
            if decision.volume is not None:
                volume_bands["<=16" if decision.volume <= 16 else ">16"] += 1
            if decision.accepted:
                eligible_closure_nodes += decision.closure_nodes

    if count != expected_count:
        raise ProjectionError(f"expected {expected_count} formulation files, observed {count}")
    activated = rejection.pop("applicable", 0)
    maximum_dual_evaluations = activated * config.max_boxes * 3
    return {
        "schema": "geotarget.exp-interval-001-formulation-aggregate/v1",
        "scope": {
            "partition": "development",
            "formulation_count": count,
            "formulation_bytes": total_bytes,
            "gate_mechanism_sha256": hashlib.sha256(
                (HERE / "interval_rescue.py").read_bytes()
            ).hexdigest(),
            "audit_mechanism_sha256": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
            "order_and_filename_independent_closure_sha256": _closure_digest(
                count, total_bytes, xor_value, sum_value
            ),
            "individual_case_records_emitted": 0,
            "case_identity_values_deserialized": 0,
            "truth_gold_answer_scorer_values_deserialized": 0,
            "manifest_or_outer_dataset_opened": False,
            "formal_solver_run": False,
        },
        "activation": {
            "applicable": activated,
            "rejected": count - activated,
            "activation_rate": activated / count,
            "rejection_taxonomy": dict(sorted(rejection.items())),
        },
        "distribution": {
            "dimension_bands": dict(sorted(dimensions.items())),
            "residual_dimension_bands": dict(sorted(residual_dimensions.items())),
            "bound_classes": dict(sorted(bound_classes.items())),
            "maximum_width_bands": dict(sorted(width_bands.items())),
            "box_volume_bands": dict(sorted(volume_bands.items())),
            "expression_op_occurrences": dict(sorted(op_occurrences.items())),
            "expression_op_case_exposures": dict(sorted(op_case_exposures.items())),
        },
        "estimated_cap_cost": {
            "model": "static upper bound; no residual evaluation or solver execution",
            "per_applicable_case_box_cap": config.max_boxes,
            "per_applicable_case_dual_dag_evaluation_cap": config.max_boxes * 3,
            "per_applicable_case_proposal_cap": config.max_proposals,
            "per_applicable_case_wall_seconds_cap": config.max_seconds,
            "maximum_boxes": activated * config.max_boxes,
            "maximum_dual_dag_evaluations": maximum_dual_evaluations,
            "maximum_interval_proposals": activated * config.max_proposals,
            "maximum_route_wall_seconds": activated * config.max_seconds,
            "maximum_expression_node_visits": eligible_closure_nodes * config.max_boxes * 3,
            "minimum_baseline_fraction": config.minimum_baseline_fraction,
            "minimum_baseline_slots_per_applicable_case": math.ceil(
                config.total_launch_slots * config.minimum_baseline_fraction
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formulations", type=Path, default=DEFAULT_FORMULATIONS)
    parser.add_argument("--expected-count", type=int, default=145)
    arguments = parser.parse_args()
    result = audit_directory(
        arguments.formulations.resolve(), expected_count=arguments.expected_count
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
