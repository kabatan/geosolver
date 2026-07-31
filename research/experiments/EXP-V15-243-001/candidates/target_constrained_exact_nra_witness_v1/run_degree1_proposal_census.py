#!/usr/bin/env python3
"""Aggregate-only degree-one adapter for the existing exact NRA candidate.

This file adds no compiler or solver.  It converts a root-owned primitive
degree-one projection into ``TargetProposal``, calls the existing
``candidate.prove`` backend on the existing digest-pinned primitive cover, and
uses the existing exact source runtime for a fresh untouched replay.  Because
the input is not the complete ordinary proposal, every external result is
HOLD even when the three internal checks pass.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Mapping

import sympy as sp

import applicability
import candidate as backend


REQUEST_KEYS = frozenset(
    {"source_path", "endpoint", "candidate_relation_high_to_low"}
)
FORBIDDEN_KEYS = frozenset(
    {
        "id",
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
STRATA = (
    "direct-polynomial",
    "periodic-ledger",
    "algebraic-cover-reconstruction",
    "selector-or-branch-ledger",
)
FAILURE_CLASSES = (
    "POST_PROCESS_OUTSIDE_RAW_TARGET_THEOREM",
    "DEGREE_ONE_PROJECTION_REJECTED",
    "EXISTING_PRIMITIVE_COVER_REJECTED",
    "EXISTING_TARGET_GRAPH_REJECTED",
    "BACKEND_RESOURCE_OR_TIMEOUT",
    "BACKEND_UNSAT_OR_NO_WITNESS",
    "BACKEND_OUTSIDE_COMPLETE_SUBSET",
    "UNTOUCHED_SOURCE_REPLAY_REJECTED",
    "UNTOUCHED_TARGET_LINK_REJECTED",
    "OTHER_FAIL_CLOSED",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--requests-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-cpu", type=int, default=14)
    parser.add_argument("--backend-timeout-seconds", type=float, default=3.0)
    return parser


def _proposal(coefficients: object) -> backend.TargetProposal:
    if (
        not isinstance(coefficients, list)
        or len(coefficients) != 2
        or any(not isinstance(item, int) or isinstance(item, bool) for item in coefficients)
    ):
        raise backend.NotProved("DEGREE_ONE_PROJECTION_REJECTED")
    leading, constant = coefficients
    common = math.gcd(abs(leading), abs(constant))
    if leading <= 0 or common != 1:
        raise backend.NotProved("DEGREE_ONE_PROJECTION_REJECTED")
    root = Fraction(-constant, leading)
    # A degree-one primitive polynomial has exactly this one real root.  The
    # fixed rational padding is an isolator construction, not target truth.
    return backend.TargetProposal(
        tuple(coefficients),
        0,
        root - 1,
        root + 1,
    )


def _validate_endpoint(value: object) -> None:
    if not isinstance(value, list) or not value:
        raise backend.NotProved("MALFORMED_ENDPOINT_LEDGER")
    converted = [float(item) for item in value]
    if any(not math.isfinite(item) for item in converted):
        raise backend.NotProved("MALFORMED_ENDPOINT_LEDGER")


def _failure_class(reason: object) -> str:
    text = str(reason)
    if "POST_PROCESS" in text:
        return "POST_PROCESS_OUTSIDE_RAW_TARGET_THEOREM"
    if "DEGREE_ONE_PROJECTION" in text or "PROPOSAL_" in text or "ISOLATOR" in text:
        return "DEGREE_ONE_PROJECTION_REJECTED"
    if "LEGACY_PRIMITIVE_COVER" in text:
        return "EXISTING_PRIMITIVE_COVER_REJECTED"
    if "LEGACY_TARGET_GRAPH" in text:
        return "EXISTING_TARGET_GRAPH_REJECTED"
    if "TIMEOUT" in text or "RESOURCE_" in text:
        return "BACKEND_RESOURCE_OR_TIMEOUT"
    if "UNSAT" in text or "NO_WITNESS" in text:
        return "BACKEND_UNSAT_OR_NO_WITNESS"
    if "POSITIVE_DIMENSIONAL" in text or "COMPLETE_SOLUTION" in text:
        return "BACKEND_OUTSIDE_COMPLETE_SUBSET"
    if "SOURCE_REPLAY" in text:
        return "UNTOUCHED_SOURCE_REPLAY_REJECTED"
    if "TARGET_LINK" in text:
        return "UNTOUCHED_TARGET_LINK_REJECTED"
    return "OTHER_FAIL_CLOSED"


def _assess_request(
    request: Mapping[str, object], *, timeout_seconds: float
) -> dict[str, object]:
    """Return a private fixed-category row; never a witness or target value."""

    private = {
        "descriptor_accepted": False,
        "primitive_cover_ready": False,
        "backend_attempted": False,
        "backend_witness_ready": False,
        "untouched_source_replay_pass": False,
        "untouched_target_link_pass": False,
        "thin_join_ready": False,
        "stratum": "none",
        "failure_class": "OTHER_FAIL_CLOSED",
        "internal_candidate_authority_observed": False,
    }
    try:
        _validate_endpoint(request["endpoint"])
        proposal = _proposal(request["candidate_relation_high_to_low"])
        private["descriptor_accepted"] = True
        source_path = Path(str(request["source_path"]))
        document = json.loads(source_path.read_bytes())
        if not isinstance(document, Mapping):
            raise backend.NotProved("LEGACY_PRIMITIVE_COVER_SOURCE_NOT_MAPPING")
        if document.get("post_process") not in (None, ""):
            raise backend.NotProved("POST_PROCESS_OUTSIDE_RAW_TARGET_THEOREM")

        source, metadata = applicability._legacy_target_link_source(document)
        stratum = str(metadata.get("structural_stratum"))
        if stratum not in STRATA:
            raise backend.NotProved("LEGACY_PRIMITIVE_COVER_UNKNOWN_STRATUM")
        private["stratum"] = stratum
        private["primitive_cover_ready"] = True
        private["backend_attempted"] = True
        witness = backend.prove(
            source,
            proposal,
            timeout_seconds=timeout_seconds,
        )
        if witness.get("authority_pass") is not True:
            raise backend.NotProved(str(witness.get("reason", "BACKEND_NO_WITNESS")))
        private["internal_candidate_authority_observed"] = True
        private["backend_witness_ready"] = True

        descriptors = witness.get("model_descriptors")
        raw_names = tuple(document.get("variables", {}).get("names", ()))
        if not isinstance(descriptors, Mapping) or not raw_names:
            raise backend.NotProved("UNTOUCHED_SOURCE_REPLAY_MODEL_LEDGER_MISSING")
        if any(name not in descriptors for name in raw_names):
            raise backend.NotProved("UNTOUCHED_SOURCE_REPLAY_RAW_COORDINATE_MISSING")
        raw_values = {
            name: backend._from_descriptor(descriptors[name]) for name in raw_names
        }
        _semantic, replay_module = backend._semantic_modules()
        replay = replay_module.ExactSourceRuntime(document, raw_values).verify()
        if replay.accepted is not True:
            raise backend.NotProved("UNTOUCHED_SOURCE_REPLAY_REJECTED")
        private["untouched_source_replay_pass"] = True

        target_descriptor = descriptors.get("__nra_raw_target")
        if not isinstance(target_descriptor, Mapping) or replay.target is None:
            raise backend.NotProved("UNTOUCHED_TARGET_LINK_MODEL_LEDGER_MISSING")
        backend_target = backend._from_descriptor(target_descriptor)
        untouched_target = sp.sympify(replay.target)
        if sp.simplify(backend_target - untouched_target) != 0:
            raise backend.NotProved("UNTOUCHED_TARGET_LINK_REJECTED")
        private["untouched_target_link_pass"] = True
        private["thin_join_ready"] = True
        private["failure_class"] = "NONE"
        return private
    except Exception as error:
        private["failure_class"] = _failure_class(error)
        return private


def main() -> int:
    arguments = _parser().parse_args()
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("degree-one NRA census must be pinned to the expected CPU")
    if not math.isfinite(arguments.backend_timeout_seconds) or arguments.backend_timeout_seconds <= 0:
        raise SystemExit("backend timeout must be finite and positive")
    payload = arguments.requests.read_bytes()
    observed_sha256 = hashlib.sha256(payload).hexdigest()
    if observed_sha256 != arguments.requests_sha256.lower():
        raise SystemExit("requests SHA-256 mismatch")
    requests = json.loads(payload)
    if not isinstance(requests, list):
        raise SystemExit("requests must be an array")

    counts = {
        "descriptor_accepted": 0,
        "descriptor_rejected": 0,
        "primitive_cover_ready": 0,
        "backend_attempted": 0,
        "backend_witness_ready": 0,
        "untouched_source_replay_pass": 0,
        "untouched_target_link_pass": 0,
        "thin_join_ready": 0,
        "internal_candidate_authority_observed": 0,
    }
    failures = {key: 0 for key in FAILURE_CLASSES}
    cover_strata = {key: 0 for key in STRATA}
    join_strata = {key: 0 for key in STRATA}

    for request in requests:
        if not isinstance(request, Mapping) or FORBIDDEN_KEYS & set(request):
            raise SystemExit("request crossed the identity/truth boundary")
        if set(request) != REQUEST_KEYS:
            raise SystemExit("request has unexpected keys")
        row = _assess_request(
            request,
            timeout_seconds=arguments.backend_timeout_seconds,
        )
        if row["descriptor_accepted"]:
            counts["descriptor_accepted"] += 1
        else:
            counts["descriptor_rejected"] += 1
        for key in (
            "primitive_cover_ready",
            "backend_attempted",
            "backend_witness_ready",
            "untouched_source_replay_pass",
            "untouched_target_link_pass",
            "thin_join_ready",
            "internal_candidate_authority_observed",
        ):
            if row[key]:
                counts[key] += 1
        stratum = str(row["stratum"])
        if row["primitive_cover_ready"] and stratum in cover_strata:
            cover_strata[stratum] += 1
        if row["thin_join_ready"] and stratum in join_strata:
            join_strata[stratum] += 1
        failure = str(row["failure_class"])
        if failure != "NONE":
            if failure not in failures:
                failure = "OTHER_FAIL_CLOSED"
            failures[failure] += 1

    aggregate = {
        "schema_version": "geotarget.target-constrained-nra-degree1-census/v1",
        "requests_sha256": observed_sha256,
        "request_count": len(requests),
        **counts,
        "failure_taxonomy": failures,
        "primitive_cover_fixed_strata": cover_strata,
        "thin_join_fixed_strata": join_strata,
        "individual_records_emitted": False,
        "raw_failure_reasons_emitted": False,
        "witnesses_or_targets_emitted": False,
        "endpoint_used_for_routing_or_backend": False,
        "ordinary_full_proposal_binding": False,
        "degree_one_projection_only": True,
        "authority_pass": False,
        "target_release": False,
        "common_worker_integration": "HOLD",
        "truth_used": False,
        "formal_scorer_used": False,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(aggregate, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
