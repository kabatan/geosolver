"""Fail-closed binding from an ordinary HP proposal to exact NRA replay.

The connector proves one *emission*, never target-set completeness.  A frozen
ordinary proposal result is bound to the untouched source bytes, the exact
Float64 endpoint bits, and a primitive degree-one descriptor.  The existing
NRA witness and exact DSL replay are then rerun.  The descriptor is accepted
only through the existing digest-pinned ``authority_boundary`` parser.

Until an independent connector audit passes, every public terminal remains a
HOLD with ``authority_pass == target_release == False``.
"""

from __future__ import annotations

from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
from typing import Mapping, Sequence

import applicability
import candidate as backend
from run_degree1_proposal_census import (
    FORBIDDEN_SOURCE_KEYS,
    STRATA,
    _replay_existing_witness,
)


SCHEMA = "geotarget.target-constrained-nra-ordinary-binding/v1"
PROPOSAL_SCHEMA = "geotarget.frozen-ordinary-degree1-proposal/v1"
APPROVED_SOURCE_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-inputs"
).resolve()
APPROVED_PANEL_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results/target-constrained-nra-ordinary-binding-v1"
).resolve()
APPROVED_PROPOSAL_ROOT = (APPROVED_PANEL_ROOT / "ordinary-proposals").resolve()
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
        "degree1_descriptor",
        "proposal_result_rel",
        "proposal_sha256",
    }
)
FORBIDDEN_ROW_KEYS = frozenset(
    {
        "id",
        "case_id",
        "problem_id",
        "slug",
        "family",
        "truth",
        "answer",
        "target",
        "outcome",
        "result",
        "score",
        "known_count",
    }
)
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


class BindingRejected(ValueError):
    """The complete binding or exact replay did not prove an emission."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64 or value.lower() != value:
        return False
    try:
        bytes.fromhex(value)
    except ValueError:
        return False
    return True


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return _sha256(canonical_bytes(value))


def _load_boundary():
    if (
        not AUTHORITY_BOUNDARY_PATH.is_file()
        or _sha256(AUTHORITY_BOUNDARY_PATH.read_bytes()) != AUTHORITY_BOUNDARY_SHA256
    ):
        raise RuntimeError("frozen authority_boundary changed")
    name = "geotarget_nra_ordinary_binding_authority_boundary"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(
        name, AUTHORITY_BOUNDARY_PATH
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("frozen authority_boundary cannot be loaded")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


BOUNDARY = _load_boundary()


def require_approved_roots(source_root: Path, proposal_root: Path) -> tuple[Path, Path]:
    source = source_root.resolve()
    proposal = proposal_root.resolve()
    if source != APPROVED_SOURCE_ROOT or proposal != APPROVED_PROPOSAL_ROOT:
        raise BindingRejected("UNAPPROVED_INPUT_CUSTODY_ROOT")
    if not source.is_dir() or not proposal.is_dir():
        raise BindingRejected("APPROVED_INPUT_CUSTODY_ROOT_MISSING")
    return source, proposal


def bounded_relative_file(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise BindingRejected("RELATIVE_ARTIFACT_PATH_MALFORMED")
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise BindingRejected("ARTIFACT_PATH_ESCAPED_APPROVED_ROOT") from error
    if path.suffix != ".json" or not path.is_file():
        raise BindingRejected("ARTIFACT_PATH_NOT_JSON_FILE")
    return path


def endpoint_from_bits(value: object) -> tuple[float, ...]:
    if not isinstance(value, list) or not value:
        raise BindingRejected("ENDPOINT_BITS_MALFORMED")
    endpoint = []
    for item in value:
        if not isinstance(item, str) or len(item) != 16 or item.lower() != item:
            raise BindingRejected("ENDPOINT_BITS_MALFORMED")
        try:
            raw = bytes.fromhex(item)
        except ValueError as error:
            raise BindingRejected("ENDPOINT_BITS_MALFORMED") from error
        number = struct.unpack(">d", raw)[0]
        if not math.isfinite(number):
            raise BindingRejected("ENDPOINT_BITS_NONFINITE")
        endpoint.append(number)
    return tuple(endpoint)


def endpoint_float64_sha256(endpoint: Sequence[float]) -> str:
    values = tuple(float(value) for value in endpoint)
    if not values or any(not math.isfinite(value) for value in values):
        raise BindingRejected("ENDPOINT_NONFINITE_OR_EMPTY")
    payload = struct.pack(">I", len(values)) + b"".join(
        struct.pack(">d", value) for value in values
    )
    return _sha256(payload)


def endpoint_bits_hex(endpoint: Sequence[float]) -> list[str]:
    values = tuple(float(value) for value in endpoint)
    if not values or any(not math.isfinite(value) for value in values):
        raise BindingRejected("ENDPOINT_NONFINITE_OR_EMPTY")
    return [struct.pack(">d", value).hex() for value in values]


def descriptor_identity(value: object) -> tuple[tuple[int, int], int]:
    if not isinstance(value, Mapping) or set(value) != {
        "minimal_polynomial_high_to_low",
        "selected_real_root_index",
    }:
        raise BindingRejected("DEGREE1_DESCRIPTOR_MALFORMED")
    coefficients = value.get("minimal_polynomial_high_to_low")
    ordinal = value.get("selected_real_root_index")
    if (
        not isinstance(coefficients, list)
        or len(coefficients) != 2
        or any(
            not isinstance(item, int) or isinstance(item, bool) for item in coefficients
        )
        or not isinstance(ordinal, int)
        or isinstance(ordinal, bool)
        or ordinal != 0
    ):
        raise BindingRejected("DEGREE1_DESCRIPTOR_MALFORMED")
    leading, constant = coefficients
    if leading <= 0 or math.gcd(abs(leading), abs(constant)) != 1:
        raise BindingRejected("DEGREE1_DESCRIPTOR_NOT_PRIMITIVE_POSITIVE")
    return (leading, constant), ordinal


def _ordinary_descriptor(
    proposal_artifact: Mapping[str, object],
    *,
    source_sha256: str,
    endpoint_sha256: str,
    expected_identity: tuple[tuple[int, int], int],
) -> tuple[Mapping[str, object], Mapping[str, object]]:
    if set(proposal_artifact) != PROPOSAL_KEYS:
        raise BindingRejected("PROPOSAL_ARTIFACT_SCHEMA_KEYS_MISMATCH")
    if (
        proposal_artifact.get("schema_version") != PROPOSAL_SCHEMA
        or proposal_artifact.get("source_sha256") != source_sha256
        or proposal_artifact.get("endpoint_float64_sha256") != endpoint_sha256
        or not is_sha256(proposal_artifact.get("original_result_sha256"))
        or proposal_artifact.get("truth_used") is not False
        or proposal_artifact.get("case_family_target_count_routing") is not False
    ):
        raise BindingRejected("PROPOSAL_ARTIFACT_BINDING_MISMATCH")
    attempt = proposal_artifact.get("ordinary_attempt")
    if not isinstance(attempt, Mapping):
        raise BindingRejected("ORDINARY_ATTEMPT_MALFORMED")
    if proposal_artifact.get("ordinary_attempt_sha256") != canonical_sha256(attempt):
        raise BindingRejected("ORDINARY_ATTEMPT_DIGEST_MISMATCH")
    if (
        attempt.get("status") != "TARGET_AUTHORITY_READY"
        or attempt.get("authority_pass") is not True
        or attempt.get("endpoint_float64_sha256") != endpoint_sha256
    ):
        raise BindingRejected("ORDINARY_ATTEMPT_NOT_READY_OR_ENDPOINT_MISMATCH")
    descriptor = BOUNDARY.exact_descriptor(attempt.get("descriptor"))
    identity = BOUNDARY.descriptor_identity(attempt.get("descriptor"))
    if descriptor is None or identity != expected_identity:
        raise BindingRejected("ORDINARY_DESCRIPTOR_EXACT_IDENTITY_MISMATCH")
    # The value handed back to the authority boundary is byte-for-byte the
    # ordinary descriptor mapping after canonical serialization; it is never
    # synthesized from the NRA witness.
    if canonical_sha256(descriptor) != canonical_sha256(attempt.get("descriptor")):
        raise BindingRejected("ORDINARY_DESCRIPTOR_NORMALIZATION_CHANGED")
    return attempt, descriptor


def _target_proposal(
    identity: tuple[tuple[int, int], int], descriptor: Mapping[str, object]
) -> backend.TargetProposal:
    coefficients, ordinal = identity
    isolator = descriptor.get("isolating_interval")
    if not isinstance(isolator, Mapping):
        raise BindingRejected("ORDINARY_ISOLATOR_MISSING")
    try:
        lower = Fraction(str(isolator.get("left")))
        upper = Fraction(str(isolator.get("right")))
    except (ValueError, ZeroDivisionError) as error:
        raise BindingRejected("ORDINARY_ISOLATOR_MALFORMED") from error
    if lower >= upper:
        raise BindingRejected("ORDINARY_ISOLATOR_MALFORMED")
    return backend.TargetProposal(coefficients, ordinal, lower, upper)


def _failure_class(error: Exception) -> str:
    text = str(error)
    if "CUSTODY" in text or "PATH" in text or "SHA" in text or "DIGEST" in text:
        return "CUSTODY_OR_DIGEST_REJECTED"
    if "ENDPOINT" in text:
        return "ENDPOINT_BINDING_REJECTED"
    if "DESCRIPTOR" in text or "PROPOSAL" in text or "ATTEMPT" in text:
        return "ORDINARY_DESCRIPTOR_BINDING_REJECTED"
    if "LEGACY_PRIMITIVE_COVER" in text or "LEGACY_TARGET_GRAPH" in text:
        return "EXISTING_COMPILER_SUBSET_REJECTED"
    if "TIMEOUT" in text or "RESOURCE" in text:
        return "BACKEND_RESOURCE_OR_TIMEOUT"
    if "UNSAT" in text or "NO_WITNESS" in text:
        return "BACKEND_UNSAT_OR_NO_WITNESS"
    if "REPLAY" in text or "TARGET_LINK" in text:
        return "UNTOUCHED_REPLAY_REJECTED"
    return "OTHER_FAIL_CLOSED"


def connect(
    row: Mapping[str, object],
    *,
    source_root: Path,
    proposal_root: Path,
    timeout_seconds: float,
) -> dict[str, object]:
    """Build one private audit artifact.  No terminal releases a target."""

    common: dict[str, object] = {
        "schema_version": SCHEMA,
        "status": "HOLD_CONNECTOR_NOT_AUDITED",
        "authority_pass": False,
        "target_release": False,
        "target_set_completeness_claim": False,
        "canonical_source_replay_bypassed": False,
        "truth_used": False,
        "case_family_target_count_routing": False,
        "binding_ready": False,
        "ordinary_binding_pass": False,
        "exact_replay_pass": False,
        "readiness": False,
        "authority_boundary_descriptor_ready": False,
    }
    try:
        if not isinstance(row, Mapping) or set(row) != ROW_KEYS:
            raise BindingRejected("REQUEST_SCHEMA_KEYS_MISMATCH")
        if FORBIDDEN_ROW_KEYS & set(row):
            raise BindingRejected("REQUEST_CROSSED_IDENTITY_TRUTH_BOUNDARY")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise BindingRejected("BACKEND_TIMEOUT_MALFORMED")
        source_root, proposal_root = require_approved_roots(source_root, proposal_root)
        source_path = bounded_relative_file(source_root, row["source_rel"])
        proposal_path = bounded_relative_file(proposal_root, row["proposal_result_rel"])
        source_payload = source_path.read_bytes()
        proposal_payload = proposal_path.read_bytes()
        source_sha256 = _sha256(source_payload)
        proposal_sha256 = _sha256(proposal_payload)
        if source_sha256 != row.get("source_sha256"):
            raise BindingRejected("SOURCE_SHA256_MISMATCH")
        if proposal_sha256 != row.get("proposal_sha256"):
            raise BindingRejected("PROPOSAL_SHA256_MISMATCH")
        try:
            document = json.loads(source_payload)
            proposal_artifact = json.loads(proposal_payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise BindingRejected("SOURCE_OR_PROPOSAL_NOT_JSON") from error
        if not isinstance(document, Mapping) or not isinstance(
            proposal_artifact, Mapping
        ):
            raise BindingRejected("SOURCE_OR_PROPOSAL_NOT_MAPPING")
        if FORBIDDEN_SOURCE_KEYS & set(document):
            raise BindingRejected("SOURCE_DOCUMENT_CROSSED_IDENTITY_TRUTH_BOUNDARY")
        if document.get("post_process") not in (None, ""):
            raise BindingRejected("POST_PROCESS_OUTSIDE_RAW_TARGET_THEOREM")

        endpoint = endpoint_from_bits(row["endpoint_float64_bits_hex"])
        endpoint_sha256 = endpoint_float64_sha256(endpoint)
        if endpoint_sha256 != row.get("endpoint_float64_sha256"):
            raise BindingRejected("ENDPOINT_FLOAT64_SHA256_MISMATCH")
        variables = document.get("variables")
        variable_names = (
            variables.get("names") if isinstance(variables, Mapping) else None
        )
        if (
            not isinstance(variable_names, list)
            or len(endpoint) != len(variable_names)
            or not all(isinstance(name, str) and name for name in variable_names)
        ):
            raise BindingRejected("ENDPOINT_SOURCE_DIMENSION_MISMATCH")
        identity = descriptor_identity(row["degree1_descriptor"])
        _ordinary_attempt, ordinary_descriptor = _ordinary_descriptor(
            proposal_artifact,
            source_sha256=source_sha256,
            endpoint_sha256=endpoint_sha256,
            expected_identity=identity,
        )
        proposal = _target_proposal(identity, ordinary_descriptor)

        source, metadata = applicability._legacy_target_link_source(
            document, include_private_bridge_ledger=True
        )
        stratum = str(metadata.get("structural_stratum"))
        if stratum not in STRATA:
            raise BindingRejected("LEGACY_PRIMITIVE_COVER_UNKNOWN_STRATUM")
        witness = backend.prove(source, proposal, timeout_seconds=timeout_seconds)
        if witness.get("authority_pass") is not True:
            raise BindingRejected(str(witness.get("reason", "BACKEND_NO_WITNESS")))
        replay = _replay_existing_witness(
            document,
            source,
            witness,
            metadata.get("private_bridge_ledger"),
        )
        if not (
            replay.get("untouched_source_replay_pass") is True
            and replay.get("untouched_target_link_pass") is True
        ):
            raise BindingRejected("UNTOUCHED_REPLAY_DID_NOT_PASS")

        descriptor_sha256 = canonical_sha256(ordinary_descriptor)
        statement = {
            "source_sha256": source_sha256,
            "endpoint_float64_sha256": endpoint_sha256,
            "degree1_descriptor": {
                "minimal_polynomial_high_to_low": list(identity[0]),
                "selected_real_root_index": identity[1],
            },
            "ordinary_descriptor_sha256": descriptor_sha256,
            "proposal_artifact_sha256": proposal_sha256,
            "original_result_sha256": proposal_artifact["original_result_sha256"],
            "ordinary_attempt_sha256": proposal_artifact["ordinary_attempt_sha256"],
            "nra_witness_sha256": witness.get("witness_sha256"),
            "source_replay_bridge_sha256": metadata["private_bridge_ledger"].get(
                "bridge_ledger_sha256"
            ),
        }
        common.update(
            {
                "status": "AUTHORITY_BOUNDARY_DESCRIPTOR_READY_PENDING_AUDIT",
                "binding_ready": True,
                "ordinary_binding_pass": True,
                "exact_replay_pass": True,
                "readiness": True,
                "authority_boundary_descriptor_ready": True,
                "authority_boundary_sha256": AUTHORITY_BOUNDARY_SHA256,
                "authority_boundary_exact_descriptor": ordinary_descriptor,
                "ordinary_descriptor_sha256": descriptor_sha256,
                "ordinary_and_nra_exact_identity_match": True,
                "ordinary_descriptor_returned_without_rewrite": True,
                "untouched_source_replay_pass": True,
                "untouched_target_link_pass": True,
                "stratum": stratum,
                "binding_statement": statement,
                "binding_signature_sha256": canonical_sha256(statement),
                "failure_class": "NONE",
            }
        )
        return common
    except Exception as error:
        common["failure_class"] = _failure_class(error)
        return common


__all__ = [
    "APPROVED_PANEL_ROOT",
    "APPROVED_PROPOSAL_ROOT",
    "APPROVED_SOURCE_ROOT",
    "BindingRejected",
    "PROPOSAL_SCHEMA",
    "ROW_KEYS",
    "SCHEMA",
    "bounded_relative_file",
    "canonical_bytes",
    "canonical_sha256",
    "connect",
    "descriptor_identity",
    "endpoint_bits_hex",
    "endpoint_float64_sha256",
    "is_sha256",
]
