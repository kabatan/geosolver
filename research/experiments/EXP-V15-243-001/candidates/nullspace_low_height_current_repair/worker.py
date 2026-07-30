#!/usr/bin/env python3
"""Baseline-first current exact outer plus nullspace transport side replay."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from typing import Mapping


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path(
    os.environ.get(
        "GEOTARGET_CURRENT_RUNTIME_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
CURRENT_OUTER = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/"
    "exact_outer_decorator/worker.py"
)
CURRENT_OUTER_SHA256 = (
    "05650c1016f3974c0f74845037c76604eb38f2f4a337cc700721f0e148d9d3f7"
)
SIDE_WORKER = HERE / "fallback_worker.py"
BASELINE_FRACTION = 0.75
SIDE_FRACTION = 0.25
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import authority_boundary as side_boundary


class IntegrationError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


if _sha256(CURRENT_OUTER) != CURRENT_OUTER_SHA256:
    raise IntegrationError("current exact outer SHA-256 changed")
OUTER = _load("nullspace_transport_current_exact_outer", CURRENT_OUTER)
BASE = OUTER.BASE
RESOURCE = OUTER.RESOURCE
BASELINE = BASE._run_hp_candidate
BASELINE_CAPTURE_COUNT = 1


def _baseline_refinement_failure(kwargs: Mapping[str, object]) -> bool:
    artifact = Path(kwargs["output"]) / "exact-coordinate-fallback/RESULT.json"
    try:
        value = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    failure = str(value.get("failure", "")) if isinstance(value, Mapping) else ""
    signatures = (
        "independent refinement proposal contract failed",
        "independent coordinate refinement failed",
        "independent coordinate refinement timed out",
        "independent refinement emitted no document",
    )
    return bool(
        isinstance(value, Mapping)
        and value.get("schema_version")
        == "geotarget.v15-243-exact-coordinate-fallback/v1"
        and value.get("source_sha256") == str(kwargs["source_sha256"])
        and value.get("endpoint_float64_sha256")
        == str(kwargs["candidate"].endpoint_sha256)
        and value.get("status") == "EXACT_COORDINATE_FALLBACK_REJECTED"
        and value.get("authority_pass") is False
        and any(signature in failure for signature in signatures)
    )


def _command(kwargs: Mapping[str, object], artifact: Path, side_seconds: float):
    candidate = kwargs["candidate"]
    return [
        "taskset",
        "-c",
        str(int(kwargs["cpu"])),
        str(BASE.PYTHON),
        str(SIDE_WORKER),
        "--source",
        str(Path(kwargs["source"]).resolve()),
        "--source-sha256",
        str(kwargs["source_sha256"]),
        "--endpoint",
        json.dumps(candidate.endpoint, separators=(",", ":"), allow_nan=False),
        "--endpoint-sha256",
        str(candidate.endpoint_sha256),
        "--timeout-seconds",
        str(max(0.5, side_seconds - 0.5)),
        "--output",
        str(artifact.resolve()),
    ]


def _run_side(kwargs: Mapping[str, object], side_seconds: float):
    cpu = int(kwargs["cpu"])
    root = Path(kwargs["output"]) / "nullspace-low-height-transport"
    artifact = root / "RESULT.json"
    artifact.unlink(missing_ok=True)
    guarded = None
    try:
        with RESOURCE.adapter.per_core_lease(
            cpu,
            wait_seconds=min(
                RESOURCE.adapter.DEFAULT_POLICY.maximum_core_lease_wait_seconds,
                max(0.0, side_seconds - 1.0),
            ),
        ):
            root.mkdir(parents=True, exist_ok=True)
            guarded = BASE.run_guarded(
                _command(kwargs, artifact, side_seconds),
                limits=BASE.Limits(
                    timeout_seconds=side_seconds,
                    rss_bytes=768 * 1024**2,
                    address_space_bytes=3072 * 1024**2,
                    data_bytes=2048 * 1024**2,
                    output_bytes=1024**2,
                    tail_bytes=16 * 1024,
                ),
                environment=BASE.THREAD_ENVIRONMENT,
                cwd=RUNTIME_ROOT,
                status_path=root / "process-status.json",
            )
    except RESOURCE.adapter.LeaseUnavailable:
        return None, {"status": "LOCK_BUSY_DEFERRED", "authority_pass": False}
    fallback = None
    try:
        loaded = json.loads(artifact.read_text(encoding="utf-8"))
        if isinstance(loaded, Mapping):
            fallback = loaded
    except (OSError, json.JSONDecodeError):
        pass
    source = Path(kwargs["source"])
    source_sha256 = str(kwargs["source_sha256"])
    candidate = kwargs["candidate"]
    descriptor = (
        side_boundary.exact_descriptor(fallback.get("descriptor"))
        if isinstance(fallback, Mapping)
        else None
    )
    try:
        source_document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        source_document = None
    if not (
        guarded is not None
        and guarded.accepted_output
        and guarded.descendant_leak is not True
        and isinstance(fallback, Mapping)
        and fallback.get("schema_version")
        == "geotarget.v15-243-exact-coordinate-fallback/v1"
        and fallback.get("completed") is True
        and fallback.get("status") == "EXACT_COORDINATE_TARGET_AUTHORITY_READY"
        and fallback.get("authority_pass") is True
        and side_boundary.matches_sha256(source, source_sha256)
        and fallback.get("source_sha256") == source_sha256
        and fallback.get("endpoint_float64_sha256") == candidate.endpoint_sha256
        and fallback.get("truth_used") is False
        and fallback.get("case_family_known_target_count_routing") is False
        and fallback.get("source_or_problem_modified") is False
        and fallback.get("bounds_added_or_inferred") is False
        and fallback.get("coordinate_reparameterization") is False
        and fallback.get("target_set_completeness_claim") is False
        and fallback.get("within_fallback_wall_budget") is True
        and descriptor is not None
        and isinstance(source_document, Mapping)
        and side_boundary.nested_exact_authority_matches_source(
            fallback, descriptor, source_document, source_sha256
        )
    ):
        descriptor = None
    transport = (
        fallback.get("nullspace_low_height_transport")
        if isinstance(fallback, Mapping)
        else None
    )
    containment = (
        fallback.get("containment") if isinstance(fallback, Mapping) else None
    )
    accepted = bool(
        descriptor is not None
        and isinstance(transport, Mapping)
        and transport.get("status") == "TRANSPORT_HP_LANES_READY"
        and transport.get("three_independent_hp_lanes_required") is True
        and transport.get("exact_polynomial_jacobian_rank") is True
        and transport.get("dependent_univariate_gcd") is True
        and transport.get("exact_source_and_strict_guard_substitution") is True
        and transport.get("square_free_minpolys") is True
        and isinstance(transport.get("distinct_exact_slice_count"), int)
        and not isinstance(transport.get("distinct_exact_slice_count"), bool)
        and int(transport.get("distinct_exact_slice_count")) >= 2
        and transport.get("routing_uses_target_answer_id_family_or_outcome")
        is False
        and isinstance(containment, Mapping)
        and containment.get("same_process_group") is True
        and containment.get("pdeathsig") == 9
        and containment.get("cpu_affinity") == [cpu]
    )
    evidence = {
        "status": "TARGET_AUTHORITY_READY" if accepted else "SIDE_REJECTED",
        "authority_pass": accepted,
        "allocated_seconds": side_seconds,
        "result_sha256": _sha256(artifact) if artifact.is_file() else None,
        "process": guarded.to_dict() if guarded is not None else None,
        "transport": dict(transport) if isinstance(transport, Mapping) else None,
        "containment": (
            dict(containment) if isinstance(containment, Mapping) else None
        ),
        "truth_used": False,
        "target_set_completeness_claim": False,
    }
    return descriptor if accepted else None, evidence


def _run(**kwargs):
    total = float(kwargs["timeout_seconds"])
    started = time.monotonic()
    baseline_kwargs = dict(kwargs)
    baseline_kwargs["timeout_seconds"] = max(0.5, total * BASELINE_FRACTION)
    baseline = BASELINE(**baseline_kwargs)
    if OUTER._ordinary_resource_busy(baseline) or OUTER._ordinary_ready(baseline):
        return baseline
    candidate = kwargs["candidate"]
    endpoint = getattr(candidate, "endpoint", None)
    if not isinstance(endpoint, (list, tuple)) or len(endpoint) == 0:
        return baseline
    if not _baseline_refinement_failure(kwargs):
        return baseline
    side_seconds = min(total * SIDE_FRACTION, total - (time.monotonic() - started))
    if side_seconds < 0.5:
        return baseline
    descriptor, evidence = _run_side(kwargs, side_seconds)
    if descriptor is None:
        return baseline
    return {
        "attempt_kind": "NULLSPACE_LOW_HEIGHT_WITNESS_TRANSPORT_REPAIR",
        "endpoint_float64_sha256": candidate.endpoint_sha256,
        "residual_inf": candidate.residual_inf,
        "provisional_target": candidate.provisional_target,
        "cluster_ordinal": candidate.cluster_ordinal,
        "cluster_rank": candidate.cluster_rank,
        "status": "TARGET_AUTHORITY_READY",
        "authority_pass": True,
        "descriptor": descriptor,
        "baseline_exact_outer_result": baseline,
        "nullspace_transport": evidence,
        "baseline_minimum_fraction": BASELINE_FRACTION,
        "side_maximum_fraction": SIDE_FRACTION,
        "case_family_truth_target_count_routing": False,
    }


if getattr(BASE, "_nullspace_low_height_transport_installed", False):
    raise IntegrationError("transport repair installed twice")
BASE._run_hp_candidate = _run
BASE._nullspace_low_height_transport_installed = True


def main():
    OUTER.SCHEDULER_MODULE.main()


if __name__ == "__main__":
    main()
