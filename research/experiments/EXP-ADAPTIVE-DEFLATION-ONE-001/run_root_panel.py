#!/usr/bin/env python3
"""Root-only fresh-refiner gate for the degree-one endpoint panel.

This is intentionally a disposable experiment connector.  It runs the frozen
ordinary high-precision refiner in a fresh process, converts only a mechanical
refinement miss into the already frozen real-gate contract, and publishes
aggregate counts.  It neither emits a proposal nor claims authority.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Mapping

import real_gate_scanner as gate


SOURCE_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-inputs"
).resolve()
REFINER = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/EXP-REAL61-001/refine_proposals_worker.py"
)
PYTHON = Path("/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python")
REQUEST_KEYS = {"source_path", "endpoint", "candidate_relation_high_to_low"}
THREAD_ENV = {
    "PYTHONHASHSEED": "0",
    "OMP_NUM_THREADS": "1",
    "OMP_THREAD_LIMIT": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "JULIA_NUM_THREADS": "1",
}


def _source(record: object) -> tuple[Path, bytes, list[float]]:
    if not isinstance(record, Mapping) or set(record) != REQUEST_KEYS:
        raise ValueError("request-contract")
    raw = record.get("source_path")
    endpoint = record.get("endpoint")
    if not isinstance(raw, str) or not isinstance(endpoint, list):
        raise ValueError("request-contract")
    path = Path(raw).resolve()
    if path.parent != SOURCE_ROOT or not path.name.endswith(".json"):
        raise ValueError("source-containment")
    if not path.stem.isdigit() or len(path.stem) != 4:
        raise ValueError("source-containment")
    values = []
    for item in endpoint:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError("endpoint-contract")
        value = float(item)
        if not math.isfinite(value):
            raise ValueError("endpoint-contract")
        values.append(value)
    payload = path.read_bytes()
    return path, payload, values


def _fresh_refinement_contract(
    path: Path,
    payload: bytes,
    endpoint: list[float],
    timeout_seconds: float,
) -> tuple[dict[str, object], str]:
    digest = hashlib.sha256(payload).hexdigest()
    trial = {
        "accuracy_claims_permitted": False,
        "candidate": "adaptive-deflation-one-root-gate",
        "validations": [
            {
                "safe": True,
                "endpoint": endpoint,
                "residual_inf": 0.0,
                "diagnostic_target": None,
            }
        ],
    }
    environment = os.environ.copy()
    environment.update(THREAD_ENV)
    with tempfile.TemporaryDirectory(prefix="adaptive-deflation-refiner-") as name:
        root = Path(name)
        trial_path = root / "trial.json"
        output_path = root / "proposal.json"
        trial_path.write_text(
            json.dumps(trial, separators=(",", ":")), encoding="utf-8"
        )
        try:
            completed = subprocess.run(
                [
                    str(PYTHON),
                    str(REFINER),
                    "--case",
                    str(path),
                    "--case-sha256",
                    digest,
                    "--trial",
                    str(trial_path),
                    "--output",
                    str(output_path),
                ],
                cwd=REFINER.parent,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return {
                "variant": "fresh-frozen-real61",
                "status": "HIGH_PRECISION_REFINEMENT_FAILED",
                "numeric_v3_ready": False,
                "target_stability_ready": False,
            }, "refiner-timeout"
        if completed.returncode != 0 or not output_path.is_file():
            return {
                "variant": "fresh-frozen-real61",
                "status": "HIGH_PRECISION_REFINEMENT_FAILED",
                "numeric_v3_ready": False,
                "target_stability_ready": False,
            }, "refiner-failed"
        result = json.loads(output_path.read_text(encoding="utf-8"))
    proposals = result.get("proposals") if isinstance(result, Mapping) else None
    ready = bool(
        isinstance(proposals, list)
        and any(
            isinstance(proposal, Mapping)
            and proposal.get("status") == "PSLQ_PROPOSAL"
            and proposal.get("numeric_gate_1e_100") is True
            for proposal in proposals
        )
    )
    return {
        "variant": "fresh-frozen-real61",
        "status": (
            "TARGET_STABILITY_READY" if ready else "HIGH_PRECISION_REFINEMENT_FAILED"
        ),
        "numeric_v3_ready": ready,
        "target_stability_ready": ready,
    }, "refiner-ready" if ready else "refiner-miss"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--requests-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-source-seconds", type=float, default=30.0)
    arguments = parser.parse_args()
    if sorted(os.sched_getaffinity(0)) != [14]:
        raise SystemExit("CPU14 required")
    request_payload = arguments.requests.read_bytes()
    if hashlib.sha256(request_payload).hexdigest() != arguments.requests_sha256:
        raise SystemExit("request SHA mismatch")
    requests = json.loads(request_payload)
    if not isinstance(requests, list):
        raise SystemExit("strict list required")
    counts = Counter({"input_count": len(requests)})
    records = []
    started = time.monotonic()
    for raw in requests:
        try:
            path, payload, endpoint = _source(raw)
            source = json.loads(payload)
            names = (source.get("variables") or {}).get("names") if isinstance(source, Mapping) else None
            constraints = source.get("constraints") if isinstance(source, Mapping) else None
            if not isinstance(names, list) or len(names) != 2 or not isinstance(constraints, list) or len(constraints) != 2 or len(endpoint) != 2:
                counts["prefilter_non_square_n2_count"] += 1
                continue
            counts["prefilter_square_n2_count"] += 1
            contract, status = _fresh_refinement_contract(
                path, payload, endpoint, arguments.per_source_seconds
            )
            counts[status + "_count"] += 1
            records.append(
                {
                    "source_path": str(path),
                    "source_sha256": hashlib.sha256(payload).hexdigest(),
                    "endpoint": endpoint,
                    "refinement_contract": contract,
                }
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            counts["input_rejected_count"] += 1
    result = gate.scan_manifest(
        {"schema_version": gate.INPUT_SCHEMA, "records": records}
    )
    public = {
        "schema_version": "geotarget.adaptive-deflation-one-fresh-root-panel/v1",
        "decision": result["decision"],
        "gate_pass": result["gate_pass"],
        "stage_counts": dict(sorted(counts.items())),
        "real_gate_counts": result["counts"],
        "signature_count": result["signature_count"],
        "elapsed_wall_seconds": time.monotonic() - started,
        "proposal_or_authority_enabled": False,
        "truth_score_case_family_outcome_read": False,
        "individual_records_emitted": False,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(public, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
