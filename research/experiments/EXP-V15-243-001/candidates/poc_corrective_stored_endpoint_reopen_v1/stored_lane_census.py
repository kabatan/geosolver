#!/usr/bin/env python3
"""Root-custody aggregate census for already-stored independent HP lanes.

This script never launches search, refinement, exactification, or a scorer.  It
discovers source documents and frozen refinement-bridge documents below one
development artifact root, validates them with the frozen D1 cascade, and
emits aggregate counts only.  Paths, source hashes, endpoints, coordinates,
targets, descriptors, case identifiers, and per-row rejection reasons are not
written to either stdout or the output artifact.
"""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping, Sequence


HERE = Path(__file__).resolve().parent
ADAPTER_PATH = HERE / "stored_endpoint_adapter.py"
ADAPTER_SHA256 = "352f40b354071a4f4106a4bc843d006ac860095a4ba4efa431c268936f20ae84"
CENSUS_SCHEMA = "geotarget.poc-stored-independent-lane-census/v1"
BRIDGE_SCHEMA = "geotarget.real61-refinement-bridge-case/v1"
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_JSON_FILES = 250_000
MAX_SELECTED_PAIRS = 12

FORBIDDEN_ROOT_TOKENS = frozenset({"validation", "sealed"})
FORBIDDEN_FILE_TOKENS = frozenset(
    {
        "score",
        "scorer",
        "truth",
        "gold",
        "answer_key",
        "validation",
        "sealed",
    }
)


class CensusError(ValueError):
    pass


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_candidate():
    if _sha256(ADAPTER_PATH.read_bytes()) != ADAPTER_SHA256:
        raise CensusError("stored endpoint adapter hash drift")
    name = "geotarget_poc_stored_lane_census_adapter"
    loaded = sys.modules.get(name)
    if loaded is not None:
        return loaded
    specification = importlib.util.spec_from_file_location(name, ADAPTER_PATH)
    if specification is None or specification.loader is None:
        raise CensusError("stored endpoint adapter cannot be loaded")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise CensusError("non-canonical JSON value") from error


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CensusError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise CensusError("non-finite JSON constant")


def _parse(payload: bytes) -> dict[str, Any]:
    if not payload or len(payload) > MAX_JSON_BYTES:
        raise CensusError("JSON file size outside census cap")
    try:
        value = json.loads(
            payload,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CensusError("invalid JSON") from error
    if not isinstance(value, dict):
        raise CensusError("JSON root is not an object")
    return value


def _safe_artifact_path(root: Path, path: Path) -> bool:
    relative = path.relative_to(root)
    normalized_parts = tuple(part.lower().replace("-", "_") for part in relative.parts)
    return not any(
        forbidden in part
        for part in normalized_parts
        for forbidden in FORBIDDEN_FILE_TOKENS
    )


def _json_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in root.rglob("*.json"):
        if not path.is_file() or not _safe_artifact_path(root, path):
            continue
        paths.append(path)
        if len(paths) > MAX_JSON_FILES:
            raise CensusError("JSON file count exceeds census cap")
    return sorted(paths, key=lambda item: str(item.relative_to(root)))


def _is_source(document: Mapping[str, Any]) -> bool:
    variables = document.get("variables")
    names = variables.get("names") if isinstance(variables, Mapping) else None
    return bool(
        document.get("task") == "solve"
        and isinstance(names, list)
        and all(isinstance(name, str) and name for name in names)
        and isinstance(document.get("answer"), str)
        and isinstance(document.get("construction", []), list)
        and isinstance(document.get("constraints", []), list)
        and isinstance(document.get("guards", []), list)
    )


def _numeric_text(value: object) -> bool:
    if isinstance(value, bool) or isinstance(value, (dict, list, tuple)):
        return False
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return False
    return number.is_finite()


def _lane_shape(
    proposal: Mapping[str, Any], *, dimension: int
) -> tuple[bool, str]:
    lane768 = proposal.get("coordinates_768bit_minimum")
    lane1024 = proposal.get("coordinates_1024bit_minimum")
    if proposal.get("status") != "INDEPENDENT_REFINEMENT_READY":
        return False, "not_independently_ready"
    if proposal.get("independent_precision_lanes") is not True:
        return False, "independence_attestation_absent"
    if proposal.get("numeric_gate_1e_100") is not True:
        return False, "numeric_gate_absent"
    if not isinstance(lane768, list) or not isinstance(lane1024, list):
        return False, "coordinate_lane_absent"
    if not lane768 or len(lane768) != len(lane1024) or len(lane768) != dimension:
        return False, "coordinate_lane_dimension"
    if not all(_numeric_text(value) for value in (*lane768, *lane1024)):
        return False, "coordinate_lane_nonfinite"
    for field in (
        "answer_512bit_minimum",
        "answer_768bit_minimum",
        "answer_1024bit_minimum",
    ):
        if not _numeric_text(proposal.get(field)):
            return False, "answer_lane_absent"
    source = proposal.get("source")
    endpoint_sha = source.get("endpoint_float64_sha256") if isinstance(source, Mapping) else None
    if not (
        isinstance(endpoint_sha, str)
        and len(endpoint_sha) == 64
        and all(character in "0123456789abcdef" for character in endpoint_sha)
    ):
        return False, "endpoint_binding_absent"
    return True, "complete"


def _non_turn_ready(
    *,
    d1: Any,
    cascade: Any,
    proposal: Mapping[str, Any],
    owned: Mapping[str, Any],
    names: Sequence[str],
    atom: Any,
) -> bool:
    if atom.coordinate_index >= len(names):
        return False
    try:
        adapted, _descriptor, _witnesses = cascade._adapt_proposal(
            proposal, owned, names
        )
        descriptors = adapted["configuration_algebraic_proposals"]
        lane768 = proposal["coordinates_768bit_minimum"]
        lane1024 = proposal["coordinates_1024bit_minimum"]
        if d1._decimal_difference(
            lane768[atom.coordinate_index], lane1024[atom.coordinate_index]
        ) > d1.TURN_ADJACENT_PRECISION_GATE:
            return False
    except Exception:
        return False
    if not isinstance(descriptors, list) or len(descriptors) != len(names):
        return False
    return all(
        index == atom.coordinate_index
        or (
            isinstance(descriptor, Mapping)
            and descriptor.get("status")
            in {"ALGEBRAIC_PROPOSAL", "PI_MULTIPLE_PROPOSAL"}
        )
        for index, descriptor in enumerate(descriptors)
    )


def census_root(root: Path, *, candidate_module: Any | None = None) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise CensusError("artifact root is not a directory")
    normalized_root_parts = tuple(part.lower().replace("-", "_") for part in root.parts)
    if any(
        forbidden in part
        for part in normalized_root_parts
        for forbidden in FORBIDDEN_ROOT_TOKENS
    ):
        raise CensusError("validation/sealed roots are forbidden")

    candidate = _load_candidate() if candidate_module is None else candidate_module
    d1 = candidate._load_d1()
    cascade = d1._load_cascade()
    paths = _json_paths(root)
    sources: dict[str, bytes] = {}
    bridges: dict[str, tuple[bytes, dict[str, Any]]] = {}
    file_counts: Counter[str] = Counter()
    for path in paths:
        try:
            payload = path.read_bytes()
            document = _parse(payload)
        except (OSError, CensusError):
            file_counts["json_rejected"] += 1
            continue
        file_counts["json_parsed"] += 1
        if _is_source(document):
            sources.setdefault(_sha256(payload), payload)
            file_counts["source_document"] += 1
        if document.get("schema_version") == BRIDGE_SCHEMA:
            bridges.setdefault(_sha256(payload), (payload, document))
            file_counts["bridge_document"] += 1

    counts: Counter[str] = Counter()
    shape_failures: Counter[str] = Counter()
    selected: list[tuple[str, bytes, dict[str, Any], bytes, Any]] = []
    signatures: set[str] = set()
    for bridge_sha, (bridge_payload, bridge) in bridges.items():
        source_sha = bridge.get("case_sha256")
        source_bytes = sources.get(source_sha) if isinstance(source_sha, str) else None
        if source_bytes is None:
            counts["bridge_source_unresolved"] += 1
            continue
        try:
            refinement, owned_payload, bound_sha, _case_id = cascade._validate_bridge(
                bridge, source_bytes
            )
            if bound_sha != source_sha:
                raise CensusError("bridge source binding mismatch")
            eligibility = d1.classify_source(source_bytes)
            proposals = cascade._sequence(refinement.get("proposals"), "proposals")
            owned_by_index = cascade._owned_by_index(owned_payload)
            source_document = _parse(source_bytes)
            names = source_document["variables"]["names"]
            if set(owned_by_index) != set(range(len(proposals))):
                raise CensusError("owned proposal coverage mismatch")
        except Exception:
            counts["bridge_contract_rejected"] += 1
            continue
        counts["bridge_contract_valid"] += 1
        if not eligibility.eligible:
            counts["bridge_source_ineligible"] += 1
            continue
        counts["bridge_source_eligible"] += 1
        semantic_signature = _sha256(
            _canonical_bytes(
                {
                    "semantic_projection_sha256": eligibility.semantic_projection_sha256,
                    "atom_count": len(eligibility.atoms),
                    "dimension": len(names),
                }
            )
        )
        for proposal_index, raw in enumerate(proposals):
            counts["stored_proposal"] += 1
            if not isinstance(raw, Mapping):
                shape_failures["proposal_not_object"] += 1
                continue
            complete, reason = _lane_shape(raw, dimension=len(names))
            if not complete:
                shape_failures[reason] += 1
                continue
            counts["stored_lane_complete"] += 1
            signatures.add(semantic_signature)
            selection_sha = _sha256(
                _canonical_bytes(
                    {
                        "bridge_sha256": bridge_sha,
                        "proposal_index": proposal_index,
                        "semantic_signature": semantic_signature,
                    }
                )
            )
            selected.append(
                (
                    selection_sha,
                    source_bytes,
                    dict(raw),
                    bridge_payload,
                    (eligibility, owned_by_index[proposal_index], tuple(names)),
                )
            )

    selected.sort(key=lambda row: row[0])
    selected = selected[:MAX_SELECTED_PAIRS]
    applicable_signatures: set[str] = set()
    for _rank, _source, proposal, _bridge, packed in selected:
        eligibility, owned, names = packed
        pair_ready = False
        for atom in eligibility.atoms:
            counts["atom_applicability_attempt"] += 1
            if _non_turn_ready(
                d1=d1,
                cascade=cascade,
                proposal=proposal,
                owned=owned,
                names=names,
                atom=atom,
            ):
                counts["atom_non_turn_ready"] += 1
                pair_ready = True
        if pair_ready:
            counts["selected_pair_non_turn_ready"] += 1
            applicable_signatures.add(eligibility.semantic_projection_sha256)

    if counts["stored_lane_complete"] == 0:
        status = "STOP_NO_COMPLETE_STORED_LANES"
    elif counts["selected_pair_non_turn_ready"] == 0:
        status = "STOP_NO_NON_TURN_READY_STORED_LANES"
    else:
        status = "GO_PRIVATE_HOLD_GATE_NOT_EXECUTED"
    required_counts = (
        "bridge_source_unresolved",
        "bridge_contract_rejected",
        "bridge_contract_valid",
        "bridge_source_ineligible",
        "bridge_source_eligible",
        "stored_proposal",
        "stored_lane_complete",
        "atom_applicability_attempt",
        "atom_non_turn_ready",
        "selected_pair_non_turn_ready",
    )
    aggregate_counts = {key: counts.get(key, 0) for key in required_counts}
    aggregate = {
        "schema_version": CENSUS_SCHEMA,
        "status": status,
        "truth_used": False,
        "scorer_used": False,
        "validation_or_sealed_opened": False,
        "per_row_output_emitted": False,
        "case_family_target_descriptor_endpoint_emitted": False,
        "search_or_refinement_executed": False,
        "corrective_exactification_executed": False,
        "complete_zero_stops_without_tuning": True,
        "json_file_count": len(paths),
        "file_counts": dict(sorted(file_counts.items())),
        "counts": dict(sorted(aggregate_counts.items())),
        "lane_shape_failure_counts": dict(sorted(shape_failures.items())),
        "complete_anonymous_signature_count": len(signatures),
        "selected_pair_cap": MAX_SELECTED_PAIRS,
        "selected_pair_count": len(selected),
        "applicable_anonymous_signature_count": len(applicable_signatures),
        "frozen_d1_adapter_sha256": candidate.D1_SHA256,
    }
    aggregate["aggregate_sha256"] = _sha256(_canonical_bytes(aggregate))
    return aggregate


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    aggregate = census_root(arguments.artifact_root)
    _atomic_json(arguments.output.resolve(), aggregate)
    print(json.dumps(aggregate, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
