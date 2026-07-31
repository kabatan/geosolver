#!/usr/bin/env python3
"""Thin V15 stored-endpoint seam for the audited PointOnCircle capability.

The mathematical/runtime mechanism is not copied here.  This adapter pins and
calls the already corrected and independently approved D1 adapter.  It merely
proves that a root-owned exact-outer rejection and a fresh refinement bridge
refer to the same source endpoint before allowing one terminal proposal.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Callable, Mapping


SCHEMA_VERSION = "geotarget.poc-corrective-stored-endpoint-reopen/v1"
RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver").resolve()
D1_PATH = (
    RUNTIME_ROOT
    / "research/experiments/EXP-REAL61-004/point_on_circle_finalist_fallback_d1/adapter.py"
)
D1_SHA256 = "afac6d4881a7be81a7605faa12cf9eb5083d799f80e4ce1598e2bb2d658361c5"
MAX_SOURCE_BYTES = 4 * 1024 * 1024
MAX_BRIDGE_BYTES = 8 * 1024 * 1024
MAX_PROPOSALS = 32
MAX_ATOMS = 4
MAX_EXACT_OUTER_SECONDS = 12.0

FORBIDDEN_KEYS = frozenset(
    {
        "truth",
        "known_truth",
        "known_target",
        "expected_target",
        "expected_target_count",
        "gold",
        "score",
        "scorer_output",
        "historical_result",
    }
)


class StoredEndpointRejected(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Applicability:
    source_sha256: str
    endpoint_float64_sha256: str
    proposal_index: int
    atom_ordinal: int
    atom_binding_sha256: str
    bridge_sha256: str
    current_exact_outer_exhausted: bool
    independent_coordinate_lanes: bool
    canonical_terminal_replay_required: bool = True
    authority_pass: bool = False
    target_release: bool = False
    completeness_claimed: bool = False


@dataclass(frozen=True, slots=True)
class CandidateHold:
    """Private experimental hold, never a public solver result."""

    untouched_baseline: Any
    exact_v2_record: Mapping[str, Any]
    applicability: Applicability
    status: str = "VERIFIED_PRIVATE_HOLD"
    authority_pass: bool = False
    target_release: bool = False
    completeness_claimed: bool = False


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _forbidden_paths(value: Any, path: tuple[str, ...] = ()) -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key).strip().lower().replace("-", "_")
            child = (*path, str(raw_key))
            if key in FORBIDDEN_KEYS:
                found.append(".".join(child))
            found.extend(_forbidden_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_forbidden_paths(item, (*path, str(index))))
    return tuple(found)


def _load_d1():
    if not D1_PATH.is_file() or _sha256(D1_PATH.read_bytes()) != D1_SHA256:
        raise StoredEndpointRejected("FROZEN_D1_ADAPTER_HASH_MISMATCH")
    name = "geotarget_v15_poc_corrective_stored_endpoint_d1"
    loaded = sys.modules.get(name)
    if loaded is not None:
        return loaded
    specification = importlib.util.spec_from_file_location(name, D1_PATH)
    if specification is None or specification.loader is None:
        raise StoredEndpointRejected("FROZEN_D1_ADAPTER_LOAD_FAILED")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    module.verify_frozen_components()
    return module


def _object(payload: bytes, *, label: str, maximum: int) -> dict[str, Any]:
    if not isinstance(payload, bytes) or not payload or len(payload) > maximum:
        raise StoredEndpointRejected(f"{label}_SIZE_CAP")
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise StoredEndpointRejected(f"{label}_NOT_JSON") from error
    if not isinstance(value, dict):
        raise StoredEndpointRejected(f"{label}_NOT_OBJECT")
    return value


def _validate_exact_outer_rejection(
    terminal: Mapping[str, Any], endpoint_sha256: str
) -> None:
    if _forbidden_paths(terminal):
        raise StoredEndpointRejected("EXACT_OUTER_TERMINAL_CROSSED_AUTHORITY_BOUNDARY")
    if (
        terminal.get("endpoint_float64_sha256") != endpoint_sha256
        or terminal.get("authority_pass") is not False
        or terminal.get("status") == "TARGET_AUTHORITY_READY"
        or terminal.get("descriptor") is not None
    ):
        raise StoredEndpointRejected("EXACT_OUTER_TERMINAL_NOT_A_BOUND_REJECTION")
    fallback = terminal.get("exact_coordinate_fallback")
    if not isinstance(fallback, Mapping):
        raise StoredEndpointRejected("EXACT_OUTER_FALLBACK_EVIDENCE_ABSENT")
    seconds = fallback.get("allocated_seconds")
    process = fallback.get("process")
    if (
        fallback.get("authority_pass") is not False
        or fallback.get("status")
        in {
            "TARGET_AUTHORITY_READY",
            "NOT_RUN_INSUFFICIENT_ENDPOINT_ALLOCATION",
            "LOCK_BUSY_DEFERRED",
            "MEMORY_BUSY_DEFERRED",
        }
        or not isinstance(seconds, (int, float))
        or isinstance(seconds, bool)
        or not 0 < float(seconds) <= MAX_EXACT_OUTER_SECONDS
        or not _is_sha256(fallback.get("result_sha256"))
        or fallback.get("truth_used") is not False
        or fallback.get("target_set_completeness_claim") is not False
        or not isinstance(process, Mapping)
        or process.get("classification") != "SUCCESS"
        or process.get("accepted_output") is not True
        or process.get("returncode") != 0
        or process.get("timeout") is not False
        or process.get("rss_cap_exceeded") is not False
        or process.get("rss_monitor_failed") is not False
        or process.get("output_cap_exceeded") is not False
        or process.get("descendant_leak") is not False
    ):
        raise StoredEndpointRejected("EXACT_OUTER_FALLBACK_NOT_CLEANLY_EXHAUSTED")


def inspect_applicability(
    *,
    source_bytes: bytes,
    bridge_payload: bytes,
    exact_outer_terminal: Mapping[str, Any],
    proposal_index: int,
    atom_ordinal: int,
    endpoint_float64_sha256: str,
) -> Applicability:
    """Validate a source/endpoint/bridge join without launching HP children."""

    if len(source_bytes) > MAX_SOURCE_BYTES:
        raise StoredEndpointRejected("SOURCE_SIZE_CAP")
    if not _is_sha256(endpoint_float64_sha256):
        raise StoredEndpointRejected("ENDPOINT_SHA256_MALFORMED")
    if (
        not isinstance(proposal_index, int)
        or isinstance(proposal_index, bool)
        or proposal_index < 0
        or not isinstance(atom_ordinal, int)
        or isinstance(atom_ordinal, bool)
        or atom_ordinal < 0
    ):
        raise StoredEndpointRejected("PROPOSAL_OR_ATOM_ORDINAL_MALFORMED")
    _validate_exact_outer_rejection(exact_outer_terminal, endpoint_float64_sha256)

    d1 = _load_d1()
    eligibility = d1.classify_source(source_bytes)
    if not eligibility.eligible or len(eligibility.atoms) > MAX_ATOMS:
        raise StoredEndpointRejected("SOURCE_NOT_NARROW_POINT_ON_CIRCLE_ELIGIBLE")
    if atom_ordinal >= len(eligibility.atoms):
        raise StoredEndpointRejected("ATOM_ORDINAL_OUTSIDE_ELIGIBILITY_SET")

    bridge = _object(bridge_payload, label="BRIDGE", maximum=MAX_BRIDGE_BYTES)
    cascade = d1._load_cascade()
    refinement, owned_payload, source_sha256, _case_id = cascade._validate_bridge(
        bridge, source_bytes
    )
    proposals = cascade._sequence(refinement.get("proposals"), "refinement proposals")
    if len(proposals) > MAX_PROPOSALS or proposal_index >= len(proposals):
        raise StoredEndpointRejected("PROPOSAL_COUNT_OR_INDEX_CAP")
    owned = cascade._owned_by_index(owned_payload)
    if set(owned) != set(range(len(proposals))):
        raise StoredEndpointRejected("OWNED_PROPOSAL_COVERAGE_MISMATCH")
    proposal = cascade._mapping(proposals[proposal_index], "refinement proposal")
    source_record = cascade._mapping(proposal.get("source"), "proposal source")
    if source_record.get("endpoint_float64_sha256") != endpoint_float64_sha256:
        raise StoredEndpointRejected("BRIDGE_ENDPOINT_DOES_NOT_MATCH_EXACT_OUTER")
    coordinate_768 = proposal.get("coordinates_768bit_minimum")
    coordinate_1024 = proposal.get("coordinates_1024bit_minimum")
    if (
        proposal.get("independent_precision_lanes") is not True
        or not isinstance(coordinate_768, list)
        or not isinstance(coordinate_1024, list)
        or not coordinate_768
        or len(coordinate_768) != len(coordinate_1024)
    ):
        raise StoredEndpointRejected("INDEPENDENT_COORDINATE_LANES_ABSENT")
    atom = eligibility.atoms[atom_ordinal]
    if atom.coordinate_index >= len(coordinate_1024):
        raise StoredEndpointRejected("POINT_ON_CIRCLE_COORDINATE_OUTSIDE_BRIDGE")
    try:
        cascade._adapt_proposal(
            proposal,
            owned[proposal_index],
            json.loads(source_bytes)["variables"]["names"],
        )
    except Exception as error:
        raise StoredEndpointRejected("NON_TURN_EXACT_COORDINATES_UNAVAILABLE") from error
    return Applicability(
        source_sha256=source_sha256,
        endpoint_float64_sha256=endpoint_float64_sha256,
        proposal_index=proposal_index,
        atom_ordinal=atom_ordinal,
        atom_binding_sha256=atom.atom_binding_sha256,
        bridge_sha256=_sha256(bridge_payload),
        current_exact_outer_exhausted=True,
        independent_coordinate_lanes=True,
    )


def run_private_hold_or_baseline(
    *,
    source_bytes: bytes,
    bridge_payload: bytes,
    exact_outer_terminal: Mapping[str, Any],
    proposal_index: int,
    atom_ordinal: int,
    endpoint_float64_sha256: str,
    untouched_baseline: Any,
    point_runner: Callable[..., Any] | None = None,
) -> Any:
    """Run one corrected terminal lane or return baseline by object identity."""

    try:
        applicability = inspect_applicability(
            source_bytes=source_bytes,
            bridge_payload=bridge_payload,
            exact_outer_terminal=exact_outer_terminal,
            proposal_index=proposal_index,
            atom_ordinal=atom_ordinal,
            endpoint_float64_sha256=endpoint_float64_sha256,
        )
        d1 = _load_d1()
        eligibility = d1.classify_source(source_bytes)
        runner = d1._default_point_runner if point_runner is None else point_runner
        result = runner(
            source_bytes=source_bytes,
            bridge_payload=bridge_payload,
            proposal_index=proposal_index,
            atom=eligibility.atoms[atom_ordinal],
        )
        d1._validate_terminal_result(result)
        if result.status != "VERIFIED" or not isinstance(result.exact_v2_record, Mapping):
            return untouched_baseline
        return CandidateHold(
            untouched_baseline=untouched_baseline,
            exact_v2_record=result.exact_v2_record,
            applicability=applicability,
        )
    except Exception:
        return untouched_baseline


__all__ = [
    "Applicability",
    "CandidateHold",
    "StoredEndpointRejected",
    "inspect_applicability",
    "run_private_hold_or_baseline",
]
