#!/usr/bin/env python3
"""CPU15 generated integration/containment smoke; emits aggregate only."""

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
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import candidate


def _load_outer():
    spec = importlib.util.spec_from_file_location("repair_a_generated_outer", HERE / "worker.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("outer worker import failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _point_document(c=(0, 2), d=(-8, 6), *, zero_ray=False):
    names = ["ax", "ay", "ox", "oy", "bx", "by", "cx", "cy", "dx", "dy"]
    values = ["1", "0", "0", "0", "3", "4", *map(str, c), *map(str, d)]
    if zero_ray:
        values[6:8] = ["0", "0"]
    construction = [
        {"name": name, "expr": f"Point({x}, {y})"}
        for name, x, y in (
            ("A", "ax", "ay"),
            ("O", "ox", "oy"),
            ("B", "bx", "by"),
            ("C", "cx", "cy"),
            ("D", "dx", "dy"),
        )
    ]
    document = {
        "task": "solve",
        "variables": {"names": names},
        "construction": construction,
        "constraints": [
            {"def": "Angle(A, O, B)", "value": "Angle(C, O, D)"}
        ],
        "guards": ["ax > 0"],
        "bounds": [[-20, 20] for _ in names],
        "answer": "ax",
        "post_process": None,
    }
    return document, values


def _line_document():
    return {
        "task": "solve",
        "variables": {"names": ["x"]},
        "construction": [
            {"name": "L1", "expr": "Line(1,0,0)"},
            {"name": "L2", "expr": "Line(3,4,0)"},
            {"name": "M1", "expr": "Line(0,1,0)"},
            {"name": "M2", "expr": "Line(4,3,0)"},
        ],
        "constraints": [{"def": "Angle(L1,L2)", "value": "Angle(M1,M2)"}],
        "guards": [],
        "bounds": [[-2, 2]],
        "answer": "x",
        "post_process": None,
    }, ["1"]


def _certify(document, values):
    return candidate.certify_exact_coordinate_witness(
        document,
        values,
        values,
        "1",
        "1",
        timeout_seconds=15,
    )


def _endpoint_sha256(endpoint):
    payload = struct.pack(">I", len(endpoint)) + b"".join(
        struct.pack(">d", value) for value in endpoint
    )
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    if os.sched_getaffinity(0) != {15}:
        raise RuntimeError("generated Repair A must be pinned to CPU15")
    positive_document, positive_values = _point_document()
    reflected_document, reflected_values = _point_document(c=(0, -2), d=(-8, -6))
    line_document, line_values = _line_document()
    supplementary_document, supplementary_values = _point_document(c=(1, 0), d=(-3, 4))
    zero_document, zero_values = _point_document(zero_ray=True)
    positives = [
        _certify(positive_document, positive_values),
        _certify(reflected_document, reflected_values),
        _certify(line_document, line_values),
    ]
    negatives = [
        _certify(supplementary_document, supplementary_values),
        _certify(zero_document, zero_values),
    ]
    positive_pass = sum(
        item.get("authority_pass") is True
        and item.get("typed_direct_angle_equality_exact") is True
        and item.get("typed_angle_relation_count") == 1
        and item.get("source_raw_answer_exact") is True
        and item.get("target_link_exact") is True
        and item.get("root_ordinal_attestation_complete") is True
        for item in positives
    )
    negative_reject = sum(item.get("authority_pass") is False for item in negatives)

    outer = _load_outer()
    with tempfile.TemporaryDirectory(prefix="repair-a-generated-") as name:
        root = Path(name)
        source = root / "source.json"
        raw = json.dumps(positive_document, separators=(",", ":")).encode()
        source.write_bytes(raw)
        endpoint = [float(value) for value in positive_values]
        endpoint_sha256 = _endpoint_sha256(endpoint)
        trial = SimpleNamespace(
            endpoint=endpoint,
            endpoint_sha256=endpoint_sha256,
            residual_inf=0.0,
            provisional_target=1.0,
            cluster_ordinal=0,
            cluster_rank=0,
        )
        kwargs = {
            "source": source,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "candidate": trial,
            "cpu": 15,
            "output": root,
        }
        descriptor, side_evidence = outer._run_modified_angle_side(
            kwargs=kwargs,
            side_seconds=6.0,
        )

        baseline = {
            "status": "GENERATED_BASELINE_FAILURE",
            "authority_pass": False,
            "descriptor": None,
        }
        observed_baseline_seconds = []
        outer._run_current_exact_outer = lambda **call: (
            observed_baseline_seconds.append(call["timeout_seconds"]) or baseline
        )
        identity_kwargs = {**kwargs, "timeout_seconds": 20.0}
        absent_artifact_identity = outer._run_repair_a(**identity_kwargs) is baseline
        outer._baseline_ambiguous_angle_failure = lambda **_call: True
        outer._run_modified_angle_side = lambda **_call: (
            None,
            {"authority_pass": False},
        )
        side_failure_identity = outer._run_repair_a(**identity_kwargs) is baseline
        trial.endpoint = []
        zero_dimension_identity = outer._run_repair_a(**identity_kwargs) is baseline

    containment = side_evidence.get("containment") or {}
    process = side_evidence.get("process") or {}
    result = {
        "schema_version": "geotarget.exact-typed-angle-repair-a-generated/v1",
        "scope": "generated only; no corpus, scorer, truth, or formal benchmark",
        "positive_exact_replay": {"pass": positive_pass, "total": len(positives)},
        "negative_near_miss": {"rejected": negative_reject, "total": len(negatives)},
        "full_fallback_side": {
            "authority_pass": descriptor is not None and side_evidence.get("authority_pass") is True,
            "typed_angle_relation_count": side_evidence.get("typed_angle_relation_count"),
        },
        "fallback_identity": {
            "absent_failure_artifact": absent_artifact_identity,
            "side_failure": side_failure_identity,
            "zero_dimension": zero_dimension_identity,
        },
        "budget": {
            "baseline_seconds_for_total_20": observed_baseline_seconds[0],
            "baseline_fraction": 0.75,
            "side_maximum_fraction": 0.25,
        },
        "containment": {
            "cpu_affinity": containment.get("cpu_affinity"),
            "same_process_group": containment.get("same_process_group"),
            "pdeathsig": containment.get("pdeathsig"),
            "guard_classification": process.get("classification"),
            "containment_breach": process.get("containment_breach"),
            "descendant_leak": process.get("descendant_leak"),
        },
        "qreflect_used": False,
        "formal_benchmark_run": False,
        "truth_scorer_manifest_or_result_used": False,
    }
    ok = (
        positive_pass == len(positives)
        and negative_reject == len(negatives)
        and result["full_fallback_side"]["authority_pass"]
        and all(result["fallback_identity"].values())
        and result["budget"]["baseline_seconds_for_total_20"] == 15.0
        and containment.get("cpu_affinity") == [15]
        and containment.get("same_process_group") is True
        and containment.get("pdeathsig") == 9
        and process.get("classification") == "SUCCESS"
        and process.get("containment_breach") is False
        and process.get("descendant_leak") is False
    )
    result["d0_pass"] = ok
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
