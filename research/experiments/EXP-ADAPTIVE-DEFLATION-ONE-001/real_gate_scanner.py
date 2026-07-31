#!/usr/bin/env python3
"""Aggregate-only real applicability gate for ADAPTIVE_DEFLATION_ONE.

The scanner accepts a Root-custodied manifest containing only untouched source
bytes by path, a bare Float64 endpoint, and the baseline numerical-refinement
contract summary.  It does not accept or inspect case/family/truth/score/
outcome fields and never emits paths, source hashes, endpoints, or signatures.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import numpy as np
import sympy as sp


SCHEMA = "geotarget.adaptive-deflation-one-real-gate/v1"
INPUT_SCHEMA = "geotarget.adaptive-deflation-one-real-gate-input/v1"
REQUIRED_ELIGIBLE = 4
REQUIRED_SIGNATURES = 2
NORMALIZED_CORANK_RATIO_MAX = 1.0e-6
SOURCE_RESIDUAL_INF_MAX = 1.0e-8
FROZEN_ROOT = Path("/home/kabatan/work/solver-experiment-runtime")
GEOSOLVER_SOURCE = FROZEN_ROOT / "geosolver/src"

if str(GEOSOLVER_SOURCE) not in sys.path:
    sys.path.insert(0, str(GEOSOLVER_SOURCE))

from geosolver._internal.autosolve.execution.interpreter_helpers import (  # noqa: E402
    _assign_variables,
)
from geosolver._internal.pipeline.evaluator.ir_evaluator import (  # noqa: E402
    build_ir_evaluator,
)
from geosolver._internal.pipeline.problem.load_problem_bundle import (  # noqa: E402
    load_problem_bundle,
)
from geosolver.ir.compiler import safe_eval_expr  # noqa: E402


ALLOWED_RECORD_KEYS = {
    "source_path",
    "source_sha256",
    "endpoint",
    "refinement_contract",
}
ALLOWED_REFINEMENT_KEYS = {
    "variant",
    "status",
    "numeric_v3_ready",
    "target_stability_ready",
}
MISS_REFINEMENT_STATUSES = {
    "HIGH_PRECISION_REFINEMENT_FAILED",
    "TARGET_STABILITY_FAILED",
}
NON_C2_NODES = (
    sp.Abs,
    sp.DiracDelta,
    sp.Heaviside,
    sp.Max,
    sp.Min,
    sp.Mod,
    sp.Piecewise,
    sp.ceiling,
    sp.floor,
    sp.sign,
)


class Ineligible(ValueError):
    def __init__(self, stage: str) -> None:
        super().__init__(stage)
        self.stage = stage


def _strict_hex(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise Ineligible("input_contract")
    return value


def _strict_endpoint(value: object) -> tuple[float, float]:
    if (
        isinstance(value, (str, bytes, bytearray, Mapping))
        or not isinstance(value, Sequence)
        or len(value) != 2
    ):
        raise Ineligible("square_n2")
    converted: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise Ineligible("input_contract")
        number = float(item)
        if not math.isfinite(number):
            raise Ineligible("input_contract")
        converted.append(number)
    return converted[0], converted[1]


def _strict_record(value: object) -> tuple[Path, str, tuple[float, float], Mapping[str, object]]:
    if not isinstance(value, Mapping) or set(value) != ALLOWED_RECORD_KEYS:
        raise Ineligible("input_contract")
    raw_path = value.get("source_path")
    if not isinstance(raw_path, str) or not raw_path:
        raise Ineligible("input_contract")
    refinement = value.get("refinement_contract")
    if not isinstance(refinement, Mapping) or set(refinement) != ALLOWED_REFINEMENT_KEYS:
        raise Ineligible("input_contract")
    if not isinstance(refinement.get("variant"), str) or not refinement.get("variant"):
        raise Ineligible("input_contract")
    return (
        Path(raw_path),
        _strict_hex(value.get("source_sha256")),
        _strict_endpoint(value.get("endpoint")),
        refinement,
    )


def _refinement_contract_missed(refinement: Mapping[str, object]) -> bool:
    status = refinement.get("status")
    return bool(
        isinstance(status, str)
        and status in MISS_REFINEMENT_STATUSES
        and refinement.get("numeric_v3_ready") is False
        and refinement.get("target_stability_ready") is not True
    )


def _source_document(path: Path, expected_sha256: str) -> tuple[bytes, Mapping[str, object]]:
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise Ineligible("source_contract")
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Ineligible("source_contract") from error
    if not isinstance(document, Mapping) or document.get("task") != "solve":
        raise Ineligible("source_contract")
    return payload, document


def _exact_target(target: object, context: Mapping[str, object]) -> sp.Expr:
    if isinstance(target, str):
        return sp.sympify(safe_eval_expr(target, dict(context)))
    if isinstance(target, bool):
        raise Ineligible("c2_exact_jh")
    if isinstance(target, int):
        return sp.Integer(target)
    if isinstance(target, float) and math.isfinite(target):
        return sp.Rational(str(target))
    return sp.sympify(target)


def _exact_system(document: Mapping[str, object]):
    try:
        bundle = load_problem_bundle(document, prefer_fast=False)
    except Exception as error:
        raise Ineligible("source_contract") from error
    names = tuple(bundle.var_names)
    if len(names) != 2 or len(bundle.spec.constraints) != 2 or len(bundle.targets) != 2:
        raise Ineligible("square_n2")
    symbols = tuple(sp.Symbol(f"z{index}", real=True) for index in range(2))
    context = dict(bundle.base_context)
    _assign_variables(context, list(names), list(symbols))
    try:
        for item in bundle.spec.construction:
            context[item.name] = safe_eval_expr(item.expr, context)
        residuals = tuple(
            sp.cancel(
                sp.together(
                    sp.sympify(safe_eval_expr(expression, context))
                    - _exact_target(bundle.targets[index], context)
                )
            )
            for index, expression in enumerate(bundle.spec.constraints)
        )
        jacobian = sp.Matrix(residuals).jacobian(symbols)
        hessians = tuple(sp.hessian(expression, symbols) for expression in residuals)
    except Exception as error:
        raise Ineligible("c2_exact_jh") from error
    operands = (*residuals, *tuple(jacobian), *(entry for matrix in hessians for entry in matrix))
    if any(
        not isinstance(item, sp.Expr)
        or item.has(*NON_C2_NODES)
        or item.has(sp.Derivative, sp.zoo, sp.nan, sp.oo, -sp.oo)
        for item in operands
    ):
        raise Ineligible("c2_exact_jh")
    return bundle, symbols, residuals, jacobian, hessians


def _real_float(expression: sp.Expr, substitutions: Mapping[sp.Symbol, float]) -> float:
    try:
        value = complex(sp.N(expression.subs(substitutions), 100))
    except Exception as error:
        raise Ineligible("c2_exact_jh") from error
    if not math.isfinite(value.real) or not math.isfinite(value.imag) or abs(value.imag) > 1.0e-60:
        raise Ineligible("c2_exact_jh")
    return float(value.real)


def _evaluate_exact_system(symbols, residuals, jacobian, hessians, endpoint):
    substitutions = dict(zip(symbols, endpoint, strict=True))
    residual = np.asarray(
        [_real_float(expression, substitutions) for expression in residuals],
        dtype=float,
    )
    j = np.asarray(
        [
            [_real_float(jacobian[row, column], substitutions) for column in range(2)]
            for row in range(2)
        ],
        dtype=float,
    )
    hs = np.asarray(
        [
            [
                [_real_float(matrix[row, column], substitutions) for column in range(2)]
                for row in range(2)
            ]
            for matrix in hessians
        ],
        dtype=float,
    )
    if not all(np.all(np.isfinite(value)) for value in (residual, j, hs)):
        raise Ineligible("c2_exact_jh")
    return residual, j, hs


def _source_scales(document: Mapping[str, object], endpoint: Sequence[float]) -> np.ndarray:
    scales = np.maximum(1.0, np.abs(np.asarray(endpoint, dtype=float)))
    bounds = document.get("bounds")
    if isinstance(bounds, list) and len(bounds) == 2:
        for index, pair in enumerate(bounds):
            if (
                isinstance(pair, list)
                and len(pair) == 2
                and all(
                    isinstance(item, (int, float))
                    and not isinstance(item, bool)
                    and math.isfinite(float(item))
                    for item in pair
                )
                and float(pair[0]) < float(pair[1])
            ):
                scales[index] = (float(pair[1]) - float(pair[0])) / 2.0
    return scales


def _normalized_corank_one(
    residual: np.ndarray,
    jacobian: np.ndarray,
    hessians: np.ndarray,
    variable_scales: np.ndarray,
) -> bool:
    coordinate = np.diag(variable_scales)
    j_scaled = jacobian @ coordinate
    h_scaled = np.asarray(
        [coordinate @ matrix @ coordinate for matrix in hessians], dtype=float
    )
    row_scales = np.asarray(
        [
            max(
                abs(float(residual[row])),
                float(np.linalg.norm(j_scaled[row], ord=2)),
                float(np.linalg.norm(h_scaled[row], ord="fro")),
            )
            for row in range(2)
        ],
        dtype=float,
    )
    if np.any(~np.isfinite(row_scales)) or np.any(row_scales <= 0.0):
        return False
    j_normalized = j_scaled / row_scales[:, None]
    h_normalized = h_scaled / row_scales[:, None, None]
    try:
        u, singular, vt = np.linalg.svd(j_normalized, full_matrices=True)
    except np.linalg.LinAlgError:
        return False
    if (
        singular.shape != (2,)
        or not np.all(np.isfinite(singular))
        or singular[0] <= 64.0 * np.finfo(float).eps
        or singular[1] / singular[0] >= NORMALIZED_CORANK_RATIO_MAX
    ):
        return False
    left_null = u[:, 1]
    right_null = vt[1, :]
    projected = np.asarray(
        [right_null @ matrix @ right_null for matrix in h_normalized], dtype=float
    )
    coefficient = abs(float(left_null @ projected))
    return bool(
        np.all(np.isfinite(projected))
        and coefficient
        > 64.0 * np.finfo(float).eps * max(1.0, float(np.linalg.norm(projected)))
    )


def _semantic_endpoint(bundle: object, endpoint: Sequence[float]) -> bool:
    try:
        evaluator = build_ir_evaluator(bundle)
        residual = evaluator.evaluate_float_residual(endpoint)
        guard_ok, _violations = evaluator.evaluate_guard(endpoint)
        hard = evaluator.evaluate_float_hard_feasibility(endpoint)
        residual_inf = float(residual.residual_norm_float)
    except Exception:
        return False
    return bool(
        getattr(residual, "is_finite", False)
        and math.isfinite(residual_inf)
        and residual_inf <= SOURCE_RESIDUAL_INF_MAX
        and guard_ok
        and hard.hard_feasible
    )


def _operator_histogram(expression: sp.Expr) -> tuple[tuple[str, int], ...]:
    counts = Counter(
        type(node).__name__
        for node in sp.preorder_traversal(expression)
        if not isinstance(node, (sp.Symbol, sp.Number))
    )
    return tuple(sorted(counts.items()))


def _structural_signature(residuals, jacobian, hessians) -> str:
    variants: list[str] = []
    for permutation in ((0, 1), (1, 0)):
        rows = []
        for row in range(2):
            rows.append(
                {
                    "operators": _operator_histogram(residuals[row]),
                    "j_zero": [
                        bool(jacobian[row, permutation[column]] == 0)
                        for column in range(2)
                    ],
                    "h_zero": [
                        bool(
                            hessians[row][permutation[first], permutation[second]]
                            == 0
                        )
                        for first in range(2)
                        for second in range(2)
                    ],
                }
            )
        variants.append(json.dumps(sorted(rows, key=repr), sort_keys=True, separators=(",", ":")))
    return hashlib.sha256(min(variants).encode()).hexdigest()


def scan_manifest(document: object) -> dict[str, object]:
    if (
        not isinstance(document, Mapping)
        or set(document) != {"schema_version", "records"}
        or document.get("schema_version") != INPUT_SCHEMA
        or not isinstance(document.get("records"), list)
    ):
        raise SystemExit("strict aggregate-only input manifest required")
    records = document["records"]
    counts = Counter({"input_record_count": len(records)})
    signatures: set[str] = set()
    for raw in records:
        try:
            source_path, source_sha256, endpoint, refinement = _strict_record(raw)
            counts["input_contract_count"] += 1
            _payload, source = _source_document(source_path, source_sha256)
            counts["source_contract_count"] += 1
            bundle, symbols, residuals, jacobian, hessians = _exact_system(source)
            counts["square_n2_count"] += 1
            if not _refinement_contract_missed(refinement):
                raise Ineligible("refinement_contract_miss")
            counts["refinement_contract_miss_count"] += 1
            if not _semantic_endpoint(bundle, endpoint):
                raise Ineligible("semantic_endpoint")
            counts["semantic_endpoint_count"] += 1
            residual, j, hs = _evaluate_exact_system(
                symbols, residuals, jacobian, hessians, endpoint
            )
            counts["c2_exact_jh_count"] += 1
            if not _normalized_corank_one(
                residual, j, hs, _source_scales(source, endpoint)
            ):
                raise Ineligible("normalized_corank1")
            counts["normalized_corank1_count"] += 1
            counts["eligible_count"] += 1
            signatures.add(_structural_signature(residuals, jacobian, hessians))
        except (Ineligible, OSError, TypeError, ValueError, OverflowError) as error:
            stage = error.stage if isinstance(error, Ineligible) else "input_contract"
            counts[f"rejected_{stage}_count"] += 1
    signature_count = len(signatures)
    eligible_count = counts["eligible_count"]
    gate_pass = eligible_count >= REQUIRED_ELIGIBLE and signature_count >= REQUIRED_SIGNATURES
    payload = {
        "schema_version": SCHEMA,
        "decision": "DYNAMIC_GATE_PASS" if gate_pass else "HOLD_REAL_APPLICABILITY_GATE",
        "gate_pass": gate_pass,
        "required_eligible_count": REQUIRED_ELIGIBLE,
        "required_signature_count": REQUIRED_SIGNATURES,
        "signature_count": signature_count,
        "counts": dict(sorted(counts.items())),
        "individual_paths_emitted": False,
        "individual_source_hashes_emitted": False,
        "individual_endpoints_emitted": False,
        "individual_signatures_emitted": False,
        "case_family_truth_score_outcome_fields_accepted_or_read": False,
        "proposal_or_authority_enabled": False,
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if sorted(os.sched_getaffinity(0)) != [14]:
        raise SystemExit("real applicability scanner must run on CPU14")
    source = json.loads(arguments.input.read_text(encoding="utf-8"))
    result = scan_manifest(source)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
