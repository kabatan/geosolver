"""Truth-blind ingestion and seed deduplication for refinement finalists."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Any, Iterable


class BridgeInputError(ValueError):
    """A finalist artifact violated the fail-closed bridge contract."""


def canonical_sha256(document: object) -> str:
    try:
        payload = json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise BridgeInputError("artifact contains non-canonical JSON data") from error
    return hashlib.sha256(payload).hexdigest()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _endpoint_digest(endpoint: list[float]) -> str:
    """Bind dimension and exact IEEE-754 binary64 bits, including signed zero."""

    payload = struct.pack(">I", len(endpoint)) + b"".join(
        struct.pack(">d", float(value)) for value in endpoint
    )
    return hashlib.sha256(payload).hexdigest()


def _policy_binding(document: dict[str, Any]) -> dict[str, object]:
    candidate = document.get("candidate")
    if not isinstance(candidate, str) or not candidate:
        raise BridgeInputError("trial artifact lacks a candidate policy identifier")
    activation = document.get("activation")
    configuration = document.get("configuration")
    policy_document = {
        "candidate": candidate,
        "configuration": configuration,
        "activation": activation,
    }
    return {
        "candidate": candidate,
        # Bind large policy documents by digest instead of copying them once
        # per endpoint.  The artifact digest and path inventory retain the
        # source bytes needed to resolve either digest later.
        "configuration_sha256": canonical_sha256(configuration),
        "activation_sha256": canonical_sha256(activation),
        "policy_sha256": canonical_sha256(policy_document),
    }


def _parse_trial(
    path: Path,
    *,
    expected_case_id: str,
    expected_case_sha256: str,
    expected_dimension: int | None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    payload = path.read_bytes()
    artifact_sha256 = _sha256(payload)
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BridgeInputError(f"invalid UTF-8 JSON trial artifact: {path}") from error
    if not isinstance(document, dict):
        raise BridgeInputError(f"trial artifact root is not an object: {path}")
    if document.get("truth_status") != "NOT_MATERIALIZED":
        raise BridgeInputError(f"trial artifact materializes truth: {path}")
    if document.get("accuracy_claims_permitted") is not False:
        raise BridgeInputError(f"trial artifact grants accuracy authority: {path}")
    if document.get("completeness_claims_permitted") not in (None, False):
        raise BridgeInputError(f"trial artifact grants completeness authority: {path}")
    if document.get("case_id") != expected_case_id:
        raise BridgeInputError(f"trial/source case identifier mismatch: {path}")
    if document.get("case_sha256") != expected_case_sha256:
        raise BridgeInputError(f"trial/source digest mismatch: {path}")
    seed = document.get("seed")
    if (
        not isinstance(seed, int)
        or isinstance(seed, bool)
        or not 0 <= seed <= 0xFFFFFFFF
    ):
        raise BridgeInputError(f"trial artifact has no unsigned 32-bit seed: {path}")
    policy = _policy_binding(document)
    validations = document.get("validations")
    if not isinstance(validations, list):
        raise BridgeInputError(f"trial validations are not a list: {path}")

    artifact = {
        "path": str(path),
        "artifact_sha256": artifact_sha256,
        "schema_version": document.get("schema_version"),
        "case_id": expected_case_id,
        "case_sha256": expected_case_sha256,
        "seed": seed,
        "policy": policy,
        "validation_count": len(validations),
    }
    observations: list[dict[str, object]] = []
    for validation_index, validation in enumerate(validations):
        if not isinstance(validation, dict) or validation.get("safe") is not True:
            continue
        if (
            validation.get("guard_ok") is False
            or validation.get("hard_feasible") is False
        ):
            continue
        raw_endpoint = validation.get("endpoint")
        if not isinstance(raw_endpoint, list):
            continue
        try:
            endpoint = [float(value) for value in raw_endpoint]
        except (TypeError, ValueError, OverflowError):
            continue
        if (
            expected_dimension is not None and len(endpoint) != expected_dimension
        ) or not all(math.isfinite(value) for value in endpoint):
            continue
        residual = validation.get("residual_inf")
        if not isinstance(residual, (int, float)) or isinstance(residual, bool):
            continue
        residual_inf = float(residual)
        if not math.isfinite(residual_inf) or residual_inf < 0.0:
            continue
        binding = {
            "case_id": expected_case_id,
            "case_sha256": expected_case_sha256,
            "trial_artifact_sha256": artifact_sha256,
            "trial_schema_version": document.get("schema_version"),
            "candidate": policy["candidate"],
            "configuration_sha256": policy["configuration_sha256"],
            "activation_sha256": policy["activation_sha256"],
            "policy_sha256": policy["policy_sha256"],
            "seed": seed,
            "validation_index": validation_index,
        }
        binding["binding_sha256"] = canonical_sha256(binding)
        observations.append(
            {
                "endpoint": endpoint,
                "endpoint_float64_sha256": _endpoint_digest(endpoint),
                "residual_inf": residual_inf,
                "binding": binding,
            }
        )
    artifact["eligible_safe_validation_count"] = len(observations)
    return artifact, observations


def collect_seed_records(
    trial_paths: Iterable[Path],
    *,
    expected_case_id: str,
    expected_case_sha256: str,
    expected_dimension: int | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Collect deterministic, target-free numerical seed representatives."""

    paths = [Path(path) for path in trial_paths]
    if not paths:
        raise BridgeInputError("at least one finalist trial artifact is required")
    parsed: list[tuple[dict[str, object], list[dict[str, object]]]] = []
    for path in paths:
        parsed.append(
            _parse_trial(
                path,
                expected_case_id=expected_case_id,
                expected_case_sha256=expected_case_sha256,
                expected_dimension=expected_dimension,
            )
        )

    # Repeated references or byte-for-byte copies of one artifact must not
    # duplicate numerical work or provenance bindings.  Keep all path aliases
    # while processing each content digest exactly once.
    parsed.sort(
        key=lambda item: (
            str(item[0]["artifact_sha256"]),
            str(item[0]["path"]),
        )
    )
    artifacts_by_digest: dict[str, dict[str, object]] = {}
    observations: list[dict[str, object]] = []
    for artifact, members in parsed:
        digest = str(artifact["artifact_sha256"])
        existing = artifacts_by_digest.get(digest)
        if existing is None:
            stored = dict(artifact)
            stored["paths"] = [str(stored.pop("path"))]
            artifacts_by_digest[digest] = stored
            observations.extend(members)
        else:
            existing["paths"].append(str(artifact["path"]))
    artifacts = list(artifacts_by_digest.values())
    for artifact in artifacts:
        artifact["paths"] = sorted(set(artifact["paths"]))

    observations.sort(
        key=lambda item: (
            float(item["residual_inf"]),
            str(item["endpoint_float64_sha256"]),
            str(item["binding"]["binding_sha256"]),
        )
    )
    representatives: list[dict[str, object]] = []
    representatives_by_endpoint: dict[str, dict[str, object]] = {}
    for observation in observations:
        endpoint_digest = str(observation["endpoint_float64_sha256"])
        match = representatives_by_endpoint.get(endpoint_digest)
        if match is None:
            record = {
                "seed_index": len(representatives),
                "endpoint": list(observation["endpoint"]),
                "endpoint_float64_sha256": endpoint_digest,
                "representative_residual_inf": observation["residual_inf"],
                "source_bindings": [observation["binding"]],
            }
            representatives.append(record)
            representatives_by_endpoint[endpoint_digest] = record
        else:
            match["source_bindings"].append(observation["binding"])

    for record in representatives:
        record["source_bindings"].sort(key=lambda item: str(item["binding_sha256"]))
        record["source_binding_count"] = len(record["source_bindings"])
        record["source_binding_set_sha256"] = canonical_sha256(
            record["source_bindings"]
        )
    representatives.sort(key=lambda item: str(item["endpoint_float64_sha256"]))
    for index, record in enumerate(representatives):
        record["seed_index"] = index

    artifacts.sort(key=lambda item: str(item["artifact_sha256"]))
    unique_policies = sorted(
        {str(artifact["policy"]["policy_sha256"]) for artifact in artifacts}
    )
    unique_seeds = sorted({int(artifact["seed"]) for artifact in artifacts})
    summary = {
        "input_trial_artifacts": artifacts,
        "input_trial_reference_count": len(paths),
        "input_trial_artifact_count": len(artifacts),
        "duplicate_trial_reference_count": len(paths) - len(artifacts),
        "eligible_safe_validation_count": len(observations),
        "unique_seed_count": len(representatives),
        "deduplicated_validation_count": len(observations) - len(representatives),
        "deduplication_policy": {
            "kind": "exact_float64_bit_identity_same_source_semantics",
            "representative_order": "lowest_residual_then_endpoint_digest_then_binding_digest",
            "signed_zero_normalized": False,
            "diagnostic_target_used": False,
            "truth_used": False,
        },
        "bound_policy_sha256": unique_policies,
        "bound_seeds": unique_seeds,
        "binding_inventory_sha256": canonical_sha256(
            [record["source_bindings"] for record in representatives]
        ),
    }
    return representatives, summary


__all__ = [
    "BridgeInputError",
    "canonical_sha256",
    "collect_seed_records",
]
