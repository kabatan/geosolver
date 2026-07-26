#!/usr/bin/env python3
"""Champion-v2+PoC with the existing 8n cross-endpoint HP rung scheduler.

This is deliberately a thin experimental composition.  Search, endpoint
selection, exact descriptor construction, and the zero-dimensional route are
the current champion bytes.  Only ``BASE._service_candidates`` is replaced by
the already implemented FIFO rung scheduler and H1-no-1280 rung runner.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from typing import Mapping, Sequence

from precision_runtime_preload import install


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CHAMPION_PATH = HERE / "champion_v2_poc_preloaded.py"
CROSS = (
    ROOT
    / "research/experiments/EXP-V15-243-001/candidates/cross_endpoint_hp_rungs"
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(CROSS) not in sys.path:
    sys.path.insert(0, str(CROSS))


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


CHAMPION = _load(
    "geotarget_repro_20260722_champion_v2_poc_cross_endpoint_base",
    CHAMPION_PATH,
)
SCHEDULER = _load(
    "geotarget_repro_20260722_cross_endpoint_scheduler",
    CROSS / "scheduler.py",
)
# h1_binding imports the candidate-private scheduler by its original local
# module name.  Bind that name to the same bytes before loading the runner.
sys.modules.setdefault("scheduler", SCHEDULER)
H1 = _load(
    "geotarget_repro_20260722_cross_endpoint_h1_binding",
    CROSS / "h1_binding.py",
)

BASE = CHAMPION.CHAMPION.BASE
_ORIGINAL_PLAN = BASE._plan
DENSE_BUILD_FACTOR = 8
MAXIMUM_DISPATCHES_PER_ENDPOINT = 4


def _evidence_sha256(candidate: object, ordinal: int) -> str:
    payload = {
        "endpoint": [float(value) for value in candidate.endpoint],
        "residual_inf": float(candidate.residual_inf),
        "semantic_verified": candidate.semantic_verified is True,
        "discovery_ordinal": ordinal,
    }
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def _safe_endpoints(
    source_sha256: str, candidates: Sequence[object]
) -> tuple[object, ...]:
    rows = []
    for ordinal, candidate in enumerate(candidates):
        if candidate.semantic_verified is not True:
            continue
        values = tuple(float(value) for value in candidate.endpoint)
        endpoint_sha256 = SCHEDULER.endpoint_float64_sha256(values)
        safety = SCHEDULER.EndpointSafetyCertificate(
            source_sha256=source_sha256,
            endpoint_sha256=endpoint_sha256,
            evidence_sha256=_evidence_sha256(candidate, ordinal),
            semantic_valid=True,
            hard_feasible=True,
            guard_ok=True,
            intrinsic_domain_ok=True,
        )
        rows.append(
            SCHEDULER.SafeEndpoint(
                values=values,
                discovery_ordinal=ordinal,
                safety=safety,
            )
        )
    return tuple(rows)


def _statistics(
    *, candidate_count: int, result: object | None, failure: str | None = None
) -> dict[str, object]:
    dispatches = tuple(result.dispatches) if result is not None else ()
    return {
        "policy": "existing cross-endpoint FIFO 8n cumulative HP rungs",
        "dense_build_factor": DENSE_BUILD_FACTOR,
        "primary_total": candidate_count,
        "primary_tranche_capacity": candidate_count,
        "primary_selected_count": candidate_count,
        "primary_deferred_unknown_count": (
            len(result.resume_queue) if result is not None else candidate_count
        ),
        "unselected_primary_disposition": "FIFO_RESUME_QUEUE",
        "primary_attempted": len(dispatches),
        "primary_wave_complete": bool(result is not None and not result.resume_queue),
        "all_discovered_primaries_served": bool(
            result is not None and not result.resume_queue
        ),
        "eligible_alternate_count": 0,
        "alternate_attempted": 0,
        "alternate_wave_complete": True,
        "same_cluster_alternates_skipped_after_authority": 0,
        "eligible_restoration_count": 0,
        "restoration_attempted": 0,
        "restoration_wave_complete": True,
        "cross_cluster_candidate_suppression": False,
        "cross_endpoint_status": result.status if result is not None else failure,
        "charged_dense_builds": (
            result.charged_dense_builds if result is not None else 0
        ),
        "charged_seconds": result.charged_seconds if result is not None else 0.0,
    }


def _service_candidates(
    *,
    source: Path,
    source_sha256: str,
    candidates: Sequence[object],
    cpu: int,
    output: Path,
    hard_deadline: float,
):
    del cpu, output  # H1 rungs execute in the already pinned case process.
    safe = _safe_endpoints(source_sha256, candidates)
    if not safe:
        return [], {}, _statistics(candidate_count=0, result=None, failure="NO_SAFE_ENDPOINT")
    remaining = max(
        0.0,
        hard_deadline - time.monotonic() - BASE.FINALIZE_RESERVE_SECONDS,
    )
    if remaining < 0.25:
        return [], {}, _statistics(
            candidate_count=len(safe), result=None, failure="INSUFFICIENT_HP_TIME"
        )
    payload = source.read_bytes()
    if hashlib.sha256(payload).hexdigest() != source_sha256:
        raise RuntimeError("source bytes changed before cross-endpoint HP")
    policy = SCHEDULER.RungPolicy(
        dense_build_factor=DENSE_BUILD_FACTOR,
        total_seconds=remaining,
        maximum_dispatches=MAXIMUM_DISPATCHES_PER_ENDPOINT * len(safe),
        maximum_dispatches_per_endpoint=MAXIMUM_DISPATCHES_PER_ENDPOINT,
    )
    result = SCHEDULER.run_fifo_rungs(
        payload,
        source_sha256,
        len(safe[0].values),
        safe,
        policy=policy,
        runner=H1.H1No1280RungRunner(),
    )
    attempts = [dict(row) for row in result.dispatches]
    descriptors: dict[str, dict[str, object]] = {}
    if isinstance(result.authority, Mapping):
        descriptor = BASE._authority_descriptor(result.authority)
        if descriptor is not None:
            descriptors[BASE._descriptor_key(descriptor)] = descriptor
            attempts.append(
                {
                    "attempt_kind": "CROSS_ENDPOINT_FIFO_8N_AUTHORITY",
                    "endpoint_float64_sha256": result.winner_endpoint_sha256,
                    "status": "TARGET_AUTHORITY_READY",
                    "authority_pass": True,
                    "descriptor": descriptor,
                }
            )
    return attempts, descriptors, _statistics(
        candidate_count=len(safe), result=result
    )


def _plan(**kwargs) -> dict[str, object]:
    plan = _ORIGINAL_PLAN(**kwargs)
    plan.update(
        {
            "cross_endpoint_hp_rungs": True,
            "cross_endpoint_dense_build_factor": DENSE_BUILD_FACTOR,
            "cross_endpoint_maximum_dispatches_per_endpoint": (
                MAXIMUM_DISPATCHES_PER_ENDPOINT
            ),
            "cross_endpoint_scheduler_path": str(CROSS / "scheduler.py"),
            "cross_endpoint_h1_binding_path": str(CROSS / "h1_binding.py"),
            "candidate_worker_path": str(Path(__file__).resolve()),
            "candidate_worker_sha256": BASE._sha256(Path(__file__).read_bytes()),
        }
    )
    return plan


BASE._service_candidates = _service_candidates
BASE._plan = _plan
install(BASE, "geotarget_repro_20260722_cross_endpoint_precision_runtime")


def main() -> None:
    CHAMPION.main()


if __name__ == "__main__":
    main()
