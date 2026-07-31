"""Byte-bound ordinary proposal input for the selected msolve exact worker.

The historical degree-one projection was only an activation pilot.  This
module binds the complete frozen ordinary HP attempt and revalidates its
primitive square-free irreducible degree-1/2/4 descriptor, factor-local real
root isolator, and zero-based real-root ordinal.  It never grants authority or
target-set completeness.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import struct
import sys
from typing import Any, Mapping

import sympy as sp


SCHEMA = "geotarget.msolve-ordinary-proposal-binding/v1"
PROPOSAL_SCHEMA = "geotarget.frozen-ordinary-proposal/v2"
LEGACY_PROPOSAL_SCHEMA = "geotarget.frozen-ordinary-degree1-proposal/v1"
APPROVED_PANEL_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results/target-constrained-nra-ordinary-binding-v1"
).resolve()
APPROVED_SOURCE_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-inputs"
).resolve()
APPROVED_PROPOSAL_ROOT = (APPROVED_PANEL_ROOT / "ordinary-proposals").resolve()
APPROVED_ORIGINAL_RESULT_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results/formal-control-development145-180-seed0/artifacts"
).resolve()
APPROVED_ORIGINAL_INPUT_ROOT = (
    APPROVED_ORIGINAL_RESULT_ROOT.parent / "inputs"
).resolve()
AUTHORITY_BOUNDARY_PATH = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/candidates/exact_outer_decorator/authority_boundary.py"
)
AUTHORITY_BOUNDARY_SHA256 = (
    "a36520a416d0b8c900bca6b79192c7014812c9b1270be09248347f0f19e167e9"
)
ROW_KEYS = frozenset(
    {
        "source_rel",
        "source_sha256",
        "endpoint_float64_bits_hex",
        "endpoint_float64_sha256",
        "proposal_result_rel",
        "proposal_sha256",
    }
)
LEGACY_ROW_KEYS = ROW_KEYS | {"degree1_descriptor"}
PROPOSAL_KEYS = frozenset(
    {
        "schema_version",
        "source_sha256",
        "endpoint_float64_sha256",
        "original_result_sha256",
        "ordinary_attempt_sha256",
        "ordinary_attempt",
        "truth_used",
        "case_family_target_count_routing",
    }
)
MAX_SOURCE_BYTES = 64 * 1024
MAX_PROPOSAL_BYTES = 256 * 1024
ALLOWED_DESCRIPTOR_DEGREES = frozenset({1, 2, 4})
MAX_COEFFICIENT_BITS = 4096
ORIGINAL_RESULT_SCHEMA = "geotarget.exp008-finalist-numeric-worker-v15/v1"
ORIGINAL_PLAN_SCHEMA = "geotarget.exp008-single-raw-endpoint-hp-plan/v1"


class OrdinaryBindingRejected(ValueError):
    """The complete ordinary artifact was not bound exactly."""


@dataclass(frozen=True)
class BoundOrdinaryProposal:
    source_path: Path
    source_bytes: bytes
    source: Mapping[str, Any]
    source_sha256: str
    endpoint: tuple[float, ...]
    endpoint_float64_sha256: str
    proposal_path: Path
    proposal_bytes: bytes
    proposal_sha256: str
    original_result_sha256: str
    ordinary_attempt_sha256: str
    ordinary_descriptor: Mapping[str, Any]
    ordinary_descriptor_sha256: str
    target_descriptor: Mapping[str, Any]
    target_descriptor_sha256: str
    polynomial_coefficients_high_to_low: tuple[int, ...]
    selected_real_root_index: int
    binding_statement: Mapping[str, Any]
    binding_statement_sha256: str
    authority_pass: bool = False
    target_release: bool = False
    completeness_claim: str = "NOT_MADE"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return sha256_bytes(canonical_bytes(value))


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64 or value.lower() != value:
        return False
    try:
        bytes.fromhex(value)
    except ValueError:
        return False
    return True


def _load_boundary():
    if (
        not AUTHORITY_BOUNDARY_PATH.is_file()
        or sha256_bytes(AUTHORITY_BOUNDARY_PATH.read_bytes())
        != AUTHORITY_BOUNDARY_SHA256
    ):
        raise OrdinaryBindingRejected("AUTHORITY_BOUNDARY_SHA256_MISMATCH")
    name = "msolve_ordinary_binding_frozen_authority_boundary"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, AUTHORITY_BOUNDARY_PATH)
    if specification is None or specification.loader is None:
        raise OrdinaryBindingRejected("AUTHORITY_BOUNDARY_UNAVAILABLE")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _bounded_file(root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise OrdinaryBindingRejected("RELATIVE_ARTIFACT_PATH_MALFORMED")
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise OrdinaryBindingRejected("ARTIFACT_PATH_ESCAPED_CUSTODY_ROOT") from error
    if (
        path.suffix != ".json"
        or path.is_symlink()
        or not path.is_file()
        or not stat.S_ISREG(path.lstat().st_mode)
    ):
        raise OrdinaryBindingRejected("ARTIFACT_IS_NOT_REGULAR_JSON")
    return path


def _read_json_bytes(path: Path, *, cap: int, label: str) -> tuple[Mapping[str, Any], bytes]:
    payload = path.read_bytes()
    if not 1 <= len(payload) <= cap:
        raise OrdinaryBindingRejected(f"{label}_BYTE_CAP")
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OrdinaryBindingRejected(f"{label}_NOT_JSON") from error
    if not isinstance(document, Mapping):
        raise OrdinaryBindingRejected(f"{label}_NOT_MAPPING")
    return document, payload


def endpoint_from_bits(value: object) -> tuple[float, ...]:
    if not isinstance(value, list) or not value:
        raise OrdinaryBindingRejected("ENDPOINT_BITS_MALFORMED")
    result = []
    for item in value:
        if not isinstance(item, str) or len(item) != 16 or item.lower() != item:
            raise OrdinaryBindingRejected("ENDPOINT_BITS_MALFORMED")
        try:
            number = struct.unpack(">d", bytes.fromhex(item))[0]
        except (ValueError, struct.error) as error:
            raise OrdinaryBindingRejected("ENDPOINT_BITS_MALFORMED") from error
        if not math.isfinite(number):
            raise OrdinaryBindingRejected("ENDPOINT_BITS_NONFINITE")
        result.append(number)
    return tuple(result)


def endpoint_sha256(endpoint: tuple[float, ...]) -> str:
    payload = struct.pack(">I", len(endpoint)) + b"".join(
        struct.pack(">d", value) for value in endpoint
    )
    return sha256_bytes(payload)


def _command_argument(command: object, flag: str) -> str:
    if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
        raise OrdinaryBindingRejected("ORIGINAL_PLAN_COMMAND_MALFORMED")
    positions = [index for index, item in enumerate(command) if item == flag]
    if len(positions) != 1 or positions[0] + 1 >= len(command):
        raise OrdinaryBindingRejected("ORIGINAL_PLAN_COMMAND_BINDING_MISSING")
    return command[positions[0] + 1]


def _original_result(expected_sha256: object) -> tuple[Mapping[str, Any], bytes, Path]:
    if not _is_sha256(expected_sha256):
        raise OrdinaryBindingRejected("ORIGINAL_RESULT_SHA256_MALFORMED")
    matches: list[tuple[Mapping[str, Any], bytes, Path]] = []
    for directory, directory_names, filenames in os.walk(
        APPROVED_ORIGINAL_RESULT_ROOT, followlinks=False
    ):
        root = Path(directory)
        directory_names[:] = [name for name in directory_names if not (root / name).is_symlink()]
        if "RESULT.json" not in filenames:
            continue
        path = (root / "RESULT.json").resolve()
        try:
            path.relative_to(APPROVED_ORIGINAL_RESULT_ROOT)
        except ValueError as error:
            raise OrdinaryBindingRejected("ORIGINAL_RESULT_ESCAPED_CUSTODY") from error
        payload = path.read_bytes()
        if sha256_bytes(payload) != expected_sha256:
            continue
        try:
            document = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OrdinaryBindingRejected("ORIGINAL_RESULT_NOT_JSON") from error
        if isinstance(document, Mapping):
            matches.append((document, payload, path))
    if len(matches) != 1:
        raise OrdinaryBindingRejected("ORIGINAL_RESULT_SHA256_NOT_UNIQUE")
    return matches[0]


def _verify_original_result_contract(original: Mapping[str, Any]) -> None:
    if not (
        original.get("schema_version") == ORIGINAL_RESULT_SCHEMA
        and original.get("status") == "SEARCH_DEADLINE_REACHED"
        and _is_sha256(original.get("source_sha256"))
        and isinstance(original.get("hp_attempts"), list)
        and original.get("truth_case_family_known_target_count_read") is False
        and original.get("source_bytes_unchanged") is True
        and original.get("source_or_problem_modified") is False
        and original.get("variables_or_equations_removed") is False
        and original.get("bounds_added_or_inferred") is False
        and original.get("gauge_or_symmetry_reduction") is False
        and original.get("coordinate_reparameterization") is False
        and original.get("target_image_completeness_claim") is False
    ):
        raise OrdinaryBindingRejected("ORIGINAL_RESULT_PROVENANCE_REJECTED")


def _verify_original_plan_contract(
    plan: Mapping[str, Any], *, original_source_sha256: str
) -> None:
    if not (
        plan.get("schema_version") == ORIGINAL_PLAN_SCHEMA
        and plan.get("status") == "DRY_RUN_NOT_STARTED"
        and plan.get("source_sha256") == original_source_sha256
        and _is_sha256(plan.get("worker_sha256"))
        and isinstance(plan.get("execution_environment_contract"), Mapping)
        and isinstance(plan.get("transitive_implementation_manifest"), Mapping)
        and plan.get("truth_read") is False
        and plan.get("case_or_family_identity_read") is False
        and plan.get("source_or_problem_modified") is False
        and plan.get("bounds_or_gauge_added") is False
        and plan.get("endpoint_unchanged_before_refinement") is True
    ):
        raise OrdinaryBindingRejected("ORIGINAL_PLAN_PROVENANCE_REJECTED")


def _verify_source_endpoint_origin(
    original: Mapping[str, Any],
    original_path: Path,
    *,
    source_bytes: bytes,
    source_sha256: str,
    endpoint: tuple[float, ...],
    endpoint_digest: str,
) -> None:
    _verify_original_result_contract(original)
    plans = []
    for path in sorted(original_path.parent.glob("reservoir-batch-*/hp/*/PLAN.json")):
        try:
            plan = json.loads(path.read_bytes())
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(plan, Mapping) and plan.get("endpoint_float64_sha256") == endpoint_digest:
            plans.append(plan)
    if len(plans) != 1:
        raise OrdinaryBindingRejected("ORIGINAL_ENDPOINT_PLAN_NOT_UNIQUE")
    for plan in plans:
        _verify_original_plan_contract(
            plan, original_source_sha256=str(original["source_sha256"])
        )
        raw_endpoint = plan.get("endpoint")
        if not isinstance(raw_endpoint, list):
            raise OrdinaryBindingRejected("ORIGINAL_ENDPOINT_PLAN_MALFORMED")
        values = tuple(float(value) for value in raw_endpoint)
        if endpoint_sha256(values) != endpoint_digest or values != endpoint:
            raise OrdinaryBindingRejected("ORIGINAL_ENDPOINT_BITS_MISMATCH")
        source_path = Path(_command_argument(plan.get("command"), "--source")).resolve()
        if source_path.parent != APPROVED_ORIGINAL_INPUT_ROOT or not source_path.is_file():
            raise OrdinaryBindingRejected("ORIGINAL_SOURCE_OUTSIDE_CUSTODY")
        original_source_bytes = source_path.read_bytes()
        if sha256_bytes(original_source_bytes) != original.get("source_sha256"):
            raise OrdinaryBindingRejected("ORIGINAL_SOURCE_SHA256_MISMATCH")
        source_document = json.loads(original_source_bytes)
        if not isinstance(source_document, Mapping):
            raise OrdinaryBindingRejected("ORIGINAL_SOURCE_NOT_MAPPING")
        projection = {key: item for key, item in source_document.items() if key != "id"}
        projected = (json.dumps(projection, indent=2, sort_keys=True) + "\n").encode()
        if projected != source_bytes or sha256_bytes(projected) != source_sha256:
            raise OrdinaryBindingRejected("ANONYMOUS_SOURCE_PROJECTION_MISMATCH")


def _validated_descriptor(value: object) -> tuple[Mapping[str, Any], Mapping[str, Any], tuple[int, ...], int]:
    boundary = _load_boundary()
    descriptor = boundary.exact_descriptor(value)
    if descriptor is None or canonical_bytes(descriptor) != canonical_bytes(value):
        raise OrdinaryBindingRejected("ORDINARY_DESCRIPTOR_BOUNDARY_REJECTED")
    coefficients = tuple(descriptor["minimal_polynomial_high_to_low"])
    degree = len(coefficients) - 1
    if (
        degree not in ALLOWED_DESCRIPTOR_DEGREES
        or any(abs(int(item)).bit_length() > MAX_COEFFICIENT_BITS for item in coefficients)
    ):
        raise OrdinaryBindingRejected("ORDINARY_DESCRIPTOR_FIXED_CAP")
    variable = sp.Symbol("ordinary_target")
    polynomial = sp.Poly.from_list(list(coefficients), gens=variable, domain=sp.ZZ)
    content, primitive = polynomial.primitive()
    if (
        int(content) != 1
        or primitive.LC() <= 0
        or primitive.is_sqf is not True
        or primitive.is_irreducible is not True
    ):
        raise OrdinaryBindingRejected("ORDINARY_POLYNOMIAL_NOT_PRIMITIVE_SQF_IRREDUCIBLE")
    isolator = descriptor["isolating_interval"]
    try:
        left = sp.Rational(str(isolator["left"]))
        right = sp.Rational(str(isolator["right"]))
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
        raise OrdinaryBindingRejected("ORDINARY_ISOLATOR_MALFORMED") from error
    if left > right or int(polynomial.count_roots(left, right)) != 1:
        raise OrdinaryBindingRejected("ORDINARY_ISOLATOR_NOT_UNIQUE")
    ordinal = int(descriptor["selected_real_root_index"])
    if isolator.get("real_root_index") != ordinal or isolator.get("multiplicity") != 1:
        raise OrdinaryBindingRejected("ORDINARY_ISOLATOR_ORDINAL_LEDGER_MISMATCH")
    roots_through_left = int(polynomial.count_roots(-sp.oo, left))
    if polynomial.eval(left) == 0:
        roots_through_left -= 1
    real_root_count = int(polynomial.count_roots(-sp.oo, sp.oo))
    if ordinal != roots_through_left or not 0 <= ordinal < real_root_count:
        raise OrdinaryBindingRejected("ORDINARY_FACTOR_LOCAL_REAL_ROOT_ORDINAL_MISMATCH")
    target_descriptor = {
        "coefficients_high_to_low": list(coefficients),
        "isolating_interval": {
            "left": str(left),
            "right": str(right),
            "multiplicity": 1,
        },
    }
    return descriptor, target_descriptor, coefficients, ordinal


def bind_row(row: Mapping[str, Any]) -> BoundOrdinaryProposal:
    if not isinstance(row, Mapping):
        raise OrdinaryBindingRejected("ORDINARY_BINDING_ROW_SCHEMA_MISMATCH")
    keys = frozenset(row)
    if keys not in {ROW_KEYS, LEGACY_ROW_KEYS}:
        raise OrdinaryBindingRejected("ORDINARY_BINDING_ROW_SCHEMA_MISMATCH")
    legacy_projection = keys == LEGACY_ROW_KEYS
    source_path = _bounded_file(APPROVED_SOURCE_ROOT, row["source_rel"])
    proposal_path = _bounded_file(APPROVED_PROPOSAL_ROOT, row["proposal_result_rel"])
    source, source_bytes = _read_json_bytes(source_path, cap=MAX_SOURCE_BYTES, label="SOURCE")
    proposal, proposal_bytes = _read_json_bytes(
        proposal_path, cap=MAX_PROPOSAL_BYTES, label="PROPOSAL"
    )
    source_digest = sha256_bytes(source_bytes)
    proposal_digest = sha256_bytes(proposal_bytes)
    if source_digest != row.get("source_sha256"):
        raise OrdinaryBindingRejected("SOURCE_SHA256_MISMATCH")
    if proposal_digest != row.get("proposal_sha256"):
        raise OrdinaryBindingRejected("PROPOSAL_ALL_BYTES_SHA256_MISMATCH")
    if set(proposal) != PROPOSAL_KEYS or proposal.get("schema_version") not in {
        PROPOSAL_SCHEMA,
        LEGACY_PROPOSAL_SCHEMA,
    }:
        raise OrdinaryBindingRejected("PROPOSAL_WRAPPER_SCHEMA_MISMATCH")
    if (
        proposal.get("source_sha256") != source_digest
        or proposal.get("truth_used") is not False
        or proposal.get("case_family_target_count_routing") is not False
    ):
        raise OrdinaryBindingRejected("PROPOSAL_SOURCE_OR_SCOPE_BINDING_MISMATCH")
    endpoint = endpoint_from_bits(row["endpoint_float64_bits_hex"])
    endpoint_digest = endpoint_sha256(endpoint)
    if (
        endpoint_digest != row.get("endpoint_float64_sha256")
        or endpoint_digest != proposal.get("endpoint_float64_sha256")
    ):
        raise OrdinaryBindingRejected("ENDPOINT_FLOAT64_BITS_SHA256_MISMATCH")
    original, original_bytes, original_path = _original_result(
        proposal.get("original_result_sha256")
    )
    _verify_source_endpoint_origin(
        original,
        original_path,
        source_bytes=source_bytes,
        source_sha256=source_digest,
        endpoint=endpoint,
        endpoint_digest=endpoint_digest,
    )
    attempt = proposal.get("ordinary_attempt")
    if not isinstance(attempt, Mapping):
        raise OrdinaryBindingRejected("ORDINARY_ATTEMPT_NOT_MAPPING")
    attempt_digest = canonical_sha256(attempt)
    if (
        proposal.get("ordinary_attempt_sha256") != attempt_digest
        or attempt.get("status") != "TARGET_AUTHORITY_READY"
        or attempt.get("authority_pass") is not True
        or attempt.get("endpoint_float64_sha256") != endpoint_digest
    ):
        raise OrdinaryBindingRejected("ORDINARY_ATTEMPT_BINDING_REJECTED")
    matches = []
    for outer in original.get("hp_attempts", []):
        if not isinstance(outer, Mapping):
            continue
        candidate = outer.get("ordinary_hp_proposal")
        if (
            isinstance(candidate, Mapping)
            and outer.get("endpoint_float64_sha256") == endpoint_digest
            and canonical_bytes(candidate) == canonical_bytes(attempt)
        ):
            matches.append(candidate)
    if len(matches) != 1:
        raise OrdinaryBindingRejected("COPIED_ORDINARY_ATTEMPT_NOT_UNIQUE_IN_ORIGINAL_BYTES")
    descriptor, target, coefficients, ordinal = _validated_descriptor(
        attempt.get("descriptor")
    )
    row_descriptor = row.get("degree1_descriptor")
    if legacy_projection:
        if len(coefficients) != 2:
            raise OrdinaryBindingRejected("LEGACY_DEGREE1_PROJECTION_ON_NONLINEAR_DESCRIPTOR")
        expected = {
            "minimal_polynomial_high_to_low": list(coefficients),
            "selected_real_root_index": ordinal,
        }
        if row_descriptor != expected:
            raise OrdinaryBindingRejected("LEGACY_DEGREE1_PROJECTION_MISMATCH")
    statement = {
        "schema_version": SCHEMA,
        "source_sha256": source_digest,
        "endpoint_float64_sha256": endpoint_digest,
        "proposal_all_bytes_sha256": proposal_digest,
        "original_result_all_bytes_sha256": sha256_bytes(original_bytes),
        "ordinary_attempt_canonical_sha256": attempt_digest,
        "ordinary_descriptor_canonical_sha256": canonical_sha256(descriptor),
        "target_descriptor_canonical_sha256": canonical_sha256(target),
        "polynomial_degree": len(coefficients) - 1,
        "selected_real_root_index": ordinal,
        "authority_pass": False,
        "target_release": False,
        "completeness_claim": "NOT_MADE",
    }
    return BoundOrdinaryProposal(
        source_path=source_path,
        source_bytes=source_bytes,
        source=source,
        source_sha256=source_digest,
        endpoint=endpoint,
        endpoint_float64_sha256=endpoint_digest,
        proposal_path=proposal_path,
        proposal_bytes=proposal_bytes,
        proposal_sha256=proposal_digest,
        original_result_sha256=sha256_bytes(original_bytes),
        ordinary_attempt_sha256=attempt_digest,
        ordinary_descriptor=descriptor,
        ordinary_descriptor_sha256=canonical_sha256(descriptor),
        target_descriptor=target,
        target_descriptor_sha256=canonical_sha256(target),
        polynomial_coefficients_high_to_low=coefficients,
        selected_real_root_index=ordinal,
        binding_statement=statement,
        binding_statement_sha256=canonical_sha256(statement),
    )


__all__ = [
    "APPROVED_ORIGINAL_RESULT_ROOT",
    "APPROVED_PANEL_ROOT",
    "APPROVED_PROPOSAL_ROOT",
    "APPROVED_SOURCE_ROOT",
    "BoundOrdinaryProposal",
    "OrdinaryBindingRejected",
    "LEGACY_ROW_KEYS",
    "ROW_KEYS",
    "bind_row",
    "canonical_bytes",
    "canonical_sha256",
]
