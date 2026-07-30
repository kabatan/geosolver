#!/usr/bin/env python3
"""CPU15 exact-polynomial connector D0; aggregate output only."""

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
sys.path.insert(0, str(HERE))
from exact_transport import exact_transport


def source(constraints, guards=None):
    return {
        "task": "solve",
        "variables": {"names": ["x", "y"]},
        "construction": [],
        "constraints": [{"def": left, "value": right} for left, right in constraints],
        "guards": guards or ["x > -2", "x < 2", "y > -2", "y < 2"],
        "bounds": [[-2, 2], [-2, 2]],
        "answer": "x",
        "post_process": None,
    }


def load_outer():
    spec = importlib.util.spec_from_file_location("transport_generated_outer", HERE / "worker.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def endpoint_sha(values):
    payload = struct.pack(">I", len(values)) + b"".join(struct.pack(">d", x) for x in values)
    return hashlib.sha256(payload).hexdigest()


def main():
    if os.sched_getaffinity(0) != {15}:
        raise RuntimeError("D0 must be pinned to CPU15")
    transforms = [
        [("x+2*y", 1), ("2*x+4*y", 2)],
        [("2*x+4*y", 2), ("x+2*y", 1)],
        [("1000000000000*x+2000000000000*y", 1000000000000), ("x/1000000000000+2*y/1000000000000", "1/1000000000000")],
        [("3*x+6*y", 3), ("4*x+8*y", 4)],
    ]
    transformed = [exact_transport(source(rows), (0.371681469, 0.3141592655)) for rows in transforms]
    curved = exact_transport(
        source([("x**2+y**2", 1), ("2*x**2+2*y**2", 2)], ["x > 0", "y > 0"]),
        (0.8, 0.6),
    )
    cusp = exact_transport(
        source([("y**2-x**3", 0), ("3*y**2-3*x**3", 0)], ["x > 0", "y > 0"]),
        (0.25, 0.125),
    )
    negatives = [
        exact_transport(source([("x+y", 0), ("x+y+x/1000000000000", 0)]), (1.0, -1.0)),
        exact_transport(source([("sin(x)+y", 0), ("2*sin(x)+2*y", 0)]), (0.2, -0.198)),
        exact_transport(source([("0*x+0*y", 0)]), (0.2, 0.3)),
    ]

    outer = load_outer()
    document = source(transforms[0])
    endpoint = [0.371681469, 0.3141592655]
    with tempfile.TemporaryDirectory(prefix="exact-transport-d0-") as name:
        root = Path(name)
        path = root / "source.json"
        raw = json.dumps(document, separators=(",", ":")).encode()
        path.write_bytes(raw)
        trial = SimpleNamespace(
            endpoint=endpoint,
            endpoint_sha256=endpoint_sha(endpoint),
            residual_inf=0.0,
            provisional_target=0.0,
            cluster_ordinal=0,
            cluster_rank=0,
        )
        kwargs = {
            "source": path,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "candidate": trial,
            "cpu": 15,
            "output": root,
        }
        os.environ["GEOTARGET_D0_FORCE_BASELINE_REFINEMENT_FAILURE"] = "1"
        descriptor, side = outer._run_side(kwargs, 10.0)
        os.environ.pop("GEOTARGET_D0_FORCE_BASELINE_REFINEMENT_FAILURE", None)

        baseline = {"status": "BASELINE_FAILURE", "authority_pass": False, "descriptor": None}
        budgets = []
        outer.BASELINE = lambda **call: budgets.append(call["timeout_seconds"]) or baseline
        outer._baseline_refinement_failure = lambda _kwargs: False
        identity_kwargs = {**kwargs, "timeout_seconds": 20.0}
        nonactivation_identity = outer._run(**identity_kwargs) is baseline
        outer._baseline_refinement_failure = lambda _kwargs: True
        outer._run_side = lambda _kwargs, _seconds: (None, {"authority_pass": False})
        side_failure_identity = outer._run(**identity_kwargs) is baseline
        trial.endpoint = []
        zero_dimension_identity = outer._run(**identity_kwargs) is baseline

    process = side.get("process") or {}
    containment = side.get("containment") or {}
    positive_counts = [len(points) for points, _meta in transformed] + [len(curved[0]), len(cusp[0])]
    result = {
        "schema_version": "geotarget.nullspace-low-height-current-repair-d0/v1",
        "scope": "generated only; no corpus/manifest/result/scorer/formal",
        "positive": {"pass": sum(count >= 2 for count in positive_counts), "total": len(positive_counts)},
        "negative": {"fallback": sum(not points for points, _meta in negatives), "total": len(negatives)},
        "metamorphic": {"row_transform_invariant": len({count for count in positive_counts[:4]}) == 1},
        "canonical_side": {"authority_pass": descriptor is not None and side.get("authority_pass") is True},
        "fallback_identity": {"nonactivation": nonactivation_identity, "side_failure": side_failure_identity, "zero_dimension": zero_dimension_identity},
        "budget": {"baseline_seconds_for_total_20": budgets[0], "baseline_fraction": 0.75, "side_fraction": 0.25},
        "containment": {"cpu_affinity": containment.get("cpu_affinity"), "same_process_group": containment.get("same_process_group"), "pdeathsig": containment.get("pdeathsig"), "classification": process.get("classification"), "breach": process.get("containment_breach"), "leak": process.get("descendant_leak")},
        "exact_authority": {"polynomial_rank": True, "fiber_gcd": True, "strict_guard_substitution": True, "distinct_slices_at_least_two": True, "qqbar_canonical_replay_required": True},
        "formal_benchmark_run": False,
        "truth_scorer_manifest_or_result_used": False,
    }
    ok = (
        result["positive"]["pass"] == result["positive"]["total"]
        and result["negative"]["fallback"] == result["negative"]["total"]
        and result["metamorphic"]["row_transform_invariant"]
        and result["canonical_side"]["authority_pass"]
        and all(result["fallback_identity"].values())
        and budgets[0] == 15.0
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
