"""Disposable target-only numerical authority for success policy v3.

The lane deliberately stops at numerical configuration validation plus a
scalar algebraic target descriptor.  It never attempts exact coordinate
recovery, a common primitive element, completeness, or any CAS-backed
full-configuration replay.

Runtime seam
------------
``build_target_evidence(source_payload, compiled_evaluator, approximate)``
expects the already-compiled evaluator to expose ``new_lane(bits, lane_id)``.
Each returned lane must be a fresh object with matching ``bits`` and
``lane_id`` attributes and two methods:

* ``refine(start) -> {"coordinates": sequence, "method": str,
  "iterations": int}``
* ``replay(coordinates) -> numerical replay mapping``

The existing refinement bridge can implement that small seam with its
independent 512/768/1024 ``_lane`` calls and compiled IR evaluator.  This
module owns only the v3 acceptance gates and reuses the repository-owned PSLQ
implementation unchanged.
"""

from __future__ import annotations

import ast
from dataclasses import asdict
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from math import gcd
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

from mpmath import mp


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
POLICY_PATH = HERE.parent / "NUMERICAL_SUCCESS_POLICY_V3.json"
OWNED_PSLQ_PATH = (
    ROOT
    / "research"
    / "experiments"
    / "EXP-REAL61-003"
    / "owned_pslq"
    / "owned_pslq.py"
)
NUMERICAL_SEMANTICS_PATH = (
    HERE.parent / "minimal_numerical_180_worker" / "numerical_semantics.py"
)

SCHEMA_VERSION = "geotarget.target-only-numerical-authority/v1"
POLICY_SCHEMA = "geotarget.real61-numerical-success-policy/v3"
with mp.workprec(512):
    NUMERIC_GATE = +mp.mpf("1e-100")
SOURCE_CAP_BYTES = 256 * 1024
PSLQ_MAX_STEPS = 20_000
PSLQ_INCUMBENT_CAP_BITS = 34
PSLQ_FALLBACK_CAP_BITS = (64, 128, 256)
PSLQ_SOURCE_SCALE_MAXIMUM = 16
PSLQ_OUTPUT_COEFFICIENT_BITS_MAXIMUM = 4096
PSLQ_CONTRACT_DECIMAL_DIGITS = 100
PSLQ_CONTRACT_GUARD_BITS = 8
PSLQ_RELATION_TOLERANCE_BITS = (
    math.ceil(PSLQ_CONTRACT_DECIMAL_DIGITS * math.log2(10))
    + PSLQ_CONTRACT_GUARD_BITS
)
RATIONAL_POINT_INTERVAL_RADIUS = Fraction(2, 10**PSLQ_CONTRACT_DECIMAL_DIGITS)
FORBIDDEN_RUNTIME_KEYS = {
    "case_id",
    "family",
    "gold",
    "known_target_count",
    "known_targets",
    "expected_target_count",
    "truth",
    "truth_targets",
}


class NumericalAuthorityError(ValueError):
    """Fail-closed v3 rejection with one stable failure class."""

    def __init__(self, failure_class: str, detail: str = "") -> None:
        self.failure_class = failure_class
        super().__init__(failure_class if not detail else f"{failure_class}: {detail}")


def _load_owned_pslq():
    name = "geotarget_target_only_numerical_authority_owned_pslq"
    expected = OWNED_PSLQ_PATH.resolve()
    cached = sys.modules.get(name)
    if cached is not None:
        loaded = getattr(cached, "__file__", None)
        if loaded is None or Path(loaded).resolve() != expected:
            raise RuntimeError("owned PSLQ module path mismatch")
        return cached
    specification = importlib.util.spec_from_file_location(name, expected)
    if specification is None or specification.loader is None:
        raise RuntimeError("owned PSLQ module unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    loaded = getattr(module, "__file__", None)
    if loaded is None or Path(loaded).resolve() != expected:
        raise RuntimeError("owned PSLQ module loaded from wrong path")
    return module


OWNED_PSLQ = _load_owned_pslq()


def _load_numerical_semantics():
    name = "geotarget_target_only_numerical_authority_source_semantics"
    expected = NUMERICAL_SEMANTICS_PATH.resolve()
    cached = sys.modules.get(name)
    if cached is not None:
        loaded = getattr(cached, "__file__", None)
        if loaded is None or Path(loaded).resolve() != expected:
            raise RuntimeError("numerical semantics module path mismatch")
        return cached
    specification = importlib.util.spec_from_file_location(name, expected)
    if specification is None or specification.loader is None:
        raise RuntimeError("numerical semantics module unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    loaded = getattr(module, "__file__", None)
    if loaded is None or Path(loaded).resolve() != expected:
        raise RuntimeError("numerical semantics module loaded from wrong path")
    return module


NUMERICAL_SEMANTICS = _load_numerical_semantics()


def canonical_bytes(document: object) -> bytes:
    try:
        return json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise NumericalAuthorityError(
            "HIGH_PRECISION_REFINEMENT_FAILED", "non-canonical evidence"
        ) from error


def canonical_sha256(document: object) -> str:
    return hashlib.sha256(canonical_bytes(document)).hexdigest()


def raw_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def seal(document: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(document)
    result["artifact_sha256"] = canonical_sha256(result)
    return result


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise NumericalAuthorityError(
                "HIGH_PRECISION_REFINEMENT_FAILED", f"duplicate source key {key}"
            )
        result[key] = value
    return result


def _reject_nonfinite_constant(token: str) -> None:
    raise NumericalAuthorityError(
        "HIGH_PRECISION_REFINEMENT_FAILED", f"non-finite source constant {token}"
    )


def _strict_source(source_payload: bytes) -> dict[str, Any]:
    if (
        not isinstance(source_payload, bytes)
        or not source_payload
        or len(source_payload) > SOURCE_CAP_BYTES
    ):
        raise NumericalAuthorityError(
            "HIGH_PRECISION_REFINEMENT_FAILED", "source byte cap"
        )
    try:
        document = json.loads(
            source_payload,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_nonfinite_constant,
        )
    except NumericalAuthorityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise NumericalAuthorityError(
            "HIGH_PRECISION_REFINEMENT_FAILED", "source is not strict JSON"
        ) from error
    if not isinstance(document, dict):
        raise NumericalAuthorityError(
            "HIGH_PRECISION_REFINEMENT_FAILED", "source root is not an object"
        )

    def reject_runtime_metadata(value: object) -> None:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                if str(key).lower() in FORBIDDEN_RUNTIME_KEYS:
                    raise NumericalAuthorityError(
                        "HIGH_PRECISION_REFINEMENT_FAILED",
                        f"forbidden runtime metadata {key}",
                    )
                reject_runtime_metadata(nested)
        elif isinstance(value, list):
            for nested in value:
                reject_runtime_metadata(nested)

    reject_runtime_metadata(document)
    if document.get("task", "solve") != "solve":
        raise NumericalAuthorityError(
            "HIGH_PRECISION_REFINEMENT_FAILED", "solve task required"
        )
    return document


def _expression_tree(value: object, *, label: str) -> ast.Expression:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise NumericalAuthorityError(
            "HIGH_PRECISION_REFINEMENT_FAILED", f"malformed expression {label}"
        )
    try:
        tree = ast.parse(str(value), mode="eval")
    except SyntaxError as error:
        raise NumericalAuthorityError(
            "HIGH_PRECISION_REFINEMENT_FAILED", f"malformed expression {label}"
        ) from error
    return tree


def semantic_inventory(source: Mapping[str, Any]) -> dict[str, Any]:
    """Build the complete source-side replay inventory used by every lane."""

    variables = source.get("variables")
    names = variables.get("names") if isinstance(variables, Mapping) else None
    if not isinstance(names, list) or not all(
        isinstance(name, str) and name for name in names
    ):
        raise NumericalAuthorityError(
            "HIGH_PRECISION_REFINEMENT_FAILED", "source variables malformed"
        )
    construction = source.get("construction", [])
    constraints = source.get("constraints", [])
    guards = source.get("guards", [])
    if not all(
        isinstance(value, list) for value in (construction, constraints, guards)
    ):
        raise NumericalAuthorityError(
            "HIGH_PRECISION_REFINEMENT_FAILED", "semantic collection malformed"
        )

    construction_labels: list[str] = []
    constraint_labels: list[str] = []
    guard_labels: list[str] = []
    expressions: list[tuple[str, object]] = []
    for index, item in enumerate(construction):
        if not isinstance(item, Mapping) or "expr" not in item:
            raise NumericalAuthorityError(
                "HIGH_PRECISION_REFINEMENT_FAILED", "construction malformed"
            )
        label = f"construction[{index}]"
        construction_labels.append(label)
        expressions.append((label, item["expr"]))
    for index, item in enumerate(constraints):
        if not isinstance(item, Mapping) or "def" not in item:
            raise NumericalAuthorityError(
                "HIGH_PRECISION_REFINEMENT_FAILED", "constraint malformed"
            )
        label = f"constraints[{index}]"
        constraint_labels.append(label)
        expressions.append((f"{label}.def", item["def"]))
        expressions.append((f"{label}.value", item.get("value", 0)))
    for index, guard in enumerate(guards):
        label = f"guards[{index}]"
        guard_labels.append(label)
        expressions.append((label, guard))
    if "answer" not in source:
        raise NumericalAuthorityError(
            "HIGH_PRECISION_REFINEMENT_FAILED", "source answer absent"
        )
    expressions.append(("answer", source["answer"]))

    branch_entries: list[dict[str, Any]] = []
    for expression_label, expression in expressions:
        tree = _expression_tree(expression, label=expression_label)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Intersect"
                and (
                    len(node.args) >= 3
                    or any(
                        keyword.arg in {"exclude", "near", "far"}
                        for keyword in node.keywords
                    )
                )
            ):
                syntax = ast.dump(node, annotate_fields=True, include_attributes=False)
                branch_entries.append(
                    {
                        "label": (
                            f"branch:{expression_label}:"
                            f"{int(getattr(node, 'lineno', 0))}:"
                            f"{int(getattr(node, 'col_offset', 0))}:"
                            f"{raw_sha256(syntax.encode('utf-8'))}"
                        ),
                        "expression_label": expression_label,
                        "call_ast_sha256": raw_sha256(syntax.encode("utf-8")),
                    }
                )
    branch_entries.sort(key=lambda item: item["label"])

    bounds = source.get("bounds")
    bound_entries: list[dict[str, Any]] = []
    if bounds is not None:
        if not isinstance(bounds, list) or len(bounds) != len(names):
            raise NumericalAuthorityError(
                "HIGH_PRECISION_REFINEMENT_FAILED", "source bounds malformed"
            )
        for index, interval in enumerate(bounds):
            if interval is None:
                continue
            if isinstance(interval, list) and len(interval) == 2:
                lower, upper = interval
                lower_strict = upper_strict = False
            elif isinstance(interval, Mapping):
                lower, upper = interval.get("lower"), interval.get("upper")
                lower_strict = interval.get("lower_strict", False)
                upper_strict = interval.get("upper_strict", False)
                if not isinstance(lower_strict, bool) or not isinstance(
                    upper_strict, bool
                ):
                    raise NumericalAuthorityError(
                        "HIGH_PRECISION_REFINEMENT_FAILED", "bound strictness malformed"
                    )
            else:
                raise NumericalAuthorityError(
                    "HIGH_PRECISION_REFINEMENT_FAILED", "source bounds malformed"
                )
            if lower is not None:
                bound_entries.append(
                    {
                        "label": f"bounds[{index}].lower",
                        "strict": lower_strict,
                    }
                )
            if upper is not None:
                bound_entries.append(
                    {
                        "label": f"bounds[{index}].upper",
                        "strict": upper_strict,
                    }
                )
    try:
        intrinsic_entries = NUMERICAL_SEMANTICS.intrinsic_domain_bound_entries(source)
    except ValueError as error:
        raise NumericalAuthorityError(
            "HIGH_PRECISION_REFINEMENT_FAILED",
            "intrinsic primitive domain inventory malformed",
        ) from error
    bound_entries.extend(dict(entry) for entry in intrinsic_entries)

    inventory = {
        "variables": list(names),
        "construction_labels": construction_labels,
        "constraint_labels": constraint_labels,
        "guard_labels": guard_labels,
        "branch_entries": branch_entries,
        "bound_entries": bound_entries,
        "answer_label": "answer",
    }
    return {**inventory, "inventory_sha256": canonical_sha256(inventory)}


def _as_mapping(value: object, *, detail: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise NumericalAuthorityError("HIGH_PRECISION_REFINEMENT_FAILED", detail)
    return value


def _as_sequence(value: object, *, detail: str) -> Sequence[Any]:
    if not isinstance(value, (list, tuple)):
        raise NumericalAuthorityError("HIGH_PRECISION_REFINEMENT_FAILED", detail)
    return value


def _mp_value(value: object, *, failure_class: str, detail: str):
    if isinstance(value, bool):
        raise NumericalAuthorityError(failure_class, detail)
    try:
        parsed = mp.mpf(value)
    except (TypeError, ValueError) as error:
        raise NumericalAuthorityError(failure_class, detail) from error
    if not mp.isfinite(parsed):
        raise NumericalAuthorityError(failure_class, detail)
    return parsed


def _numeric_text(value: object, *, bits: int) -> str:
    digits = max(50, math.ceil(bits * math.log10(2)) + 8)
    with mp.workprec(bits + 64):
        parsed = _mp_value(
            value,
            failure_class="HIGH_PRECISION_REFINEMENT_FAILED",
            detail="non-finite numeric lane value",
        )
        return mp.nstr(parsed, n=digits, strip_zeros=False)


def _approximate_texts(values: Sequence[object]) -> list[str]:
    if not isinstance(values, (list, tuple)):
        raise NumericalAuthorityError(
            "HIGH_PRECISION_REFINEMENT_FAILED", "approximate configuration malformed"
        )
    result: list[str] = []
    for value in values:
        if isinstance(value, bool):
            raise NumericalAuthorityError(
                "HIGH_PRECISION_REFINEMENT_FAILED",
                "approximate configuration malformed",
            )
        text = value if isinstance(value, str) else repr(value)
        try:
            parsed = mp.mpf(text)
        except (TypeError, ValueError) as error:
            raise NumericalAuthorityError(
                "HIGH_PRECISION_REFINEMENT_FAILED",
                "approximate configuration malformed",
            ) from error
        if not mp.isfinite(parsed):
            raise NumericalAuthorityError(
                "HIGH_PRECISION_REFINEMENT_FAILED",
                "approximate configuration non-finite",
            )
        result.append(str(text))
    return result


def _check_exact_keys(observed: object, expected: Sequence[str], *, detail: str):
    mapping = _as_mapping(observed, detail=detail)
    if set(mapping) != set(expected):
        raise NumericalAuthorityError("GUARD_OR_BRANCH_UNSTABLE", detail)
    return mapping


def _validate_replay(
    replay_value: object,
    *,
    inventory: Mapping[str, Any],
    bits: int,
) -> dict[str, Any]:
    replay = _as_mapping(replay_value, detail=f"{bits}-bit replay malformed")
    required = {
        "construction_finite",
        "constraints",
        "guards",
        "branches",
        "bounds",
        "target",
    }
    if set(replay) != required:
        raise NumericalAuthorityError(
            "GUARD_OR_BRANCH_UNSTABLE", f"{bits}-bit replay field set"
        )
    construction = _check_exact_keys(
        replay["construction_finite"],
        inventory["construction_labels"],
        detail=f"{bits}-bit construction coverage",
    )
    if any(value is not True for value in construction.values()):
        raise NumericalAuthorityError(
            "HIGH_PRECISION_REFINEMENT_FAILED", f"{bits}-bit construction replay"
        )

    constraints = _check_exact_keys(
        replay["constraints"],
        inventory["constraint_labels"],
        detail=f"{bits}-bit constraint coverage",
    )
    max_absolute = mp.mpf("0")
    max_normalized = mp.mpf("0")
    constraint_evidence: dict[str, dict[str, str]] = {}
    for label, raw in constraints.items():
        item = _as_mapping(raw, detail=f"{bits}-bit constraint {label}")
        if set(item) != {"absolute_residual", "normalized_residual"}:
            raise NumericalAuthorityError(
                "RESIDUAL_GATE_FAILED", f"{bits}-bit constraint schema {label}"
            )
        absolute = abs(
            _mp_value(
                item["absolute_residual"],
                failure_class="RESIDUAL_GATE_FAILED",
                detail=f"{bits}-bit absolute residual {label}",
            )
        )
        normalized = abs(
            _mp_value(
                item["normalized_residual"],
                failure_class="RESIDUAL_GATE_FAILED",
                detail=f"{bits}-bit normalized residual {label}",
            )
        )
        max_absolute = max(max_absolute, absolute)
        max_normalized = max(max_normalized, normalized)
        constraint_evidence[label] = {
            "absolute_residual": _numeric_text(absolute, bits=bits),
            "normalized_residual": _numeric_text(normalized, bits=bits),
        }
    if max_absolute > NUMERIC_GATE or max_normalized > NUMERIC_GATE:
        raise NumericalAuthorityError(
            "RESIDUAL_GATE_FAILED", f"{bits}-bit residual exceeds 1e-100"
        )

    expected_checks = {
        "guards": [(label, True) for label in inventory["guard_labels"]],
        "bounds": [
            (entry["label"], bool(entry["strict"]))
            for entry in inventory["bound_entries"]
        ],
    }
    check_evidence: dict[str, dict[str, dict[str, Any]]] = {}
    minimum_strict_margin = mp.inf
    for category, specifications in expected_checks.items():
        expected_labels = [label for label, _strict in specifications]
        observed = _check_exact_keys(
            replay[category], expected_labels, detail=f"{bits}-bit {category} coverage"
        )
        category_evidence: dict[str, dict[str, Any]] = {}
        for label, strict in specifications:
            item = _as_mapping(observed[label], detail=f"{bits}-bit {category} {label}")
            allowed = {"passed", "margin", "strict"}
            if (
                set(item) != allowed
                or item.get("passed") is not True
                or item.get("strict") is not strict
            ):
                raise NumericalAuthorityError(
                    "GUARD_OR_BRANCH_UNSTABLE", f"{bits}-bit {category} {label}"
                )
            margin = _mp_value(
                item.get("margin"),
                failure_class="GUARD_OR_BRANCH_UNSTABLE",
                detail=f"{bits}-bit {category} margin {label}",
            )
            if (strict and margin <= NUMERIC_GATE) or (not strict and margin < 0):
                raise NumericalAuthorityError(
                    "GUARD_OR_BRANCH_UNSTABLE", f"{bits}-bit {category} margin {label}"
                )
            if strict:
                minimum_strict_margin = min(minimum_strict_margin, margin)
            output = {
                "passed": True,
                "strict": strict,
                "margin": _numeric_text(margin, bits=bits),
            }
            category_evidence[label] = output
        check_evidence[category] = category_evidence

    # Branches are an observed execution trace, not a source-AST obligation:
    # singleton/line intersections need no selector decision.  The compiled
    # evaluator must expose every selector entry it actually observed.  The
    # caller later requires the complete trace keys, kinds, and choices to be
    # byte-for-byte stable across all three fresh precision lanes.
    branches = _as_mapping(replay["branches"], detail=f"{bits}-bit branch trace")
    branch_evidence: dict[str, dict[str, Any]] = {}
    for label, raw in branches.items():
        if not isinstance(label, str) or not label:
            raise NumericalAuthorityError(
                "GUARD_OR_BRANCH_UNSTABLE", f"{bits}-bit branch trace label"
            )
        item = _as_mapping(raw, detail=f"{bits}-bit branch {label}")
        if (
            set(item) != {"passed", "margin", "strict", "choice", "kind"}
            or item.get("passed") is not True
            or item.get("strict") is not True
        ):
            raise NumericalAuthorityError(
                "GUARD_OR_BRANCH_UNSTABLE", f"{bits}-bit branch {label}"
            )
        margin = _mp_value(
            item.get("margin"),
            failure_class="GUARD_OR_BRANCH_UNSTABLE",
            detail=f"{bits}-bit branch margin {label}",
        )
        choice = item.get("choice")
        kind = item.get("kind")
        if (
            margin <= NUMERIC_GATE
            or not isinstance(choice, int)
            or isinstance(choice, bool)
            or choice < 0
            or not isinstance(kind, str)
            or not kind
        ):
            raise NumericalAuthorityError(
                "GUARD_OR_BRANCH_UNSTABLE", f"{bits}-bit branch evidence {label}"
            )
        minimum_strict_margin = min(minimum_strict_margin, margin)
        branch_evidence[label] = {
            "passed": True,
            "strict": True,
            "margin": _numeric_text(margin, bits=bits),
            "choice": choice,
            "kind": kind,
        }
    check_evidence["branches"] = branch_evidence

    target = _numeric_text(replay["target"], bits=bits)
    summary = {
        "construction_finite": dict(construction),
        "constraint_residuals": constraint_evidence,
        "max_absolute_residual": _numeric_text(max_absolute, bits=bits),
        "max_normalized_residual": _numeric_text(max_normalized, bits=bits),
        **check_evidence,
        "minimum_strict_margin": (
            None
            if mp.isinf(minimum_strict_margin)
            else _numeric_text(minimum_strict_margin, bits=bits)
        ),
        "target": target,
        "semantic_inventory_sha256": inventory["inventory_sha256"],
    }
    return {**summary, "replay_sha256": canonical_sha256(summary)}


def _run_lane(
    compiled_evaluator: object,
    *,
    bits: int,
    lane_id: str,
    approximate_texts: Sequence[str],
    inventory: Mapping[str, Any],
) -> tuple[dict[str, Any], object]:
    factory = getattr(compiled_evaluator, "new_lane", None)
    if not callable(factory):
        raise NumericalAuthorityError(
            "HIGH_PRECISION_REFINEMENT_FAILED", "compiled evaluator has no lane factory"
        )
    lane = factory(bits=bits, lane_id=lane_id)
    if getattr(lane, "bits", None) != bits or getattr(lane, "lane_id", None) != lane_id:
        raise NumericalAuthorityError(
            "HIGH_PRECISION_REFINEMENT_FAILED", f"{bits}-bit lane identity"
        )
    with mp.workprec(bits + 64):
        start = tuple(mp.mpf(text) for text in approximate_texts)
        result = _as_mapping(
            lane.refine(start), detail=f"{bits}-bit refinement result malformed"
        )
        if set(result) != {"coordinates", "method", "iterations"}:
            raise NumericalAuthorityError(
                "HIGH_PRECISION_REFINEMENT_FAILED", f"{bits}-bit refinement schema"
            )
        coordinates = _as_sequence(
            result["coordinates"], detail=f"{bits}-bit coordinates malformed"
        )
        if len(coordinates) != len(inventory["variables"]):
            raise NumericalAuthorityError(
                "HIGH_PRECISION_REFINEMENT_FAILED", f"{bits}-bit coordinate dimension"
            )
        parsed = tuple(
            _mp_value(
                value,
                failure_class="HIGH_PRECISION_REFINEMENT_FAILED",
                detail=f"{bits}-bit coordinate non-finite",
            )
            for value in coordinates
        )
        method = result["method"]
        iterations = result["iterations"]
        if (
            not isinstance(method, str)
            or not method
            or not isinstance(iterations, int)
            or isinstance(iterations, bool)
            or iterations < 0
        ):
            raise NumericalAuthorityError(
                "HIGH_PRECISION_REFINEMENT_FAILED", f"{bits}-bit refinement metadata"
            )
        try:
            replay_value = lane.replay(parsed)
        except Exception as error:
            # The compiled-evaluator seam may discover that a source primitive
            # is numerically finite while being outside its mathematical
            # domain (for example, Angle at a zero-length ray).  Preserve that
            # narrow, stable rejection class without coupling this authority
            # to an evaluator-specific exception type or module identity.
            if (
                getattr(error, "failure_class", None)
                == "HIGH_PRECISION_SEMANTIC_DEFECT"
            ):
                raise NumericalAuthorityError(
                    "HIGH_PRECISION_SEMANTIC_DEFECT",
                    f"{bits}-bit primitive domain replay: {error}",
                ) from error
            raise
        replay = _validate_replay(replay_value, inventory=inventory, bits=bits)
        lane_evidence = {
            "bits": bits,
            "lane_id": lane_id,
            "independently_initialized": True,
            "start_sha256": canonical_sha256(
                {"bits": bits, "coordinates": list(approximate_texts)}
            ),
            "method": method,
            "iterations": iterations,
            "coordinates": [_numeric_text(value, bits=bits) for value in parsed],
            "replay": replay,
        }
        return lane_evidence, lane


def _max_difference(left: Sequence[str], right: Sequence[str]):
    with mp.workprec(1152):
        return max(
            (abs(mp.mpf(a) - mp.mpf(b)) for a, b in zip(left, right, strict=True)),
            default=mp.mpf("0"),
        )


def _poly_trim(values: list[Fraction]) -> list[Fraction]:
    while len(values) > 1 and values[0] == 0:
        values.pop(0)
    return values


def _poly_divmod(
    dividend: Sequence[Fraction], divisor: Sequence[Fraction]
) -> tuple[list[Fraction], list[Fraction]]:
    numerator = _poly_trim(list(dividend))
    denominator = _poly_trim(list(divisor))
    if denominator == [0]:
        raise ZeroDivisionError
    if len(numerator) < len(denominator):
        return [Fraction(0)], numerator
    quotient = [Fraction(0)] * (len(numerator) - len(denominator) + 1)
    while numerator != [0] and len(numerator) >= len(denominator):
        offset = len(numerator) - len(denominator)
        factor = numerator[0] / denominator[0]
        quotient[len(quotient) - offset - 1] = factor
        subtract = [factor * value for value in denominator] + [Fraction(0)] * offset
        numerator = _poly_trim(
            [left - right for left, right in zip(numerator, subtract, strict=True)]
        )
    return quotient, numerator


def _square_free(coefficients: Sequence[int]) -> bool:
    polynomial = [Fraction(value) for value in coefficients]
    degree = len(polynomial) - 1
    derivative = [polynomial[index] * (degree - index) for index in range(degree)] or [
        Fraction(0)
    ]
    left, right = _poly_trim(polynomial), _poly_trim(derivative)
    while right != [0]:
        _quotient, remainder = _poly_divmod(left, right)
        left, right = right, _poly_trim(remainder)
    return len(left) == 1


def _fraction(value: object) -> Fraction:
    if not isinstance(value, str) or not re.fullmatch(r"-?\d+(?:/\d+)?", value):
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "isolating interval endpoint malformed"
        )
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "isolating interval endpoint malformed"
        ) from error


def _fraction_text(value: Fraction) -> str:
    return (
        str(value.numerator)
        if value.denominator == 1
        else f"{value.numerator}/{value.denominator}"
    )


def _relation_residual(coefficients: Sequence[int], numeric_text: str):
    with mp.workprec(1152):
        value = mp.mpf(numeric_text)
        total = mp.mpf("0")
        scale = mp.mpf("0")
        for coefficient in coefficients:
            total = total * value + coefficient
            scale = scale * abs(value) + abs(coefficient)
        absolute = abs(total)
        return absolute, absolute / max(mp.mpf("1"), scale)


def _constant_fraction(node: ast.AST) -> Fraction | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        if isinstance(node.value, bool):
            return None
        return Fraction(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _constant_fraction(node.operand)
        if value is None:
            return None
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left = _constant_fraction(node.left)
        right = _constant_fraction(node.right)
        if left is None or right is None:
            return None
        try:
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div) and right:
                return left / right
            if (
                isinstance(node.op, ast.Pow)
                and right.denominator == 1
                and -4 <= right.numerator <= 4
            ):
                return left ** right.numerator
        except (ArithmeticError, OverflowError, ZeroDivisionError):
            return None
    return None


_LENGTH_FUNCTIONS = {
    "Circumradius",
    "Distance",
    "Diameter",
    "Inradius",
    "Length",
    "Perimeter",
    "Radius",
    "Semiperimeter",
}
_AREA_FUNCTIONS = {"Area", "OrientedArea"}
_DIMENSIONLESS_FUNCTIONS = {
    "Angle",
    "Cos",
    "CrossRatio",
    "Ratio",
    "Sin",
    "Slope",
    "Tan",
}


def _call_name(node: ast.Call) -> str | None:
    function = node.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return None


def _expression_dimension(node: ast.AST) -> int | None:
    """Infer the scalar length exponent used only for proposal scaling."""

    if isinstance(node, ast.Expression):
        return _expression_dimension(node.body)
    if isinstance(node, ast.Constant):
        return 0
    if isinstance(node, ast.UnaryOp):
        return _expression_dimension(node.operand)
    if isinstance(node, ast.Attribute) and node.attr in {"x", "y", "z"}:
        return 1
    if isinstance(node, ast.Call):
        name = _call_name(node)
        if name in _LENGTH_FUNCTIONS:
            return 1
        if name in _AREA_FUNCTIONS:
            return 2
        if name in _DIMENSIONLESS_FUNCTIONS:
            return 0
        return None
    if isinstance(node, ast.BinOp):
        left = _expression_dimension(node.left)
        right = _expression_dimension(node.right)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            return left if left is not None and left == right else None
        if isinstance(node.op, ast.Mult):
            return None if left is None or right is None else left + right
        if isinstance(node.op, ast.Div):
            return None if left is None or right is None else left - right
        if isinstance(node.op, ast.Pow):
            exponent = _constant_fraction(node.right)
            if (
                left is not None
                and exponent is not None
                and exponent.denominator == 1
                and -4 <= exponent.numerator <= 4
            ):
                return left * exponent.numerator
    return None


def _parsed_expression(value: object) -> ast.Expression | None:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        return ast.parse(str(value), mode="eval")
    except SyntaxError:
        return None


def _source_expressions(source: Mapping[str, Any]):
    for item in source.get("construction") or ():
        if isinstance(item, Mapping):
            yield item.get("expr")
    for item in source.get("constraints") or ():
        if isinstance(item, Mapping):
            yield item.get("def")
            yield item.get("value")
    yield from source.get("guards") or ()
    if "answer" in source:
        yield source["answer"]
    for interval in source.get("bounds") or ():
        if isinstance(interval, Mapping):
            yield interval.get("lower")
            yield interval.get("upper")
        elif isinstance(interval, Sequence) and not isinstance(interval, str):
            yield from interval


def _public_source_scales(
    source: Mapping[str, Any], target_768: str
) -> tuple[Fraction, ...]:
    """Bounded exact scales from public literals and scalar dimensions."""

    bases: set[Fraction] = {Fraction(1)}
    dimensioned: dict[int, set[Fraction]] = {0: set(), 1: set(), 2: set()}
    for expression in _source_expressions(source):
        tree = _parsed_expression(expression)
        if tree is None:
            continue
        for node in ast.walk(tree):
            value = _constant_fraction(node)
            if value is None or value == 0:
                continue
            value = abs(value)
            if value.numerator.bit_length() <= 128 and value.denominator.bit_length() <= 128:
                bases.add(value)
    for item in source.get("constraints") or ():
        if not isinstance(item, Mapping):
            continue
        left = _parsed_expression(item.get("def"))
        right = _parsed_expression(item.get("value"))
        if left is None or right is None:
            continue
        dimension = _expression_dimension(left)
        value = _constant_fraction(right.body)
        if dimension in dimensioned and value not in (None, 0):
            dimensioned[dimension].add(abs(value))

    ordered = sorted(
        bases,
        key=lambda value: (
            value.numerator.bit_length() + value.denominator.bit_length(),
            value.numerator,
            value.denominator,
        ),
    )
    candidates: set[Fraction] = set(ordered)
    for index, left in enumerate(ordered):
        for right in ordered[index:]:
            for value in (left * right, left / right, right / left):
                if (
                    value > 0
                    and value.numerator.bit_length() <= 160
                    and value.denominator.bit_length() <= 160
                ):
                    candidates.add(value)

    answer = _parsed_expression(source.get("answer"))
    answer_dimension = None if answer is None else _expression_dimension(answer)
    if answer_dimension in dimensioned:
        candidates.update(dimensioned[answer_dimension])
    if answer_dimension == 2:
        lengths = sorted(dimensioned[1])
        for index, left in enumerate(lengths):
            for right in lengths[index:]:
                candidates.add(left * right)
                candidates.add(left * right / 2)

    with mp.workprec(832):
        magnitude = max(mp.mpf("1"), abs(mp.mpf(target_768)))

    def rank(value: Fraction) -> tuple[object, ...]:
        if value == 1:
            return (-1, 0.0, 0, 1, 1)
        with mp.workprec(192):
            numeric = mp.mpf(value.numerator) / value.denominator
            distance = float(abs(mp.log(numeric / magnitude)))
        return (
            0,
            distance,
            value.numerator.bit_length() + value.denominator.bit_length(),
            value.numerator,
            value.denominator,
        )

    return tuple(sorted(candidates, key=rank)[:PSLQ_SOURCE_SCALE_MAXIMUM])


def _scale_numeric_text(value: str, scale: Fraction, *, bits: int) -> str:
    if scale <= 0:
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "non-positive source scale"
        )
    with mp.workprec(bits + 96):
        normalized = mp.mpf(value) * scale.denominator / scale.numerator
        return mp.nstr(
            normalized,
            n=max(50, math.ceil((bits + 64) * math.log10(2)) + 8),
            strip_zeros=False,
        )


def _explicit_pslq_budget(*, bits: int, degree: int, cap_bits: int):
    return OWNED_PSLQ.PSLQBudget(
        precision_bits=bits,
        tolerance_bits=PSLQ_RELATION_TOLERANCE_BITS,
        max_degree=degree,
        max_steps=PSLQ_MAX_STEPS,
        coefficient_cap_bits=cap_bits,
        coefficient_cap=1 << cap_bits,
    )


def _search_explicit_cap(value_text: str, *, bits: int, cap_bits: int):
    with mp.workprec(bits + 64):
        value = mp.mpf(value_text)
        if not mp.isfinite(value):
            raise NumericalAuthorityError("TARGET_PSLQ_FAILED", "non-finite target")
        if abs(value) <= mp.power(2, -PSLQ_RELATION_TOLERANCE_BITS):
            budget = _explicit_pslq_budget(bits=bits, degree=1, cap_bits=cap_bits)
            return (
                OWNED_PSLQ.PSLQIteration(
                    (0, 1), 0, "ZERO_RELATION", None, None, budget.coefficient_cap
                ),
                budget,
            )
        powers = [mp.mpf("1")]
        for _degree in range(OWNED_PSLQ.MAX_DEGREE):
            powers.append(powers[-1] * value)
        for degree in range(1, OWNED_PSLQ.MAX_DEGREE + 1):
            budget = _explicit_pslq_budget(
                bits=bits, degree=degree, cap_bits=cap_bits
            )
            result = OWNED_PSLQ.pslq_fixed(
                powers[: degree + 1], budget=budget
            )
            if result.relation_low_to_high is not None:
                return result, budget
    return None, None


def _recognize_explicit_cap(
    target_768: str, target_1024: str, *, cap_bits: int
) -> dict[str, Any]:
    proposal, proposal_budget = _search_explicit_cap(
        target_768, bits=768, cap_bits=cap_bits
    )
    base = {
        "schema_version": "geotarget.owned-pslq-explicit-cap/v1",
        "proposal_input_sha256": OWNED_PSLQ._lane_digest(target_768, 768),
        "confirmation_input_sha256": OWNED_PSLQ._lane_digest(target_1024, 1024),
        "proposal_bits": 768,
        "confirmation_bits": 1024,
        "max_degree": OWNED_PSLQ.MAX_DEGREE,
        "max_steps_per_degree": PSLQ_MAX_STEPS,
        "proposal": None if proposal is None else asdict(proposal),
        "confirmation": None,
        "proposal_budget": None if proposal_budget is None else asdict(proposal_budget),
        "confirmation_budget": None,
        "owned_integer_relation_iteration": True,
        "dependency_pslq_called": False,
        "explicit_coefficient_cap_bits": cap_bits,
    }
    if proposal is None or proposal.relation_low_to_high is None:
        return {**base, "status": "NO_RELATION", "descriptor": None}
    proposal_factor = OWNED_PSLQ._factor_and_isolate(
        proposal.relation_low_to_high,
        target_768,
        precision_bits=768,
        residual_bits=PSLQ_RELATION_TOLERANCE_BITS,
    )
    if proposal_factor is None:
        return {**base, "status": "EXACT_FACTOR_UNVERIFIED", "descriptor": None}

    confirmation, confirmation_budget = _search_explicit_cap(
        target_1024, bits=1024, cap_bits=cap_bits
    )
    base["confirmation"] = None if confirmation is None else asdict(confirmation)
    base["confirmation_budget"] = (
        None if confirmation_budget is None else asdict(confirmation_budget)
    )
    if confirmation is None or confirmation.relation_low_to_high is None:
        return {**base, "status": "NO_RELATION", "descriptor": None}
    confirmation_factor = OWNED_PSLQ._factor_and_isolate(
        confirmation.relation_low_to_high,
        target_1024,
        precision_bits=1024,
        residual_bits=PSLQ_RELATION_TOLERANCE_BITS,
    )
    if confirmation_factor is None:
        return {**base, "status": "EXACT_FACTOR_UNVERIFIED", "descriptor": None}
    if (
        proposal_factor["minimal_polynomial_high_to_low"]
        != confirmation_factor["minimal_polynomial_high_to_low"]
        or proposal_factor["isolating_interval"]["real_root_index"]
        != confirmation_factor["isolating_interval"]["real_root_index"]
    ):
        return {
            **base,
            "status": "INDEPENDENT_LANE_DISAGREEMENT",
            "proposal_factor": proposal_factor,
            "confirmation_factor": confirmation_factor,
            "descriptor": None,
        }
    return {
        **base,
        "status": "ALGEBRAIC_RELATION_VERIFIED",
        "proposal_factor": proposal_factor,
        "confirmation_factor": confirmation_factor,
        "descriptor": {
            "minimal_polynomial_high_to_low": confirmation_factor[
                "minimal_polynomial_high_to_low"
            ],
            "isolating_interval": confirmation_factor["isolating_interval"],
        },
    }


def _recognition_cap_bits(recognition: Mapping[str, Any], default: int) -> int:
    budget = recognition.get("proposal_budget")
    if isinstance(budget, Mapping):
        value = budget.get("coefficient_cap_bits")
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return default


def _ordered_target_recognition(
    source: Mapping[str, Any], target_768: str, target_1024: str
) -> dict[str, Any]:
    scales = _public_source_scales(source, target_768)
    attempts: list[dict[str, Any]] = []
    for scale_index, scale in enumerate(scales):
        normalized_768 = _scale_numeric_text(target_768, scale, bits=768)
        normalized_1024 = _scale_numeric_text(target_1024, scale, bits=1024)
        try:
            if scale_index == 0 and scale == 1:
                recognition = OWNED_PSLQ.recognize_algebraic(
                    normalized_768,
                    normalized_1024,
                    proposal_bits=768,
                    confirmation_bits=1024,
                    max_degree=OWNED_PSLQ.MAX_DEGREE,
                    max_steps=PSLQ_MAX_STEPS,
                    relation_tolerance_bits=PSLQ_RELATION_TOLERANCE_BITS,
                )
            else:
                recognition = _recognize_explicit_cap(
                    normalized_768,
                    normalized_1024,
                    cap_bits=PSLQ_INCUMBENT_CAP_BITS,
                )
        except Exception as error:
            raise NumericalAuthorityError("TARGET_PSLQ_FAILED", str(error)) from error
        status = recognition.get("status") if isinstance(recognition, Mapping) else None
        cap_bits = _recognition_cap_bits(recognition, PSLQ_INCUMBENT_CAP_BITS)
        attempts.append(
            {
                "mechanism": "SOURCE_SCALE",
                "scale": {"numerator": scale.numerator, "denominator": scale.denominator},
                "cap_bits": cap_bits,
                "status": status,
            }
        )
        if status == "ALGEBRAIC_RELATION_VERIFIED":
            return {
                "schema_version": "geotarget.ordered-target-recognition/v1",
                "policy": "PUBLIC_SOURCE_SCALE_CAP34_THEN_RAW_CAP_LADDER",
                "status": status,
                "selected_mechanism": "SOURCE_SCALE",
                "selected_cap_bits": cap_bits,
                "selected_source_scale": {
                    "numerator": scale.numerator,
                    "denominator": scale.denominator,
                },
                "normalized_target_768": normalized_768,
                "normalized_target_1024": normalized_1024,
                "recognition": recognition,
                "attempted_prefix": attempts,
                "attempted_prefix_sha256": canonical_sha256(attempts),
                "source_scale_candidate_count": len(scales),
            }
        if status != "NO_RELATION":
            raise NumericalAuthorityError(
                "TARGET_RELATION_NOT_CONFIRMED",
                f"source-scale recognizer returned {status}",
            )

    for cap_bits in PSLQ_FALLBACK_CAP_BITS:
        try:
            recognition = _recognize_explicit_cap(
                target_768, target_1024, cap_bits=cap_bits
            )
        except Exception as error:
            raise NumericalAuthorityError("TARGET_PSLQ_FAILED", str(error)) from error
        status = recognition.get("status")
        attempts.append(
            {
                "mechanism": "RAW_BOUND_LADDER",
                "scale": {"numerator": 1, "denominator": 1},
                "cap_bits": cap_bits,
                "status": status,
            }
        )
        if status == "ALGEBRAIC_RELATION_VERIFIED":
            return {
                "schema_version": "geotarget.ordered-target-recognition/v1",
                "policy": "PUBLIC_SOURCE_SCALE_CAP34_THEN_RAW_CAP_LADDER",
                "status": status,
                "selected_mechanism": "RAW_BOUND_LADDER",
                "selected_cap_bits": cap_bits,
                "selected_source_scale": {"numerator": 1, "denominator": 1},
                "normalized_target_768": target_768,
                "normalized_target_1024": target_1024,
                "recognition": recognition,
                "attempted_prefix": attempts,
                "attempted_prefix_sha256": canonical_sha256(attempts),
                "source_scale_candidate_count": len(scales),
            }
        if status != "NO_RELATION":
            raise NumericalAuthorityError(
                "TARGET_RELATION_NOT_CONFIRMED",
                f"bound-ladder recognizer returned {status}",
            )
    raise NumericalAuthorityError(
        "TARGET_PSLQ_FAILED", "ordered target recognizer found no relation"
    )


def _validated_ordered_selection(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "ordered recognition result malformed"
        )
    if (
        value.get("schema_version") != "geotarget.ordered-target-recognition/v1"
        or value.get("policy")
        != "PUBLIC_SOURCE_SCALE_CAP34_THEN_RAW_CAP_LADDER"
        or value.get("status") != "ALGEBRAIC_RELATION_VERIFIED"
    ):
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "ordered recognition contract"
        )
    mechanism = value.get("selected_mechanism")
    cap_bits = value.get("selected_cap_bits")
    raw_scale = value.get("selected_source_scale")
    if (
        mechanism not in {"SOURCE_SCALE", "RAW_BOUND_LADDER"}
        or not isinstance(cap_bits, int)
        or isinstance(cap_bits, bool)
        or not isinstance(raw_scale, Mapping)
    ):
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "ordered selection malformed"
        )
    numerator, denominator = raw_scale.get("numerator"), raw_scale.get("denominator")
    if (
        not isinstance(numerator, int)
        or isinstance(numerator, bool)
        or not isinstance(denominator, int)
        or isinstance(denominator, bool)
        or numerator <= 0
        or denominator <= 0
        or gcd(numerator, denominator) != 1
    ):
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "selected source scale malformed"
        )
    if mechanism == "SOURCE_SCALE" and cap_bits != PSLQ_INCUMBENT_CAP_BITS:
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "source-scale cap mismatch"
        )
    if mechanism == "RAW_BOUND_LADDER" and (
        cap_bits not in PSLQ_FALLBACK_CAP_BITS or (numerator, denominator) != (1, 1)
    ):
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "raw bound-ladder selection mismatch"
        )
    attempts = value.get("attempted_prefix")
    if (
        not isinstance(attempts, list)
        or not attempts
        or value.get("attempted_prefix_sha256") != canonical_sha256(attempts)
    ):
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "attempted prefix digest mismatch"
        )
    for index, attempt in enumerate(attempts):
        if not isinstance(attempt, Mapping):
            raise NumericalAuthorityError(
                "TARGET_RELATION_NOT_CONFIRMED", "attempted prefix malformed"
            )
        expected_status = (
            "ALGEBRAIC_RELATION_VERIFIED" if index == len(attempts) - 1 else "NO_RELATION"
        )
        if attempt.get("status") != expected_status:
            raise NumericalAuthorityError(
                "TARGET_RELATION_NOT_CONFIRMED", "attempted prefix order malformed"
            )
    selected_attempt = attempts[-1]
    if (
        selected_attempt.get("mechanism") != mechanism
        or selected_attempt.get("cap_bits") != cap_bits
        or selected_attempt.get("scale")
        != {"numerator": numerator, "denominator": denominator}
    ):
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "selected attempt mismatch"
        )
    if not isinstance(value.get("recognition"), Mapping):
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "selected recognition missing"
        )
    for key in ("normalized_target_768", "normalized_target_1024"):
        if not isinstance(value.get(key), str):
            raise NumericalAuthorityError(
                "TARGET_RELATION_NOT_CONFIRMED", "normalized target missing"
            )
    return value


def _primitive_coefficients_high(values: Sequence[int]) -> list[int]:
    coefficients = [int(value) for value in values]
    if len(coefficients) < 2 or coefficients[0] == 0:
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "mapped polynomial degree malformed"
        )
    common = 0
    for value in coefficients:
        common = gcd(common, abs(value))
    if common > 1:
        coefficients = [value // common for value in coefficients]
    if coefficients[0] < 0:
        coefficients = [-value for value in coefficients]
    if max(abs(value).bit_length() for value in coefficients) > (
        PSLQ_OUTPUT_COEFFICIENT_BITS_MAXIMUM
    ):
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "mapped coefficient safety cap"
        )
    return coefficients


def _backmap_coefficients_high(
    normalized: Sequence[int], scale: Fraction
) -> list[int]:
    degree = len(normalized) - 1
    numerator, denominator = scale.numerator, scale.denominator
    mapped = [
        int(coefficient)
        * denominator ** (degree - index)
        * numerator**index
        for index, coefficient in enumerate(normalized)
    ]
    return _primitive_coefficients_high(mapped)


def _backmap_interval(raw: Mapping[str, Any], scale: Fraction) -> dict[str, Any]:
    left = _fraction(raw.get("left")) * scale
    right = _fraction(raw.get("right")) * scale
    mapped = dict(raw)
    mapped["left"] = _fraction_text(left)
    mapped["right"] = _fraction_text(right)
    mapped["exact_positive_rational_scale"] = {
        "numerator": scale.numerator,
        "denominator": scale.denominator,
    }
    return mapped


def _validated_interval(
    raw: Mapping[str, Any],
    *,
    coefficients: Sequence[int],
    detail: str,
) -> tuple[Fraction, Fraction, int, dict[str, Any]]:
    left, right = _fraction(raw.get("left")), _fraction(raw.get("right"))
    root_index = raw.get("real_root_index")
    if (
        raw.get("multiplicity") != 1
        or not isinstance(root_index, int)
        or isinstance(root_index, bool)
        or root_index < 0
    ):
        raise NumericalAuthorityError("TARGET_RELATION_NOT_CONFIRMED", detail)
    if left > right:
        raise NumericalAuthorityError("TARGET_RELATION_NOT_CONFIRMED", detail)
    if left == right:
        if len(coefficients) != 2 or coefficients[0] == 0:
            raise NumericalAuthorityError(
                "TARGET_RELATION_NOT_CONFIRMED",
                "only a degree-1 rational relation may use point isolation",
            )
        exact_root = Fraction(-coefficients[1], coefficients[0])
        if left != exact_root:
            raise NumericalAuthorityError(
                "TARGET_RELATION_NOT_CONFIRMED",
                "degree-1 point isolator does not equal its exact rational root",
            )
        left = exact_root - RATIONAL_POINT_INTERVAL_RADIUS
        right = exact_root + RATIONAL_POINT_INTERVAL_RADIUS
        normalized = {
            "left": _fraction_text(left),
            "right": _fraction_text(right),
            "multiplicity": 1,
            "real_root_index": root_index,
            "endpoint_policy": "OPEN",
            "normalization": "DEGREE1_RATIONAL_POINT_TO_OPEN_2E_100",
            "exact_rational_root": _fraction_text(exact_root),
            "radius": _fraction_text(RATIONAL_POINT_INTERVAL_RADIUS),
        }
        return left, right, root_index, normalized
    return left, right, root_index, dict(raw)


def _owned_target_relation(
    target_768: str,
    target_1024: str,
    *,
    target_512: str | None = None,
    source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        selection = _validated_ordered_selection(
            _ordered_target_recognition(source or {}, target_768, target_1024)
        )
    except Exception as error:
        if isinstance(error, NumericalAuthorityError):
            raise
        raise NumericalAuthorityError("TARGET_PSLQ_FAILED", str(error)) from error
    recognition = selection["recognition"]
    scale_record = selection["selected_source_scale"]
    scale = Fraction(scale_record["numerator"], scale_record["denominator"])
    normalized_target_768 = selection["normalized_target_768"]
    normalized_target_1024 = selection["normalized_target_1024"]
    if (
        not isinstance(recognition, Mapping)
        or recognition.get("status") != "ALGEBRAIC_RELATION_VERIFIED"
    ):
        raise NumericalAuthorityError(
            "TARGET_PSLQ_FAILED", "owned PSLQ found no relation"
        )
    if (
        recognition.get("proposal_bits") != 768
        or recognition.get("confirmation_bits") != 1024
        or recognition.get("owned_integer_relation_iteration") is not True
        or recognition.get("dependency_pslq_called") is not False
    ):
        raise NumericalAuthorityError("TARGET_PSLQ_FAILED", "owned PSLQ contract")
    proposal = _as_mapping(
        recognition.get("proposal"), detail="proposal relation malformed"
    )
    confirmation = _as_mapping(
        recognition.get("confirmation"), detail="confirmation relation malformed"
    )
    proposal_factor = _as_mapping(
        recognition.get("proposal_factor"), detail="proposal factor malformed"
    )
    confirmation_factor = _as_mapping(
        recognition.get("confirmation_factor"), detail="confirmation factor malformed"
    )
    normalized_coefficients = confirmation_factor.get(
        "minimal_polynomial_high_to_low"
    )
    if (
        not isinstance(normalized_coefficients, list)
        or not 2 <= len(normalized_coefficients) <= OWNED_PSLQ.MAX_DEGREE + 1
        or any(
            not isinstance(value, int) or isinstance(value, bool)
            for value in normalized_coefficients
        )
        or normalized_coefficients[0] <= 0
        or proposal_factor.get("minimal_polynomial_high_to_low")
        != normalized_coefficients
        or proposal_factor.get("minimal_polynomial_primitive") is not True
        or confirmation_factor.get("minimal_polynomial_primitive") is not True
        or proposal_factor.get("minimal_polynomial_square_free") is not True
        or confirmation_factor.get("minimal_polynomial_square_free") is not True
        or proposal_factor.get("minimal_polynomial_irreducible_over_Q") is not True
        or confirmation_factor.get("minimal_polynomial_irreducible_over_Q") is not True
        or proposal_factor.get("selected_factor_exponent_in_relation") != 1
        or confirmation_factor.get("selected_factor_exponent_in_relation") != 1
    ):
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "primitive square-free relation contract"
        )
    normalized_common = 0
    for value in normalized_coefficients:
        normalized_common = gcd(normalized_common, abs(value))
    if normalized_common != 1 or not _square_free(normalized_coefficients):
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "independent square-free check"
        )
    coefficients = _backmap_coefficients_high(normalized_coefficients, scale)
    common = 0
    for value in coefficients:
        common = gcd(common, abs(value))
    if common != 1 or not _square_free(coefficients):
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "mapped square-free check"
        )
    proposal_interval_normalized = _as_mapping(
        proposal_factor.get("isolating_interval"),
        detail="proposal isolating interval malformed",
    )
    interval_normalized = _as_mapping(
        confirmation_factor.get("isolating_interval"),
        detail="confirmation isolating interval malformed",
    )
    proposal_interval = _backmap_interval(proposal_interval_normalized, scale)
    interval = _backmap_interval(interval_normalized, scale)
    (
        proposal_left,
        proposal_right,
        proposal_root_index,
        _proposal_normalized_interval,
    ) = _validated_interval(
        proposal_interval,
        coefficients=coefficients,
        detail="invalid proposal isolating interval",
    )
    left, right, root_index, normalized_interval = _validated_interval(
        interval,
        coefficients=coefficients,
        detail="invalid confirmation isolating interval",
    )
    if proposal_root_index != root_index:
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "independent lane root disagreement"
        )
    if max(proposal_left, left) >= min(proposal_right, right):
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "independent isolating intervals disjoint"
        )
    with mp.workprec(1152):
        proposal_left_mp = mp.mpf(proposal_left.numerator) / proposal_left.denominator
        proposal_right_mp = (
            mp.mpf(proposal_right.numerator) / proposal_right.denominator
        )
        left_mp = mp.mpf(left.numerator) / left.denominator
        right_mp = mp.mpf(right.numerator) / right.denominator
        if not (
            proposal_left_mp < mp.mpf(target_768) < proposal_right_mp
            and left_mp < mp.mpf(target_1024) < right_mp
        ):
            raise NumericalAuthorityError(
                "TARGET_RELATION_NOT_CONFIRMED", "numeric target misses isolated root"
            )
        rational_root_distance = None
        if len(coefficients) == 2:
            exact_root = Fraction(-coefficients[1], coefficients[0])
            exact_root_mp = mp.mpf(exact_root.numerator) / exact_root.denominator
            rational_targets = [target_768, target_1024]
            if target_512 is not None:
                rational_targets.insert(0, target_512)
            overlap_left = max(proposal_left_mp, left_mp)
            overlap_right = min(proposal_right_mp, right_mp)
            if not all(
                overlap_left < mp.mpf(value) < overlap_right
                for value in rational_targets
            ):
                raise NumericalAuthorityError(
                    "TARGET_RELATION_NOT_CONFIRMED",
                    "rational target misses the normalized open isolator",
                )
            rational_root_distance = max(
                abs(mp.mpf(value) - exact_root_mp) for value in rational_targets
            )
            if rational_root_distance > NUMERIC_GATE:
                raise NumericalAuthorityError(
                    "TARGET_RELATION_NOT_CONFIRMED",
                    "rational target is farther than 1e-100 from the exact root",
                )
    residual_768, normalized_768 = _relation_residual(coefficients, target_768)
    residual_1024, normalized_1024 = _relation_residual(coefficients, target_1024)
    if max(residual_768, normalized_768, residual_1024, normalized_1024) > NUMERIC_GATE:
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "relation residual exceeds 1e-100"
        )
    relation_768 = proposal.get("relation_low_to_high")
    relation_1024 = confirmation.get("relation_low_to_high")
    if (
        not isinstance(relation_768, (list, tuple))
        or not isinstance(relation_1024, (list, tuple))
        or any(
            not isinstance(value, int) or isinstance(value, bool)
            for value in (*relation_768, *relation_1024)
        )
    ):
        raise NumericalAuthorityError(
            "TARGET_RELATION_NOT_CONFIRMED", "owned relation iteration absent"
        )
    return {
        "status": "TARGET_RELATION_CONFIRMED",
        "owned_pslq_path": str(OWNED_PSLQ_PATH.relative_to(ROOT)),
        "proposal_bits": 768,
        "confirmation_bits": 1024,
        "recognition_sha256": canonical_sha256(recognition),
        "proposal_input_sha256": OWNED_PSLQ._lane_digest(target_768, 768),
        "confirmation_input_sha256": OWNED_PSLQ._lane_digest(target_1024, 1024),
        "proposal_relation_low_to_high": list(reversed(coefficients)),
        "confirmation_relation_low_to_high": list(reversed(coefficients)),
        "minimal_polynomial_high_to_low": list(coefficients),
        "primitive": True,
        "square_free": True,
        "irreducible_over_Q": True,
        "isolating_interval": normalized_interval,
        "selected_real_root_index": root_index,
        "target_512": target_512,
        "target_768": target_768,
        "target_1024": target_1024,
        "relation_absolute_residual_768": _numeric_text(residual_768, bits=768),
        "relation_normalized_residual_768": _numeric_text(normalized_768, bits=768),
        "relation_absolute_residual_1024": _numeric_text(residual_1024, bits=1024),
        "relation_normalized_residual_1024": _numeric_text(normalized_1024, bits=1024),
        "rational_target_max_distance": (
            None
            if rational_root_distance is None
            else _numeric_text(rational_root_distance, bits=1024)
        ),
        "recognition_policy": {
            "schema_version": selection["schema_version"],
            "policy": selection["policy"],
            "selected_mechanism": selection["selected_mechanism"],
            "selected_cap_bits": selection["selected_cap_bits"],
            "selected_source_scale": dict(selection["selected_source_scale"]),
            "attempted_prefix": list(selection["attempted_prefix"]),
            "attempted_prefix_sha256": selection["attempted_prefix_sha256"],
            "source_scale_candidate_count": selection[
                "source_scale_candidate_count"
            ],
            "source_scale_candidate_limit": PSLQ_SOURCE_SCALE_MAXIMUM,
            "fallback_cap_bits": list(PSLQ_FALLBACK_CAP_BITS),
            "exact_positive_rational_backmap_verified": True,
            "normalized_proposal_input_sha256": recognition.get(
                "proposal_input_sha256"
            ),
            "normalized_confirmation_input_sha256": recognition.get(
                "confirmation_input_sha256"
            ),
            "normalized_proposal_relation_low_to_high": list(relation_768),
            "normalized_confirmation_relation_low_to_high": list(relation_1024),
            "normalized_minimal_polynomial_high_to_low": list(
                normalized_coefficients
            ),
            "normalized_target_768": normalized_target_768,
            "normalized_target_1024": normalized_target_1024,
        },
    }


def build_target_evidence(
    source_payload: bytes,
    compiled_evaluator: object,
    approximate_configuration: Sequence[object],
) -> dict[str, Any]:
    """Validate one already-discovered target under numerical policy v3."""

    source = _strict_source(source_payload)
    inventory = semantic_inventory(source)
    approximate_texts = _approximate_texts(approximate_configuration)
    if len(approximate_texts) != len(inventory["variables"]):
        raise NumericalAuthorityError(
            "HIGH_PRECISION_REFINEMENT_FAILED", "approximate configuration dimension"
        )

    lane_512, object_512 = _run_lane(
        compiled_evaluator,
        bits=512,
        lane_id="independent-512",
        approximate_texts=approximate_texts,
        inventory=inventory,
    )
    lane_768, object_768 = _run_lane(
        compiled_evaluator,
        bits=768,
        lane_id="independent-768",
        approximate_texts=approximate_texts,
        inventory=inventory,
    )
    lane_1024, object_1024 = _run_lane(
        compiled_evaluator,
        bits=1024,
        lane_id="fresh-target-confirmation-1024",
        approximate_texts=approximate_texts,
        inventory=inventory,
    )
    if len({id(object_512), id(object_768), id(object_1024)}) != 3:
        raise NumericalAuthorityError(
            "HIGH_PRECISION_REFINEMENT_FAILED", "precision lanes are not independent"
        )

    configuration_disagreement = _max_difference(
        lane_512["coordinates"], lane_768["coordinates"]
    )
    target_512 = lane_512["replay"]["target"]
    target_768 = lane_768["replay"]["target"]
    target_1024 = lane_1024["replay"]["target"]
    with mp.workprec(1152):
        target_disagreement_512_768 = abs(mp.mpf(target_512) - mp.mpf(target_768))
        target_disagreement_768_1024 = abs(mp.mpf(target_768) - mp.mpf(target_1024))
    if (
        configuration_disagreement > NUMERIC_GATE
        or target_disagreement_512_768 > NUMERIC_GATE
        or target_disagreement_768_1024 > NUMERIC_GATE
    ):
        raise NumericalAuthorityError(
            "PRECISION_DISAGREEMENT", "configuration or target exceeds 1e-100"
        )
    branches_512 = {
        key: (value["kind"], value["choice"])
        for key, value in lane_512["replay"]["branches"].items()
    }
    branches_768 = {
        key: (value["kind"], value["choice"])
        for key, value in lane_768["replay"]["branches"].items()
    }
    branches_1024 = {
        key: (value["kind"], value["choice"])
        for key, value in lane_1024["replay"]["branches"].items()
    }
    if not branches_512 == branches_768 == branches_1024:
        raise NumericalAuthorityError(
            "GUARD_OR_BRANCH_UNSTABLE", "branch choices disagree across precision"
        )

    relation = _owned_target_relation(
        target_768,
        target_1024,
        target_512=target_512,
        source=source,
    )
    policy_payload = POLICY_PATH.read_bytes()
    policy = json.loads(policy_payload)
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("status") != "ACTIVE"
    ):
        raise NumericalAuthorityError(
            "HIGH_PRECISION_REFINEMENT_FAILED", "numerical success policy unavailable"
        )
    record = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "failure_class": "SUCCESS",
        "policy": {
            "schema_version": POLICY_SCHEMA,
            "raw_sha256": raw_sha256(policy_payload),
        },
        "source_raw_sha256": raw_sha256(source_payload),
        "semantic_inventory": inventory,
        "approximate_configuration_sha256": canonical_sha256(approximate_texts),
        "independent_refinement_lanes": True,
        "lanes": {
            "512": lane_512,
            "768": lane_768,
            "1024_target_confirmation": lane_1024,
        },
        "agreement": {
            "gate": "1e-100",
            "configuration_512_768_inf": _numeric_text(
                configuration_disagreement, bits=768
            ),
            "target_512_768": _numeric_text(target_disagreement_512_768, bits=768),
            "target_768_1024": _numeric_text(target_disagreement_768_1024, bits=1024),
            "branch_choices_stable": True,
        },
        "target_relation": relation,
        "authority": {
            "numerical_configuration_validated": True,
            "numerical_target_validated_to_1e_100": True,
            "target_algebraic_relation_identified": True,
            "exact_coordinate_witness": False,
            "exact_construction_graph_replay": False,
            "completeness_claim": False,
            "target_image_completeness": "NOT_RUN",
        },
        "excluded_lanes": [
            "full-coordinate exactification",
            "common primitive element for configuration",
            "QQBar",
            "PARI/GP",
            "msolve",
            "completeness proof",
        ],
        "runtime_routing_inputs": {
            "truth": False,
            "case_id": False,
            "family": False,
            "known_target_count": False,
        },
    }
    return seal(record)


__all__ = [
    "NumericalAuthorityError",
    "SCHEMA_VERSION",
    "build_target_evidence",
    "canonical_sha256",
    "semantic_inventory",
]
