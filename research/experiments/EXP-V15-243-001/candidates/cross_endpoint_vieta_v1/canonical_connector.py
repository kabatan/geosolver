#!/usr/bin/env python3
"""Frozen canonical exact replay for a cross-endpoint Vieta proposal.

This module does not create authority.  It injects one already reconstructed,
irreducible target polynomial into the existing exact-coordinate DAG/QQBar
replay, while every coordinate descriptor is independently recognized from
the endpoint's two stored HP rungs.  The frozen replay still proves source
relations, guards, bounds, raw-answer equality, and every root ordinal.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from functools import reduce
from math import gcd
import struct
import sys
from typing import Any, Mapping, Sequence


HERE = Path(__file__).resolve().parent
CORE = HERE / "candidate.py"
RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
EXACT_ROOT = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/exact_coordinate_replay"
)
EXACT_CANDIDATE = EXACT_ROOT / "candidate.py"
EXACT_DAG = (
    RUNTIME_ROOT
    / "research/experiments/EXP-REAL61-004/qqbar_exact_replay/dag_compile.py"
)
EXACT_QQBAR = EXACT_DAG.with_name("qqbar_worker.jl")
PYTHON = RUNTIME_ROOT / "python/.venv/bin/python"
SCHEMA = "geotarget.cross-endpoint-vieta-canonical-replay/v1"
PRIVATE_SCHEMA = "geotarget.cross-endpoint-vieta-private-subset/v3"
LOW_BITS = 768
HIGH_BITS = 1024
MAX_SOURCE_BYTES = 4 * 1024 * 1024
MAX_TUPLE_DIMENSION = 64
MAX_CUSTODY_ARTIFACT_BYTES = 16 * 1024 * 1024

FROZEN_DEPENDENCIES = {
    CORE: "2c26493575c09ba788efdc0bff2d4e0db2a80f946ee7c0b0f41b5114da107f6d",
    EXACT_CANDIDATE: "e0f24e605e7e7211d134ddea66e66adbb89307148a8f03c1afebd4a2c969c66f",
    EXACT_DAG: "9b83181004a8ea2ea73f2974129e37ce252f7d352937b9f8b601b39eddf03d18",
    EXACT_QQBAR: "3ac6415600da77f8748a11d15fa47eb3dcb9f8deada375388fc762a155df0b4a",
    PYTHON: "ccc93c55c24bb92866cc2f9eff61b124abf5d1ee6c8da0ef9b5eed4d78a21f07",
}

FORBIDDEN_REQUEST_KEYS = frozenset(
    {
        "id",
        "case_id",
        "problem_id",
        "family",
        "family_id",
        "truth",
        "known_truth",
        "known_target",
        "expected_target",
        "expected_target_count",
        "gold",
        "score",
        "outcome",
        "historical_result",
    }
)
FORBIDDEN_SOURCE_KEYS = frozenset(
    {
        "case_id",
        "problem_id",
        "family",
        "family_id",
        "truth",
        "known_truth",
        "known_target",
        "expected_target",
        "expected_target_count",
        "gold",
        "score",
        "scorer_output",
        "outcome",
        "historical_result",
    }
)


class ConnectorFailure(RuntimeError):
    pass


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _valid_sha(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def verify_frozen_dependencies() -> dict[str, str]:
    observed = {
        str(path): _sha256(path.read_bytes()) if path.is_file() else "MISSING"
        for path in FROZEN_DEPENDENCIES
    }
    expected = {str(path): digest for path, digest in FROZEN_DEPENDENCIES.items()}
    if observed != expected:
        raise ConnectorFailure("frozen Vieta/canonical replay closure changed")
    return observed


def _contains_forbidden_key(value: Any, forbidden: frozenset[str]) -> bool:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key).lower().replace("-", "_")
            if key in forbidden or _contains_forbidden_key(item, forbidden):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_key(item, forbidden) for item in value)
    return False


def _source(path: Path, expected_sha256: str) -> tuple[bytes, dict[str, Any]]:
    payload = path.read_bytes()
    if (
        not payload
        or len(payload) > MAX_SOURCE_BYTES
        or not _valid_sha(expected_sha256)
        or _sha256(payload) != expected_sha256
    ):
        raise ConnectorFailure("source bytes or SHA-256 changed")
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConnectorFailure("source is not JSON") from error
    variables = document.get("variables") if isinstance(document, Mapping) else None
    names = variables.get("names") if isinstance(variables, Mapping) else None
    if (
        not isinstance(document, dict)
        or document.get("task") != "solve"
        or "id" in document
        or not isinstance(names, list)
        or not names
        or len(names) > MAX_TUPLE_DIMENSION
        or not all(isinstance(name, str) and name for name in names)
        or document.get("post_process") not in (None, "")
        or _contains_forbidden_key(document, FORBIDDEN_SOURCE_KEYS)
    ):
        raise ConnectorFailure("source projection is outside exact solve authority")
    return payload, document


def _endpoint_sha256(bits: Sequence[str]) -> str:
    if not bits or not all(
        isinstance(value, str)
        and len(value) == 16
        and all(character in "0123456789abcdef" for character in value)
        for value in bits
    ):
        raise ConnectorFailure("endpoint Float64 bits are malformed")
    payload = struct.pack(">I", len(bits)) + b"".join(bytes.fromhex(value) for value in bits)
    values = [struct.unpack(">d", bytes.fromhex(value))[0] for value in bits]
    if not all(math.isfinite(value) for value in values):
        raise ConnectorFailure("endpoint contains non-finite Float64")
    return _sha256(payload)


def _artifact(value: object, label: str) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    if not isinstance(value, Mapping) or set(value) != {"path", "sha256"}:
        raise ConnectorFailure(f"{label} artifact binding schema changed")
    path = Path(str(value.get("path")))
    expected = value.get("sha256")
    payload = path.read_bytes()
    if (
        not payload
        or len(payload) > MAX_CUSTODY_ARTIFACT_BYTES
        or not _valid_sha(expected)
        or _sha256(payload) != expected
    ):
        raise ConnectorFailure(f"{label} artifact bytes or digest changed")
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConnectorFailure(f"{label} artifact is not JSON") from error
    if not isinstance(document, dict):
        raise ConnectorFailure(f"{label} artifact is not an object")
    return {"path": path, "sha256": expected}, payload, document


def _plan_endpoint_bits(plan: Mapping[str, Any]) -> tuple[str, ...]:
    endpoint = plan.get("endpoint")
    if not isinstance(endpoint, list) or not endpoint:
        raise ConnectorFailure("original PLAN endpoint is absent")
    try:
        values = [float(value) for value in endpoint]
    except (TypeError, ValueError, OverflowError) as error:
        raise ConnectorFailure("original PLAN endpoint is malformed") from error
    if not all(math.isfinite(value) for value in values):
        raise ConnectorFailure("original PLAN endpoint is non-finite")
    return tuple(struct.pack(">d", value).hex() for value in values)


def _hp_provenance_sha256(
    *,
    result_sha256: str,
    plan_sha256: str,
    lane_sha256: str,
    source_sha256: str,
    endpoint_bits: Sequence[str],
    endpoint_sha256: str,
    precision_bits: int,
) -> str:
    binding = {
        "schema_version": "geotarget.cross-endpoint-vieta-hp-provenance/v1",
        "result_bytes_sha256": result_sha256,
        "plan_bytes_sha256": plan_sha256,
        "lane_bytes_sha256": lane_sha256,
        "source_projection_sha256": source_sha256,
        "endpoint_float64_bits_hex": list(endpoint_bits),
        "endpoint_float64_sha256": endpoint_sha256,
        "precision_bits": precision_bits,
    }
    return _sha256(json.dumps(binding, sort_keys=True, separators=(",", ":")).encode())


def subset_sha256(source_sha256: str, endpoint_sha256: Sequence[str]) -> str:
    if not _valid_sha(source_sha256) or not 2 <= len(endpoint_sha256) <= 6:
        raise ConnectorFailure("subset source or degree is invalid")
    if len(set(endpoint_sha256)) != len(endpoint_sha256) or not all(
        _valid_sha(value) for value in endpoint_sha256
    ):
        raise ConnectorFailure("subset endpoint SHA set is invalid")
    digest = hashlib.sha256()
    digest.update(b"vieta-subset-v1")
    digest.update(bytes.fromhex(source_sha256))
    for value in sorted(endpoint_sha256):
        digest.update(bytes.fromhex(value))
    return digest.hexdigest()


def _rung(
    value: object,
    *,
    precision_bits: int,
    dimension: int,
    source_sha256: str,
    endpoint_bits: Sequence[str],
    endpoint_sha256: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "precision_bits",
        "provenance_sha256",
        "raw_answer_decimal",
        "full_tuple_decimal",
        "result_artifact",
        "plan_artifact",
        "lane_artifact",
    }:
        raise ConnectorFailure("HP rung schema changed")
    coordinates = value.get("full_tuple_decimal")
    if (
        value.get("precision_bits") != precision_bits
        or not _valid_sha(value.get("provenance_sha256"))
        or not isinstance(value.get("raw_answer_decimal"), str)
        or not isinstance(coordinates, list)
        or len(coordinates) != dimension
        or not all(isinstance(item, str) and item for item in coordinates)
    ):
        raise ConnectorFailure("HP rung binding is malformed")
    try:
        decimals = [
            Decimal(value["raw_answer_decimal"]),
            *(Decimal(item) for item in coordinates),
        ]
    except (InvalidOperation, ValueError) as error:
        raise ConnectorFailure("HP rung decimal is malformed") from error
    if not all(item.is_finite() for item in decimals):
        raise ConnectorFailure("HP rung contains a non-finite decimal")
    result_binding, _result_payload, result = _artifact(
        value["result_artifact"], "original RESULT"
    )
    plan_binding, _plan_payload, plan = _artifact(
        value["plan_artifact"], "original PLAN"
    )
    lane_binding, _lane_payload, lane = _artifact(
        value["lane_artifact"], "original HP lane"
    )
    if (
        result.get("schema_version")
        != "geotarget.exp008-single-raw-endpoint-hp-result/v1"
        or result.get("status") != "COMPLETE"
        or result.get("process_classification") != "SUCCESS"
        or result.get("artifact_accepted") is not True
        or result.get("authority_pass") is not True
        or result.get("source_sha256") != source_sha256
        or result.get("endpoint_float64_sha256") != endpoint_sha256
        or result.get("artifact_sha256") != lane_binding["sha256"]
        or result.get("truth_read") is not False
        or result.get("case_or_family_identity_read") is not False
        or result.get("source_or_problem_modified") is not False
        or result.get("bounds_or_gauge_added") is not False
        or result.get("endpoint_unchanged_before_refinement") is not True
        or result.get("transitive_implementation_current_at_result_write") is not True
    ):
        raise ConnectorFailure("original RESULT authority binding changed")
    if (
        plan.get("schema_version")
        != "geotarget.exp008-single-raw-endpoint-hp-plan/v1"
        or plan.get("source_sha256") != source_sha256
        or plan.get("endpoint_float64_sha256") != endpoint_sha256
        or _plan_endpoint_bits(plan) != tuple(endpoint_bits)
        or plan.get("truth_read") is not False
        or plan.get("case_or_family_identity_read") is not False
        or plan.get("source_or_problem_modified") is not False
        or plan.get("bounds_or_gauge_added") is not False
        or plan.get("endpoint_unchanged_before_refinement") is not True
    ):
        raise ConnectorFailure("original PLAN source/endpoint binding changed")
    final = lane.get("final_result")
    numeric = final.get("original_numerical_replay") if isinstance(final, Mapping) else None
    lanes = numeric.get("lanes") if isinstance(numeric, Mapping) else None
    scope = final.get("authority_scope") if isinstance(final, Mapping) else None
    float64_replay = final.get("float64_replay") if isinstance(final, Mapping) else None
    transformations = final.get("problem_transformations") if isinstance(final, Mapping) else None
    input_contract = final.get("input_contract") if isinstance(final, Mapping) else None
    matches = [
        item
        for item in lanes or []
        if isinstance(item, Mapping) and item.get("bits") == precision_bits
    ]
    if (
        lane.get("schema_version")
        != "geotarget.exp008-target-first-fallback-composition/v1"
        or lane.get("status") != "TARGET_AUTHORITY_READY"
        or lane.get("authority_pass") is not True
        or not isinstance(final, Mapping)
        or final.get("status") != "TARGET_AUTHORITY_READY"
        or final.get("source_raw_sha256") != source_sha256
        or final.get("endpoint_float64_sha256") != endpoint_sha256
        or final.get("authority_pass") is not True
        or not isinstance(input_contract, Mapping)
        or input_contract.get("source_bytes_and_digest") is not True
        or input_contract.get("bare_float64_endpoint") is not True
        or input_contract.get("truth") is not False
        or input_contract.get("known_target_count") is not False
        or input_contract.get("case_id") is not False
        or input_contract.get("family") is not False
        or not isinstance(transformations, Mapping)
        or any(value is not False for value in transformations.values())
        or not isinstance(float64_replay, Mapping)
        or float64_replay.get("semantic_valid") is not True
        or float64_replay.get("hard_feasible") is not True
        or float64_replay.get("guard_ok") is not True
        or float64_replay.get("intrinsic_domain_ok") is not True
        or not isinstance(numeric, Mapping)
        or numeric.get("numeric_v3_ready") is not True
        or not isinstance(scope, Mapping)
        or scope.get("original_dsl_hp_replay") is not True
        or len(matches) != 1
    ):
        raise ConnectorFailure("original numeric guard/branch replay authority changed")
    original_lane = matches[0]
    if (
        original_lane.get("finite") is not True
        or original_lane.get("hard_feasible") is not True
        or original_lane.get("guard_ok") is not True
        or original_lane.get("guard_violations") != []
        or original_lane.get("raw_hard_feasible_without_intrinsic_domains") is not True
        or original_lane.get("intrinsic_domain_ok") is not True
        or original_lane.get("intrinsic_domain_violations") != []
        or original_lane.get("point") != list(coordinates)
        or original_lane.get("answer") != value["raw_answer_decimal"]
    ):
        raise ConnectorFailure("requested HP rung differs from original numeric replay lane")
    expected_provenance = _hp_provenance_sha256(
        result_sha256=result_binding["sha256"],
        plan_sha256=plan_binding["sha256"],
        lane_sha256=lane_binding["sha256"],
        source_sha256=source_sha256,
        endpoint_bits=endpoint_bits,
        endpoint_sha256=endpoint_sha256,
        precision_bits=precision_bits,
    )
    if value["provenance_sha256"] != expected_provenance:
        raise ConnectorFailure("HP rung provenance is not the canonical original-artifact binding")
    return {
        "precision_bits": precision_bits,
        "provenance_sha256": value["provenance_sha256"],
        "raw_answer_decimal": value["raw_answer_decimal"],
        "full_tuple_decimal": tuple(coordinates),
        "result_artifact": result_binding,
        "plan_artifact": plan_binding,
        "lane_artifact": lane_binding,
        "numeric_guard_branch_parity": True,
    }


def validate_private_subset(value: object) -> dict[str, Any]:
    if (
        not isinstance(value, Mapping)
        or set(value)
        != {"schema_version", "source", "source_sha256", "subset_sha256", "endpoints"}
        or value.get("schema_version") != PRIVATE_SCHEMA
        or _contains_forbidden_key(value, FORBIDDEN_REQUEST_KEYS)
    ):
        raise ConnectorFailure("private subset schema or truth boundary changed")
    source_path = Path(str(value.get("source")))
    source_sha = value.get("source_sha256")
    source_payload, document = _source(source_path, str(source_sha))
    dimension = len(document["variables"]["names"])
    raw_endpoints = value.get("endpoints")
    if not isinstance(raw_endpoints, list) or not 2 <= len(raw_endpoints) <= 6:
        raise ConnectorFailure("private subset degree is outside 2 through 6")
    endpoints: list[dict[str, Any]] = []
    endpoint_shas: list[str] = []
    for raw in raw_endpoints:
        if not isinstance(raw, Mapping) or set(raw) != {
            "endpoint_float64_bits_hex",
            "endpoint_float64_sha256",
            "low",
            "high",
        }:
            raise ConnectorFailure("private endpoint schema changed")
        bits = raw.get("endpoint_float64_bits_hex")
        if not isinstance(bits, list) or len(bits) != dimension:
            raise ConnectorFailure("endpoint Float64 dimension changed")
        endpoint_sha = raw.get("endpoint_float64_sha256")
        if _endpoint_sha256(bits) != endpoint_sha:
            raise ConnectorFailure("endpoint Float64 SHA-256 changed")
        low = _rung(
            raw.get("low"),
            precision_bits=LOW_BITS,
            dimension=dimension,
            source_sha256=str(source_sha),
            endpoint_bits=bits,
            endpoint_sha256=str(endpoint_sha),
        )
        high = _rung(
            raw.get("high"),
            precision_bits=HIGH_BITS,
            dimension=dimension,
            source_sha256=str(source_sha),
            endpoint_bits=bits,
            endpoint_sha256=str(endpoint_sha),
        )
        if low["provenance_sha256"] == high["provenance_sha256"]:
            raise ConnectorFailure("HP rung provenance is not independent")
        endpoint_shas.append(str(endpoint_sha))
        endpoints.append(
            {
                "endpoint_float64_bits_hex": tuple(bits),
                "endpoint_float64_sha256": endpoint_sha,
                "low": low,
                "high": high,
            }
        )
    if subset_sha256(str(source_sha), endpoint_shas) != value.get("subset_sha256"):
        raise ConnectorFailure("subset custody digest changed")
    return {
        "source": source_path,
        "source_sha256": source_sha,
        "source_payload": source_payload,
        "source_document": document,
        "subset_sha256": value["subset_sha256"],
        "endpoints": tuple(endpoints),
    }


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ConnectorFailure("frozen module cannot be loaded")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def load_core_and_exact():
    verify_frozen_dependencies()
    core = _load("geotarget_cross_endpoint_vieta_frozen_core", CORE)
    exact = _load("geotarget_cross_endpoint_vieta_frozen_exact", EXACT_CANDIDATE)
    return core, exact


def _vieta_polynomial(exact: Any, coefficients: Sequence[int]):
    if (
        not 3 <= len(coefficients) <= 7
        or not all(isinstance(value, int) and not isinstance(value, bool) for value in coefficients)
        or coefficients[0] <= 0
        or reduce(gcd, (abs(value) for value in coefficients), 0) != 1
    ):
        raise ConnectorFailure("Vieta polynomial descriptor is not primitive degree 2 through 6")
    symbol = exact.sp.Symbol("x")
    polynomial = exact.sp.Poly.from_list(list(coefficients), gens=symbol, domain=exact.sp.ZZ)
    if polynomial.is_sqf is not True:
        raise ConnectorFailure("Vieta polynomial is not square-free")
    return polynomial


def _factor_proposal(exact: Any, polynomial: Any, interval: Mapping[str, Any], target: str):
    coefficients = [int(value) for value in polynomial.all_coeffs()]
    if polynomial.is_sqf is not True or polynomial.is_irreducible is not True:
        raise ConnectorFailure("canonical target factor is not square-free irreducible over Q")
    with exact.mp.workdps(260):
        approximation = exact.mp.mpf(str(target))
        if not exact.mp.isfinite(approximation):
            raise ConnectorFailure("high target is not finite")
        residual = abs(exact._mp_poly_value(polynomial, approximation))
    return {
        "status": "ALGEBRAIC_PROPOSAL",
        "coefficients_high_to_low": coefficients,
        "polynomial_metadata": {
            "square_free": True,
            "irreducible_over_Q": True,
            "isolating_interval": dict(interval),
        },
        "independent_confirmation_residual": exact.mp.nstr(residual, 160),
        "numeric_lanes_used_only_for_proposal": True,
        "proposal_mechanism": "CROSS_ENDPOINT_VIETA_IRREDUCIBLE_FACTOR",
        "vieta_whole_polynomial_used_as_minimal_descriptor": False,
        "target_set_completeness_claim": False,
    }


def _matching_factor(
    exact: Any,
    factors: Sequence[Any],
    target: str,
) -> tuple[int, dict[str, Any]]:
    matches: list[tuple[int, dict[str, Any]]] = []
    with exact.mp.workdps(260):
        approximation = exact.mp.mpf(str(target))
        if not exact.mp.isfinite(approximation):
            raise ConnectorFailure("factor target lane is not finite")
        for index, factor in enumerate(factors):
            try:
                interval = exact._interval_descriptor(factor, approximation)
            except Exception:
                continue
            matches.append((index, interval))
    if len(matches) != 1:
        raise ConnectorFailure("target numeric box does not select exactly one irreducible factor")
    return matches[0]


def prepare_factorized_targets(
    *,
    exact: Any,
    endpoints: Sequence[Mapping[str, Any]],
    coefficients: Sequence[int],
    subset_root_ordinals: Sequence[int],
) -> tuple[dict[str, Any], ...]:
    """Factor the Vieta polynomial and bind every HP endpoint to one factor.

    The reducible whole Vieta polynomial is never serialized as a target
    descriptor.  Low and high rungs must independently choose the same unique
    primitive irreducible factor and the same factor-local real-root ordinal.
    Only the roots actually observed and independently replayed can be emitted;
    no unobserved conjugate is synthesized and completeness remains false.  A
    factor/isolator failure is endpoint-local so a valid sibling is retained.
    """

    polynomial = _vieta_polynomial(exact, coefficients)
    degree = int(polynomial.degree())
    if len(endpoints) != degree or len(subset_root_ordinals) != degree:
        raise ConnectorFailure("Vieta factorization endpoint degree changed")
    if (
        any(
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value < degree
            for value in subset_root_ordinals
        )
        or set(subset_root_ordinals) != set(range(degree))
    ):
        raise ConnectorFailure("Vieta subset root ordinals are not a complete ordering")
    factorization = exact.sp.factor_list(polynomial)
    raw_factors = factorization[1]
    if not raw_factors or any(multiplicity != 1 for _factor, multiplicity in raw_factors):
        raise ConnectorFailure("Vieta factorization contains a repeated factor")
    factors = [exact.sp.Poly(factor, polynomial.gens[0], domain=exact.sp.ZZ) for factor, _ in raw_factors]
    if any(factor.is_sqf is not True or factor.is_irreducible is not True for factor in factors):
        raise ConnectorFailure("Vieta factorization did not yield irreducible square-free factors")

    high_targets = [Decimal(endpoint["high"]["raw_answer_decimal"]) for endpoint in endpoints]
    expected_ordinals = [0] * degree
    for ordinal, endpoint_index in enumerate(sorted(range(degree), key=high_targets.__getitem__)):
        expected_ordinals[endpoint_index] = ordinal
    if tuple(expected_ordinals) != tuple(subset_root_ordinals):
        raise ConnectorFailure("Vieta subset ordinal does not match the independently parsed HP lane")

    assignments: list[tuple[int, dict[str, Any]] | None] = []
    reasons: list[str | None] = []
    for endpoint in endpoints:
        try:
            low_factor, low_interval = _matching_factor(
                exact, factors, endpoint["low"]["raw_answer_decimal"]
            )
            high_factor, high_interval = _matching_factor(
                exact, factors, endpoint["high"]["raw_answer_decimal"]
            )
            if low_factor != high_factor or low_interval != high_interval:
                raise ConnectorFailure(
                    "independent HP rungs disagree on factor or factor-root ordinal"
                )
            assignments.append((high_factor, high_interval))
            reasons.append(None)
        except Exception:
            assignments.append(None)
            reasons.append("FACTOR_OR_FACTOR_ROOT_NOT_UNIQUE_ACROSS_INDEPENDENT_RUNGS")

    intervals: list[tuple[Fraction, Fraction] | None] = []
    for index, assignment in enumerate(assignments):
        if assignment is None:
            intervals.append(None)
            continue
        try:
            left = Fraction(str(assignment[1]["left"]))
            right = Fraction(str(assignment[1]["right"]))
            if left > right:
                raise ValueError("reversed")
        except (KeyError, ValueError, ZeroDivisionError):
            assignments[index] = None
            reasons[index] = "FACTOR_ISOLATOR_MALFORMED"
            intervals.append(None)
            continue
        intervals.append((left, right))
    for left_index, left_interval in enumerate(intervals):
        if left_interval is None:
            continue
        for right_index in range(left_index + 1, len(intervals)):
            right_interval = intervals[right_index]
            if right_interval is not None and max(
                left_interval[0], right_interval[0]
            ) <= min(left_interval[1], right_interval[1]):
                assignments[left_index] = None
                assignments[right_index] = None
                reasons[left_index] = "OBSERVED_ROOT_ISOLATOR_OVERLAPS_SIBLING"
                reasons[right_index] = "OBSERVED_ROOT_ISOLATOR_OVERLAPS_SIBLING"

    result: list[dict[str, Any]] = []
    for endpoint, assignment, reason in zip(endpoints, assignments, reasons, strict=True):
        if assignment is None:
            result.append({"status": "FACTOR_REJECTED", "reason": reason})
            continue
        factor_index, interval = assignment
        proposal = _factor_proposal(
            exact,
            factors[factor_index],
            interval,
            endpoint["high"]["raw_answer_decimal"],
        )
        descriptor = exact._qqbar_descriptor(proposal)
        identity = _sha256(
            json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode()
        )
        result.append(
            {
                "status": "FACTOR_READY",
                "reason": "INDEPENDENT_RUNGS_SELECT_UNIQUE_IRREDUCIBLE_FACTOR_ROOT",
                "target_proposal": proposal,
                "descriptor_identity_sha256": identity,
                "factor_local_real_root_ordinal": int(
                    descriptor["isolating_interval"]["real_root_index"]
                ),
                "product_global_root_ordinal_used": False,
                "unobserved_root_emitted": False,
            }
        )
    return tuple(result)


def canonical_replay_endpoint(
    *,
    exact: Any,
    source_document: Mapping[str, Any],
    endpoint: Mapping[str, Any],
    target_proposal: Mapping[str, Any],
    timeout_seconds: float,
) -> bool:
    """Run the unchanged exact DAG/QQBar source replay for one full tuple."""

    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0.25:
        raise ConnectorFailure("canonical replay timeout is invalid")
    low = endpoint["low"]
    high = endpoint["high"]
    coordinate_proposals = [
        exact.recognize_algebraic(left, right, max_degree=8, max_coeff=10**12)
        for left, right in zip(
            low["full_tuple_decimal"], high["full_tuple_decimal"], strict=True
        )
    ]
    if (
        target_proposal.get("proposal_mechanism")
        != "CROSS_ENDPOINT_VIETA_IRREDUCIBLE_FACTOR"
        or target_proposal.get("vieta_whole_polynomial_used_as_minimal_descriptor")
        is not False
    ):
        raise ConnectorFailure("canonical replay did not receive a factor-only target descriptor")
    target_root_ordinal = int(
        exact._qqbar_descriptor(target_proposal)["isolating_interval"]["real_root_index"]
    )
    prepared, _lowering = exact.prepare_document(source_document)
    job = exact.DAG.compile_document(
        prepared,
        coordinate_descriptors=[exact._job_descriptor(item) for item in coordinate_proposals],
        target_descriptor=exact._job_descriptor(target_proposal),
    )
    exact._normalize_exact_guard_calls(job)
    replay = exact._run_qqbar(job, timeout_seconds=timeout_seconds)
    if not isinstance(replay, Mapping) or replay.get("status") != "EXACT_REPLAY_ACCEPTED":
        return False
    coordinate_ordinals = [
        int(exact._qqbar_descriptor(item)["isolating_interval"]["real_root_index"])
        for item in coordinate_proposals
    ]
    exact._validate_replay_terminal(
        replay,
        document=prepared,
        coordinate_root_indices=coordinate_ordinals,
        target_root_index=target_root_ordinal,
    )
    attestation = replay.get("target_root_attestation")
    return bool(
        replay.get("truth_used") is False
        and replay.get("post_process_used") is False
        and replay.get("completeness_claim_permitted") is False
        and replay.get("target_image_completeness") == "NOT_RUN"
        and replay.get("source_raw_answer_exact") is True
        and replay.get("target_link_exact") is True
        and replay.get("root_ordinal_attestation_complete") is True
        and isinstance(attestation, Mapping)
        and attestation.get("claimed_real_root_index") == target_root_ordinal
        and attestation.get("attested_real_root_index") == target_root_ordinal
        and attestation.get("index_match") is True
        and attestation.get("multiplicity") == 1
    )


def structural_signature(document: Mapping[str, Any]) -> str:
    """Anonymous source-semantics shape; never emitted individually."""

    construction = document.get("construction")
    constraints = document.get("constraints")
    guards = document.get("guards") or []
    variables = document.get("variables")
    names = variables.get("names") if isinstance(variables, Mapping) else []
    if not isinstance(construction, list) or not isinstance(constraints, list):
        raise ConnectorFailure("source structural signature fields are malformed")

    def expression_shape(text: object) -> str:
        if not isinstance(text, str):
            return "MALFORMED"
        tokens = []
        current = ""
        for character in text:
            if character.isalpha() or character == "_":
                current += character
            else:
                if current:
                    tokens.append(current)
                    current = ""
                if character in "+-*/<>=()":
                    tokens.append(character)
        if current:
            tokens.append(current)
        variable_set = set(names) if isinstance(names, list) else set()
        return " ".join("VAR" if token in variable_set else token for token in tokens)

    payload = {
        "dimension": len(names) if isinstance(names, list) else -1,
        "construction": [
            expression_shape(item.get("expr")) if isinstance(item, Mapping) else "MALFORMED"
            for item in construction
        ],
        "constraints": [
            expression_shape(item.get("def")) if isinstance(item, Mapping) else "MALFORMED"
            for item in constraints
        ],
        "guards": [expression_shape(item) for item in guards] if isinstance(guards, list) else [],
    }
    return _sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
