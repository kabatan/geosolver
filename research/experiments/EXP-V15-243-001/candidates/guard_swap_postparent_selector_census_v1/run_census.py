#!/usr/bin/env python3
"""Target-free census of archived full-parent endpoints for guard swap.

The coordinator validates the frozen search18 artifact and launches one fresh
worker process per physical source.  A worker replays only archived parent
endpoints through the hash-pinned source adapter and exact frozen pair
certificate selector.  Persisted output is aggregate-only: no endpoint,
problem name, target, truth, or per-source identifier is written.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
from typing import Mapping, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
ARCHIVE = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/results/guard-equation-swap-search18-5s-seed0-v1"
)
OLD_CANDIDATE = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/candidates/guard_equation_swap_continuation/candidate.py"
)
OLD_ADAPTER = OLD_CANDIDATE.with_name("v15_typed_adapter.py")
MANIFEST_SHA256 = "ab7c9a73fb75d0302cbc79330939f62ac20944b73622df8a35ea41cb6a327ac1"
PLAN_SHA256 = "654b213ca116badca3a303a3feebb0cfa7dbc4de3a38f823afac1bd0bf0a0088"
CANDIDATE_SHA256 = "aee0886c6a3e37ea1069128de9523a0b5647e15eba8e8622b7fa0865dc6f07ef"
ADAPTER_SHA256 = "b9dabe71cb863a4bed906201de0833b2d97230d7a430118c95a2d61f01cedd3e"
SOURCE_COUNT = 18
START_COUNT = 24
MAX_STDOUT_BYTES = 65536
THREAD_VARIABLES = (
    "OMP_NUM_THREADS",
    "OMP_THREAD_LIMIT",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "JULIA_NUM_THREADS",
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_json(path: Path) -> Mapping[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError(f"JSON root is not an object: {path}")
    return raw


def _load_module(name: str, path: Path, expected_sha256: str):
    if _sha256(path.read_bytes()) != expected_sha256:
        raise RuntimeError(f"hash-pinned dependency changed: {path.name}")
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _point(values: object) -> np.ndarray:
    point = np.asarray(values, dtype=float)
    if point.ndim != 1 or point.size < 1 or not np.all(np.isfinite(point)):
        raise ValueError("archived point is malformed")
    return point


def _point_digest(point: np.ndarray) -> str:
    values = np.asarray(point, dtype=np.float64)
    digest = hashlib.sha256()
    digest.update(struct.pack("!Q", int(values.size)))
    digest.update(values.astype(">f8", copy=False).tobytes())
    return digest.hexdigest()


def _ordered_digest(points: Sequence[np.ndarray]) -> str:
    digest = hashlib.sha256()
    digest.update(struct.pack("!Q", len(points)))
    for lane, point in enumerate(points):
        values = np.asarray(point, dtype=np.float64)
        digest.update(struct.pack("!qQ", lane, int(values.size)))
        digest.update(values.astype(">f8", copy=False).tobytes())
    return digest.hexdigest()


def _signature(adapter: object, guard_row: int) -> str:
    slots = tuple(getattr(adapter, "_slots"))
    programs = tuple(getattr(getattr(adapter, "_ad_program"), "guards"))
    slot = slots[int(guard_row)]
    guard = programs[int(slot.source_ordinal)]
    payload = {
        "source_kind": str(slot.source_kind),
        "guard_kind": str(getattr(guard, "kind", "")),
        "operator": str(getattr(guard, "operator", "")),
        "side": str(slot.side),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return _sha256(encoded)


def _validated_streams(
    trials: Sequence[Mapping[str, object]], expected_source_sha256: str
) -> tuple[tuple[np.ndarray, np.ndarray, str], ...]:
    observations: dict[tuple[int, bytes, bytes], tuple[np.ndarray, np.ndarray, str]] = {}
    for trial in trials:
        if trial.get("source_sha256") != expected_source_sha256:
            raise ValueError("trial/source binding changed")
        if trial.get("plan_sha256") != PLAN_SHA256:
            raise ValueError("trial plan binding changed")
        if trial.get("target_evaluated") is not False:
            raise ValueError("target-evaluated trial is forbidden")
        if trial.get("completed") is not True:
            continue
        prefix = trial.get("literal_prefix")
        stream = trial.get("parent_endpoint_stream")
        if not isinstance(prefix, Mapping) or not isinstance(stream, Mapping):
            raise ValueError("completed trial lacks parent records")
        raw_starts = prefix.get("points")
        raw_entries = stream.get("entries")
        if not isinstance(raw_starts, list) or not isinstance(raw_entries, list):
            raise ValueError("completed parent record is malformed")
        if len(raw_starts) != START_COUNT or len(raw_entries) != START_COUNT:
            raise ValueError("completed parent record is not the full prefix")
        starts = tuple(_point(value) for value in raw_starts)
        if _ordered_digest(starts) != prefix.get("sha256"):
            raise ValueError("literal prefix digest changed")
        endpoints: list[np.ndarray] = []
        for expected_lane, entry in enumerate(raw_entries):
            if not isinstance(entry, Mapping) or entry.get("lane") != expected_lane:
                raise ValueError("parent endpoint order changed")
            endpoint = _point(entry.get("point"))
            if endpoint.shape != starts[expected_lane].shape:
                raise ValueError("parent endpoint dimension changed")
            if _point_digest(endpoint) != entry.get("configuration_sha256"):
                raise ValueError("parent configuration digest changed")
            endpoints.append(endpoint)
            key = (expected_lane, endpoint.tobytes(), starts[expected_lane].tobytes())
            observations[key] = (
                endpoint,
                starts[expected_lane],
                str(entry["configuration_sha256"]),
            )
        if _ordered_digest(endpoints) != stream.get("sha256"):
            raise ValueError("parent endpoint stream digest changed")
        if stream.get("order_preserved") is not True:
            raise ValueError("parent endpoint stream was reordered")
    return tuple(observations[key] for key in sorted(observations))


def _worker(work_item_path: Path) -> int:
    item = _load_json(work_item_path)
    source_path = Path(str(item["source_path"]))
    expected_source_sha256 = str(item["source_sha256"])
    source_bytes = source_path.read_bytes()
    if _sha256(source_bytes) != expected_source_sha256:
        raise ValueError("physical source bytes changed")
    trials = tuple(_load_json(Path(str(path))) for path in item["trial_paths"])
    observations = _validated_streams(trials, expected_source_sha256)
    kernel = _load_module("guard_swap_census_kernel", OLD_CANDIDATE, CANDIDATE_SHA256)
    adapter_module = _load_module(
        "guard_swap_census_typed_adapter", OLD_ADAPTER, ADAPTER_SHA256
    )
    result: dict[str, object] = {
        "schema_version": "geotarget.guard-swap-postparent-source-census-worker/v1",
        "input_binding_sha256": str(item["input_binding_sha256"]),
        "archived_observation_count": len(observations),
        "static_square": False,
        "static_analytic_residual": False,
        "static_smooth_slot_count": 0,
        "eligible_endpoint_count": 0,
        "eligible_configuration_count": 0,
        "eligible_guard_signature_sha256": [],
        "status_counts": {},
        "target_evaluated": False,
        "authority_pass": False,
        "target_release": False,
    }
    try:
        adapter = adapter_module.build_typed_adapter(
            source_bytes,
            expected_source_sha256,
            source_callback_cap=max(1, len(observations)),
            deadline_monotonic=time.monotonic() + float(item["adapter_seconds"]),
        )
    except adapter_module.AdapterIneligible:
        result["status_counts"] = {"source_static_ineligible": len(observations)}
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    result["static_square"] = True
    result["static_analytic_residual"] = bool(
        getattr(adapter, "_residual_static_analytic")
    )
    result["static_smooth_slot_count"] = len(tuple(getattr(adapter, "_slots")))
    configuration = kernel.Configuration()
    lower = np.asarray(adapter.source_lower, dtype=float)
    upper = np.asarray(adapter.source_upper, dtype=float)
    statuses: Counter[str] = Counter()
    eligible_configurations: set[str] = set()
    signatures: set[str] = set()
    for endpoint, physical_start, configuration_sha256 in observations:
        if endpoint.shape != lower.shape or np.any(endpoint < lower) or np.any(endpoint > upper):
            statuses["outside_literal_bounds"] += 1
            continue
        try:
            observed = adapter.observe_for_swap(endpoint.copy())
        except Exception:
            statuses["observation_error"] += 1
            continue
        residual = np.asarray(observed.residual, dtype=float)
        residual_inf = (
            float(np.linalg.norm(residual, ord=np.inf))
            if residual.size and np.all(np.isfinite(residual))
            else math.inf
        )
        if not bool(observed.finite):
            statuses["nonfinite"] += 1
            continue
        if bool(observed.source_valid):
            statuses["source_valid"] += 1
            continue
        if residual_inf > configuration.root_entry_tolerance:
            statuses["residual_above_entry"] += 1
            continue
        state = kernel._State(
            endpoint.copy(),
            residual.copy(),
            np.asarray(observed.smooth_margins, dtype=float).copy(),
            True,
            False,
            None
            if observed.residual_jacobian is None
            else np.asarray(observed.residual_jacobian, dtype=float).copy(),
            None
            if observed.margin_jacobian is None
            else np.asarray(observed.margin_jacobian, dtype=float).copy(),
            np.asarray(observed.smooth_margin_provenance, dtype=bool).copy(),
        )
        counters = kernel.Counters()
        selected = kernel._select_pair(
            state,
            np.maximum(1.0, np.abs(physical_start)),
            configuration,
            counters,
        )
        if selected is None:
            statuses["pair_ineligible"] += 1
            continue
        certificate = selected[0]
        statuses["eligible"] += 1
        eligible_configurations.add(configuration_sha256)
        signatures.add(_signature(adapter, certificate.guard_row))
    result["eligible_endpoint_count"] = statuses["eligible"]
    result["eligible_configuration_count"] = len(eligible_configurations)
    result["eligible_guard_signature_sha256"] = sorted(signatures)
    result["status_counts"] = dict(sorted(statuses.items()))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


def _coordinator(output_path: Path, worker_timeout: float, adapter_seconds: float) -> int:
    if not output_path.is_absolute():
        raise ValueError("aggregate output path must be absolute")
    if HERE == output_path or HERE in output_path.parents:
        raise ValueError("aggregate output must remain outside the candidate directory")
    manifest_path = ARCHIVE / "RUN_MANIFEST.json"
    if _sha256(manifest_path.read_bytes()) != MANIFEST_SHA256:
        raise RuntimeError("frozen search18 run manifest changed")
    manifest = _load_json(manifest_path)
    if manifest.get("plan_sha256") != PLAN_SHA256:
        raise RuntimeError("frozen search18 plan changed")
    raw_results = manifest.get("results")
    if not isinstance(raw_results, list) or len(raw_results) != SOURCE_COUNT * 2:
        raise RuntimeError("frozen search18 result set changed")
    trial_paths: dict[int, list[Path]] = defaultdict(list)
    source_sha256: dict[int, str] = {}
    closure = hashlib.sha256()
    closure.update(manifest_path.read_bytes())
    for record in raw_results:
        if not isinstance(record, Mapping):
            raise RuntimeError("run manifest result is malformed")
        source_slot = int(record["source_ordinal"])
        job = int(record["job_ordinal"])
        trial_path = ARCHIVE / "trials" / f"{job:03d}.json"
        payload = trial_path.read_bytes()
        if _sha256(payload) != record.get("sha256"):
            raise RuntimeError("archived trial hash changed")
        trial = json.loads(payload)
        expected = str(trial["source_sha256"])
        previous = source_sha256.setdefault(source_slot, expected)
        if previous != expected:
            raise RuntimeError("paired trials disagree on physical source")
        trial_paths[source_slot].append(trial_path)
        closure.update(payload)
    if set(source_sha256) != set(range(SOURCE_COUNT)):
        raise RuntimeError("physical source coverage changed")
    environment = os.environ.copy()
    for name in THREAD_VARIABLES:
        environment[name] = "1"
    worker_rows: list[Mapping[str, object]] = []
    failures: Counter[str] = Counter()
    with tempfile.TemporaryDirectory(prefix="guard-swap-census-") as temporary:
        temporary_root = Path(temporary)
        for source_slot in range(SOURCE_COUNT):
            source_path = ARCHIVE / "physical_sources" / f"{source_slot:03d}.json"
            if _sha256(source_path.read_bytes()) != source_sha256[source_slot]:
                raise RuntimeError("physical source archive changed")
            closure.update(source_path.read_bytes())
            item = {
                "source_path": str(source_path),
                "source_sha256": source_sha256[source_slot],
                "trial_paths": [str(path) for path in trial_paths[source_slot]],
                "adapter_seconds": adapter_seconds,
            }
            binding = _sha256(
                json.dumps(item, sort_keys=True, separators=(",", ":")).encode()
            )
            item["input_binding_sha256"] = binding
            item_path = temporary_root / f"source-{source_slot:03d}.json"
            item_path.write_text(
                json.dumps(item, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            try:
                completed = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve()), "worker", "--work-item", str(item_path)],
                    check=False,
                    capture_output=True,
                    timeout=worker_timeout,
                    env=environment,
                )
            except subprocess.TimeoutExpired:
                failures["worker_timeout"] += 1
                continue
            if len(completed.stdout) > MAX_STDOUT_BYTES:
                failures["worker_output_oversize"] += 1
                continue
            if completed.returncode != 0:
                failures["worker_nonzero"] += 1
                continue
            try:
                row = json.loads(completed.stdout)
            except Exception:
                failures["worker_malformed"] += 1
                continue
            if not isinstance(row, Mapping) or row.get("input_binding_sha256") != binding:
                failures["worker_binding_mismatch"] += 1
                continue
            if row.get("target_evaluated") is not False:
                failures["target_evaluated"] += 1
                continue
            worker_rows.append(row)
    eligible_sources = sum(int(row["eligible_endpoint_count"]) > 0 for row in worker_rows)
    signatures: dict[str, int] = defaultdict(int)
    for row in worker_rows:
        for signature in set(row["eligible_guard_signature_sha256"]):
            signatures[str(signature)] += 1
    statuses: Counter[str] = Counter()
    for row in worker_rows:
        statuses.update({str(key): int(value) for key, value in row["status_counts"].items()})
    result = {
        "schema_version": "geotarget.guard-swap-postparent-source-census/v1",
        "input_closure_sha256": closure.hexdigest(),
        "run_manifest_sha256": MANIFEST_SHA256,
        "old_candidate_sha256": CANDIDATE_SHA256,
        "old_typed_adapter_sha256": ADAPTER_SHA256,
        "physical_source_count": SOURCE_COUNT,
        "worker_success_count": len(worker_rows),
        "worker_failure_counts": dict(sorted(failures.items())),
        "source_with_archived_observations_count": sum(
            int(row["archived_observation_count"]) > 0 for row in worker_rows
        ),
        "archived_unique_observation_count": sum(
            int(row["archived_observation_count"]) for row in worker_rows
        ),
        "static_square_source_count": sum(bool(row["static_square"]) for row in worker_rows),
        "static_analytic_residual_source_count": sum(
            bool(row["static_analytic_residual"]) for row in worker_rows
        ),
        "static_smooth_slot_source_count": sum(
            int(row["static_smooth_slot_count"]) > 0 for row in worker_rows
        ),
        "eligible_source_count": eligible_sources,
        "eligible_endpoint_count": sum(
            int(row["eligible_endpoint_count"]) for row in worker_rows
        ),
        "eligible_configuration_count": sum(
            int(row["eligible_configuration_count"]) for row in worker_rows
        ),
        "distinct_guard_signature_count": len(signatures),
        "guard_signature_source_multiplicities": sorted(signatures.values()),
        "eligible_endpoint_counts_by_source_sorted": sorted(
            int(row["eligible_endpoint_count"]) for row in worker_rows
        ),
        "status_counts": dict(sorted(statuses.items())),
        "gate": {
            "minimum_eligible_sources": 4,
            "minimum_distinct_guard_signatures": 2,
        },
        "target_truth_case_family_or_outcome_used": False,
        "authority_pass": False,
        "target_release": False,
    }
    passed = bool(
        len(worker_rows) == SOURCE_COUNT
        and not failures
        and eligible_sources >= 4
        and len(signatures) >= 2
    )
    result["decision"] = "GO_SELECTOR_PROTOTYPE_HOLD" if passed else "STOP_SELECTOR_CENSUS"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if passed else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)
    worker = subparsers.add_parser("worker")
    worker.add_argument("--work-item", type=Path, required=True)
    coordinator = subparsers.add_parser("coordinator")
    coordinator.add_argument("--output", type=Path, required=True)
    coordinator.add_argument("--worker-timeout", type=float, default=30.0)
    coordinator.add_argument("--adapter-seconds", type=float, default=25.0)
    arguments = parser.parse_args()
    if arguments.mode == "worker":
        return _worker(arguments.work_item)
    if arguments.worker_timeout <= 0 or arguments.adapter_seconds <= 0:
        raise ValueError("worker limits must be positive")
    return _coordinator(
        arguments.output.resolve(), arguments.worker_timeout, arguments.adapter_seconds
    )


if __name__ == "__main__":
    raise SystemExit(main())
