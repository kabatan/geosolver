#!/usr/bin/env python3
"""CPU14 generated qreflect repair tests; emits aggregate evidence only."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path(
    os.environ.get(
        "GEOTARGET_CURRENT_RUNTIME_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import candidate


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _endpoint_sha256(endpoint):
    payload = struct.pack(">I", len(endpoint)) + b"".join(
        struct.pack(">d", value) for value in endpoint
    )
    return hashlib.sha256(payload).hexdigest()


def _point_document(px: str, py: str, cx: str, cy: str):
    return {
        "task": "solve",
        "variables": {"names": ["x", "y"]},
        "construction": [
            {"name": "P", "expr": "Point(x,y)"},
            {"name": "C", "expr": f"Point({cx},{cy})"},
            {"name": "R", "expr": "Reflect(P,C)"},
        ],
        "constraints": [
            {"def": "x", "value": px},
            {"def": "y", "value": py},
        ],
        "guards": ["R.x != P.x"],
        "bounds": [[-30, 30], [-30, 30]],
        "answer": "R.x",
        "post_process": None,
    }


def _line_document():
    return {
        "task": "solve",
        "variables": {"names": ["x", "y"]},
        "construction": [
            {"name": "P", "expr": "Point(x,y)"},
            {"name": "L", "expr": "Line(1,0,-4)"},
            {"name": "R", "expr": "Reflect(P,L)"},
        ],
        "constraints": [
            {"def": "x", "value": "1"},
            {"def": "y", "value": "2"},
        ],
        "guards": ["R.x > P.x"],
        "bounds": [[-10, 10], [-10, 10]],
        "answer": "R.x",
        "post_process": None,
    }


def _certify(module, document, coordinates, answer):
    return module.certify_exact_coordinate_witness(
        document,
        coordinates,
        coordinates,
        answer,
        answer,
        timeout_seconds=20,
    )


def _positive(result):
    return bool(
        result.get("status") == "EXACT_TARGET_AUTHORITY_READY"
        and result.get("authority_pass") is True
        and result.get("source_raw_answer_exact") is True
        and result.get("target_link_exact") is True
        and result.get("root_ordinal_attestation_complete") is True
        and result.get("target_set_completeness_claim") is False
    )


def _classifier_checks(worker):
    point = _point_document("1", "2", "4", "7")
    line = _line_document()
    wrong_arity = json.loads(json.dumps(point))
    wrong_arity["construction"][2]["expr"] = "Reflect(P)"
    keyword = json.loads(json.dumps(point))
    keyword["construction"][2]["expr"] = "Reflect(P, center=C)"
    nested = json.loads(json.dumps(point))
    nested["construction"][2]["expr"] = "Reflect(P, Point(4,7))"
    selector = json.loads(json.dumps(point))
    selector["construction"][2]["expr"] = "Reflect(P,C)[0]"
    container = json.loads(json.dumps(point))
    container["construction"][2]["expr"] = "Reflect(P,[C])"
    unknown = json.loads(json.dumps(point))
    unknown["construction"][2]["expr"] = "Reflect(P,Z)"
    chained = json.loads(json.dumps(point))
    chained["construction"].append({"name": "S", "expr": "Reflect(R,C)"})
    return {
        "point_point": worker._direct_point_reflect_count(point),
        "point_line": worker._direct_point_reflect_count(line),
        "wrong_arity": worker._direct_point_reflect_count(wrong_arity),
        "keyword": worker._direct_point_reflect_count(keyword),
        "nested": worker._direct_point_reflect_count(nested),
        "selector": worker._direct_point_reflect_count(selector),
        "container": worker._direct_point_reflect_count(container),
        "unknown": worker._direct_point_reflect_count(unknown),
        "chained": worker._direct_point_reflect_count(chained),
    }


def _identity_checks(worker, root: Path, source: Path, source_sha: str):
    baseline = {"status": "NO_EXACT_AUTHORITY", "authority_pass": False}
    candidate_object = SimpleNamespace(
        endpoint=[1.0, 2.0],
        endpoint_sha256=_endpoint_sha256([1.0, 2.0]),
        residual_inf=0.0,
        provisional_target=7.0,
        cluster_ordinal=0,
        cluster_rank=0,
    )
    common = {
        "timeout_seconds": 40.0,
        "source": source,
        "source_sha256": source_sha,
        "candidate": candidate_object,
        "cpu": 14,
        "output": root,
    }
    artifact = root / "exact-coordinate-fallback/RESULT.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps(
            {
                "schema_version": "geotarget.v15-243-exact-coordinate-fallback/v1",
                "source_sha256": source_sha,
                "endpoint_float64_sha256": candidate_object.endpoint_sha256,
                "status": "EXACT_COORDINATE_FALLBACK_REJECTED",
                "authority_pass": False,
                "failure": "MethodError: no method matching qreflect(::QPoint, ::QPoint)",
            }
        ),
        encoding="utf-8",
    )
    original_baseline = worker.BASELINE
    original_side = worker._run_side
    captures = []
    try:
        worker.BASELINE = lambda **kwargs: baseline
        worker._run_side = lambda kwargs, seconds, count: (
            captures.append((seconds, count)) or (None, {"status": "SIDE_REJECTED"})
        )
        side_failure = worker._run(**common)
        worker._run_side = lambda kwargs, seconds, count: (_ for _ in ()).throw(
            RuntimeError("generated side crash")
        )
        side_crash = worker._run(**common)
        worker._run_side = lambda kwargs, seconds, count: (
            captures.append((seconds, count)) or (None, {"status": "SIDE_REJECTED"})
        )
        zero_candidate = SimpleNamespace(**candidate_object.__dict__)
        zero_candidate.endpoint = []
        zero_candidate.endpoint_sha256 = _endpoint_sha256([])
        zero = worker._run(**{**common, "candidate": zero_candidate})
        ready = {
            "status": "TARGET_AUTHORITY_READY",
            "authority_pass": True,
            "descriptor": {
                "minimal_polynomial_high_to_low": [1, -7],
                "selected_real_root_index": 0,
                "isolating_interval": {
                    "left": "7",
                    "right": "7",
                    "multiplicity": 1,
                    "real_root_index": 0,
                },
                "proposal_relation_low_to_high": [-7, 1],
                "confirmation_relation_low_to_high": [-7, 1],
                "target_512": "7",
                "target_768": "7",
                "target_1024": "7",
            },
        }
        worker.BASELINE = lambda **kwargs: ready
        ready_return = worker._run(**common)
    finally:
        worker.BASELINE = original_baseline
        worker._run_side = original_side
    return {
        "side_failure_baseline_identity": side_failure is baseline,
        "side_crash_baseline_identity": side_crash is baseline,
        "zero_dim_baseline_identity": zero is baseline,
        "ready_baseline_identity": ready_return is ready,
        "side_fraction_within_25pct": bool(captures and captures[0][0] <= 10.0),
        "side_direct_count": captures[0][1] if captures else None,
    }


def main() -> int:
    if os.sched_getaffinity(0) != {14}:
        raise RuntimeError("qreflect generated tests must be pinned to CPU14")
    current_candidate = _load(
        "qreflect_generated_current_candidate",
        RUNTIME_ROOT
        / "research/experiments/EXP-V15-243-001/candidates/"
        "exact_coordinate_replay/candidate.py",
    )
    worker = _load("qreflect_generated_worker", HERE / "worker.py")

    variants = [
        (_point_document("1", "2", "4", "7"), ["1", "2"], "7"),
        (_point_document("4", "7", "1", "2"), ["4", "7"], "-2"),
        (_point_document("1/2", "-2/3", "5/4", "7/3"), ["1/2", "-2/3"], "2"),
        (_point_document("4", "-3", "7", "2"), ["4", "-3"], "10"),
        (_point_document("-2", "1", "-7", "4"), ["-2", "1"], "-12"),
    ]
    point_results = [_certify(candidate, *variant) for variant in variants]
    current_point = _certify(current_candidate, *variants[0])
    line_document = _line_document()
    line_local = _certify(candidate, line_document, ["1", "2"], "7")
    line_current = _certify(current_candidate, line_document, ["1", "2"], "7")

    overload = """function qreflect(value::QPoint, center::QPoint)\n  return qsub(qscale(center, 2), value)\nend\n\n"""
    local_generated = candidate._extended_worker_source()
    line_dispatch_byte_parity = (
        local_generated.count(overload) == 1
        and local_generated.replace(overload, "", 1)
        == current_candidate._extended_worker_source()
    )
    classifier = _classifier_checks(worker)

    with tempfile.TemporaryDirectory(prefix="qreflect-generated-") as name:
        root = Path(name)
        source = root / "source.json"
        source.write_text(
            json.dumps(variants[0][0], separators=(",", ":")),
            encoding="utf-8",
        )
        source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
        identities = _identity_checks(worker, root, source, source_sha)
        side_candidate = SimpleNamespace(
            endpoint=[1.0, 2.0],
            endpoint_sha256=_endpoint_sha256([1.0, 2.0]),
            residual_inf=0.0,
            provisional_target=7.0,
            cluster_ordinal=0,
            cluster_rank=0,
        )
        descriptor, side_evidence = worker._run_side(
            {
                "source": source,
                "source_sha256": source_sha,
                "candidate": side_candidate,
                "cpu": 14,
                "output": root,
            },
            20.0,
            1,
        )

    aggregate = {
        "schema_version": "geotarget.qreflect-current-repair-generated/v1",
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "point_variants_passed": sum(_positive(item) for item in point_results),
        "point_variants_total": len(point_results),
        "current_point_missing_dispatch": bool(
            current_point.get("authority_pass") is False
            and "qreflect" in str(current_point.get("failure", "")).lower()
            and "qpoint" in str(current_point.get("failure", "")).lower()
        ),
        "line_local_pass": _positive(line_local),
        "line_current_pass": _positive(line_current),
        "line_dispatch_generated_byte_parity": line_dispatch_byte_parity,
        "classifier": classifier,
        "identity_and_budget": identities,
        "side_authority_pass": descriptor is not None,
        "side_containment": side_evidence.get("containment"),
        "side_canonical_parity": side_evidence.get(
            "canonical_source_guard_branch_raw_target_minpoly_ordinal_isolator_numeric_parity"
        ),
        "truth_used": False,
        "formal_corpus_manifest_result_scorer_used": False,
    }
    expected_classifier = {
        "point_point": 1,
        "point_line": 0,
        "wrong_arity": 0,
        "keyword": 0,
        "nested": 0,
        "selector": 0,
        "container": 0,
        "unknown": 0,
        "chained": 2,
    }
    passed = bool(
        aggregate["point_variants_passed"] == aggregate["point_variants_total"]
        and aggregate["current_point_missing_dispatch"]
        and aggregate["line_local_pass"]
        and aggregate["line_current_pass"]
        and aggregate["line_dispatch_generated_byte_parity"]
        and classifier == expected_classifier
        and all(identities.values())
        and aggregate["side_authority_pass"]
        and aggregate["side_canonical_parity"]
        and aggregate["side_containment"]
        == {"same_process_group": True, "pdeathsig": 9, "cpu_affinity": [14]}
    )
    aggregate["passed"] = passed
    (HERE / "GENERATED_RESULT.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(aggregate, ensure_ascii=False, separators=(",", ":")))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
