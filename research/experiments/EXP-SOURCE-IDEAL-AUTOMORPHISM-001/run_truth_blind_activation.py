#!/usr/bin/env python3.12
"""Root-owned aggregate-only activation census on frozen anonymous endpoints.

This runner consumes no expected answer and emits no individual source path,
endpoint, coefficient, proposal, target, or signature.  It is an activation
gate only; proposals remain non-authoritative local-search starts.
"""

from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Mapping

from candidate import ExactSource, Predicate, PROPOSAL_STATUS, augment_baseline


REQUESTS = Path(
    "/home/kabatan/work/solver-experiment-results/"
    "partial-ideal-root-readiness-v1/degree1-requests.json"
).resolve()
REQUESTS_SHA256 = "ee424315256582652ea0df72a05c21903a5fd4366867c6788129a79e4f80fd35"
SOURCE_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results/"
    "partial-ideal-root-readiness-v1/degree1-inputs"
).resolve()
OUTPUT_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results/"
    "source-ideal-signed-automorphism-orbit-v1"
).resolve()
RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver").resolve()
SOURCE_COMPILER_PATH = (
    RUNTIME_ROOT
    / "research/experiments/EXP-REAL61-004/msolve_all_real_proposal/source_compile.py"
)
SOURCE_COMPILER_SHA256 = "24d6cee020256043f6ad4657ffa84a8b4e9188ab9ff18bf3e9339672a3229349"
SEMANTIC_COMPILER_PATH = (
    RUNTIME_ROOT / "research/experiments/EXP-REAL61-002/algebraic_lane/compiler.py"
)
SEMANTIC_COMPILER_SHA256 = "f127f7f1e2f93161e1353f07222e93ffacfa1c2dbd4e68e5b1fd23a8a3b10318"
LEGACY_RUNTIME_PATH = (
    RUNTIME_ROOT / "research/experiments/EXP-REAL61-001/legacy61_runtime.py"
)
LEGACY_RUNTIME_SHA256 = "3261a6289f4a43681e698937c158d4a4f1740e54b70b88559c399e3b6395ec2b"
REQUEST_KEYS = frozenset({"source_path", "endpoint", "candidate_relation_high_to_low"})
FORBIDDEN_KEYS = frozenset(
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
FORBIDDEN_SOURCE_KEYS = frozenset(
    {"id", "case_id", "problem_id", "slug", "family", "truth", "outcome", "result", "score", "known_count"}
)
BASELINE = b"source-ideal-signed-automorphism-fallback-v1\x00"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError("frozen module cannot be loaded")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _bounded_source_path(value: object) -> Path:
    if not isinstance(value, str):
        raise ValueError("SOURCE_CUSTODY_REJECTED")
    path = Path(value).resolve()
    if path.parent != SOURCE_ROOT or path.suffix != ".json" or not path.is_file():
        raise ValueError("SOURCE_CUSTODY_REJECTED")
    return path


def _fraction(value: object) -> Fraction | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("NONRATIONAL_BOUND")
    result = Fraction(str(value))
    if result.denominator == 0:
        raise ValueError("NONRATIONAL_BOUND")
    return result


def _bounds(document: Mapping[str, object], dimension: int):
    value = document.get("bounds")
    if value is None:
        return ()
    if not isinstance(value, list) or len(value) != dimension:
        raise ValueError("BOUND_DIMENSION_MISMATCH")
    result = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError("BOUND_MALFORMED")
        result.append((_fraction(item[0]), _fraction(item[1])))
    return tuple(result)


def _exact_source(document: Mapping[str, object], compiled: Mapping[str, object]) -> ExactSource:
    source_names = document.get("variables")
    source_names = source_names.get("names") if isinstance(source_names, Mapping) else None
    cover_names = compiled.get("cover_variable_names")
    equations = compiled.get("equations")
    predicates = compiled.get("predicates")
    if (
        not isinstance(source_names, list)
        or not all(isinstance(name, str) and name for name in source_names)
        or cover_names != source_names
        or not isinstance(equations, list)
        or not all(isinstance(text, str) for text in equations)
        or not isinstance(predicates, list)
        or compiled.get("branch_replay_obligation_count") != 0
        or compiled.get("replay_obligations") != []
    ):
        raise ValueError("NONBIJECTIVE_OR_REPLAY_OBLIGATION")
    converted_predicates = []
    for predicate in predicates:
        if (
            not isinstance(predicate, Mapping)
            or predicate.get("relation") not in {"gt", "ge", "ne"}
            or not isinstance(predicate.get("expression"), str)
        ):
            raise ValueError("PREDICATE_MALFORMED")
        converted_predicates.append(
            Predicate(str(predicate["relation"]), str(predicate["expression"]))
        )
    return ExactSource(
        tuple(source_names),
        tuple(equations),
        tuple(converted_predicates),
        _bounds(document, len(source_names)),
    )


def _endpoint(value: object, dimension: int) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != dimension:
        raise ValueError("ENDPOINT_MALFORMED")
    endpoint = tuple(float(item) for item in value)
    if any(not math.isfinite(item) for item in endpoint):
        raise ValueError("ENDPOINT_MALFORMED")
    return endpoint


def _atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n"
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--requests-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-cpu", type=int, default=14)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    if os.sched_getaffinity(0) != {arguments.expected_cpu} or arguments.expected_cpu != 14:
        raise SystemExit("truth-blind activation must run only on CPU14")
    if arguments.requests.resolve() != REQUESTS:
        raise SystemExit("requests are outside approved custody")
    if arguments.output.resolve().parent != OUTPUT_ROOT or arguments.output.suffix != ".json":
        raise SystemExit("output is outside approved repository-external root")
    request_payload = arguments.requests.read_bytes()
    if (
        arguments.requests_sha256.lower() != REQUESTS_SHA256
        or _sha256(request_payload) != REQUESTS_SHA256
    ):
        raise SystemExit("request SHA-256 mismatch")
    pinned = (
        (SOURCE_COMPILER_PATH, SOURCE_COMPILER_SHA256),
        (SEMANTIC_COMPILER_PATH, SEMANTIC_COMPILER_SHA256),
        (LEGACY_RUNTIME_PATH, LEGACY_RUNTIME_SHA256),
    )
    if any(not path.is_file() or _sha256(path.read_bytes()) != digest for path, digest in pinned):
        raise SystemExit("frozen compiler/runtime closure changed")
    compiler = _load("source_ideal_automorphism_frozen_compiler", SOURCE_COMPILER_PATH)
    runtime = _load("source_ideal_automorphism_frozen_legacy_runtime", LEGACY_RUNTIME_PATH)
    requests = json.loads(request_payload)
    if not isinstance(requests, list):
        raise SystemExit("requests must be an array")

    counts: Counter[str] = Counter()
    signatures: set[str] = set()
    for request in requests:
        counts["request"] += 1
        try:
            if (
                not isinstance(request, Mapping)
                or set(request) != REQUEST_KEYS
                or FORBIDDEN_KEYS & set(request)
            ):
                raise ValueError("REQUEST_SCHEMA_REJECTED")
            source_path = _bounded_source_path(request["source_path"])
            payload = source_path.read_bytes()
            document = json.loads(payload)
            if not isinstance(document, Mapping) or FORBIDDEN_SOURCE_KEYS & set(document):
                raise ValueError("SOURCE_IDENTITY_BOUNDARY_REJECTED")
            compiled, _msolve_input = compiler.compile_source_document(
                dict(document), source_bytes=payload
            )
            if compiled.get("status") != "ELIGIBLE_MSOLVE_DIMENSION_PROBE":
                counts["compile_ineligible"] += 1
                continue
            source = _exact_source(document, compiled)
            endpoint = _endpoint(request["endpoint"], len(source.variables))
            _opaque, _budget, evaluator = runtime.build_opaque_case(
                dict(document), callback_cap=4, deadline=time.monotonic() + 60.0
            )

            def replay(point: tuple[float, ...]) -> bool:
                return runtime.validate_endpoint(evaluator, point).get("safe") is True

            if not replay(endpoint):
                counts["accepted_endpoint_invalid"] += 1
                continue
            result = augment_baseline(
                source,
                accepted_endpoint=endpoint,
                baseline_payload=BASELINE,
                replay=replay,
            )
            counts["structural_eligible"] += int(result.eligible)
            counts["source_invalid"] += result.source_invalid
            counts["fallback_byte_mismatch"] += int(result.baseline_payload is not BASELINE)
            if result.status != PROPOSAL_STATUS:
                counts["candidate_unknown"] += 1
                continue
            false = sum(not replay(proposal) for proposal in result.proposals)
            counts["false_emission"] += false
            if false == 0 and result.proposals:
                counts["activation_source"] += 1
                counts["proposal"] += len(result.proposals)
                if result.anonymous_signature is not None:
                    signatures.add(result.anonymous_signature)
        except Exception:
            # Individual failure text is intentionally not exposed; the fixed
            # aggregate bucket cannot encode source identity or target outcome.
            counts["custody_or_compile_rejected"] += 1

    decision = "GO_REVIEW" if (
        counts["activation_source"] >= 3
        and len(signatures) >= 2
        and counts["false_emission"] == 0
        and counts["source_invalid"] == 0
        and counts["fallback_byte_mismatch"] == 0
    ) else "STOP_ZERO_OR_NARROW_ACTIVATION"
    aggregate = {
        "schema_version": "geotarget.source-ideal-signed-automorphism-activation/v1",
        "decision": decision,
        "request_count": counts["request"],
        "compile_ineligible_count": counts["compile_ineligible"],
        "custody_or_compile_rejected_count": counts["custody_or_compile_rejected"],
        "accepted_endpoint_invalid_count": counts["accepted_endpoint_invalid"],
        "structural_eligible_count": counts["structural_eligible"],
        "candidate_unknown_count": counts["candidate_unknown"],
        "activation_source_count": counts["activation_source"],
        "anonymous_signature_count": len(signatures),
        "proposal_count": counts["proposal"],
        "false_emission_count": counts["false_emission"],
        "source_invalid_count": counts["source_invalid"],
        "fallback_byte_mismatch_count": counts["fallback_byte_mismatch"],
        "individual_records_emitted": False,
        "paths_endpoints_coefficients_targets_emitted": False,
        "truth_used": False,
        "case_identity_routing": False,
        "canonical_source_replay_bypassed": False,
        "target_release": False,
        "completeness_claim": False,
    }
    _atomic_write(arguments.output.resolve(), aggregate)
    print(json.dumps(aggregate, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
