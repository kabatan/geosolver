"""Fail-closed transitive closure for the candidate-private champion-v5 path."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Mapping


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
BASE_PATH = HERE.parent / "adaptive_hp/transitive_manifest.py"
SCHEMA_VERSION = (
    "geotarget.exp-v15-243.point-on-circle-champion-v5-closure/v1"
)


def _load_base():
    name = "geotarget_point_on_circle_champion_closure_base_manifest"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, BASE_PATH)
    if specification is None or specification.loader is None:
        raise ImportError(BASE_PATH)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


BASE = _load_base()
ARM_ENV = BASE.ARM_ENV
CLOSURE_ENV = BASE.CLOSURE_ENV
ARM_NO_1280 = BASE.ARM_NO_1280
ARM_WITH_1280 = BASE.ARM_WITH_1280
ARMS = BASE.ARMS
ManifestError = BASE.ManifestError

CANDIDATE_FILES = {
    "poc_authority_adapter_wrapper": HERE / "authority_adapter_wrapper.py",
    "poc_backend_integration": HERE / "champion_backend_integration.py",
    "poc_adaptive_worker": HERE / "champion_composition_worker_no_1280.py",
    "poc_approved_hp_bridge": HERE / "approved_hp_bridge_v5.py",
    "poc_champion_v1_wrapper": HERE / "champion_v1_wrapper.py",
    "poc_champion_v2_wrapper": HERE / "champion_v2_wrapper.py",
    "poc_champion_v5_wrapper": HERE / "champion_v5_wrapper.py",
    "poc_dataset_runner": HERE / "run_dataset.py",
    "poc_one_core_contract": HERE / "one_core_contract.py",
    "poc_active_thin_runner": HERE / "active_run_candidate_one.py",
    "poc_active_primary_composition": HERE / "active_primary_composition_worker.py",
    "poc_active_hp_composition": HERE / "active_hp_composition_worker.py",
    "poc_active_scheduler_bridge": HERE / "active_scheduler_bridge.py",
    "champion_v5_base": HERE.parents[1] / "champion_v5/worker.py",
    "active_scheduler_bridge_base": HERE.parent / "hp_lock_scheduler/bridge.py",
    "active_champion_v0_hp_composition_base": (
        HERE.parents[1] / "champion_v0/hp_composition_worker.py"
    ),
    "active_primary_composition_base": (
        HERE.parents[2]
        / "EXP-REAL61-008/hp_precision_schedule_v11/composition_worker.py"
    ),
    "champion_v0_base_worker": HERE.parents[1] / "champion_v0/worker.py",
    "champion_v0_search_worker": (
        HERE.parents[1] / "champion_v0/search_worker.py"
    ),
    "champion_v0_base_hp_bridge": HERE.parents[1] / "champion_v0/hp_bridge.py",
    "champion_v0_frozen_base_worker": (
        HERE.parents[2] / "EXP-REAL61-008/finalist_numeric_worker_v15/worker.py"
    ),
    "champion_v0_endpoint_reservoir": (
        HERE.parent / "endpoint_reservoir/candidate.py"
    ),
    "champion_v0_search_adapter": (
        HERE.parents[2]
        / "EXP-REAL61-008/hybrid_direct_broyden_tr_lm_v9/"
        "corrective_nearroot_strict_restart_v2/adapter.py"
    ),
    "champion_v0_search_candidate": (
        HERE.parents[2]
        / "EXP-REAL61-008/hybrid_direct_broyden_tr_lm_v9/"
        "corrective_nearroot_strict_restart_v2/candidate.py"
    ),
    "champion_v0_search_retained_adapter": (
        HERE.parents[2]
        / "EXP-REAL61-008/hybrid_direct_broyden_tr_lm_v9/"
        "corrective_accepted_invalid_v1/adapter.py"
    ),
    "champion_v0_search_retained_candidate": (
        HERE.parents[2]
        / "EXP-REAL61-008/hybrid_direct_broyden_tr_lm_v9/"
        "corrective_accepted_invalid_v1/candidate.py"
    ),
    "champion_v0_search_frozen_candidate": (
        HERE.parents[2]
        / "EXP-REAL61-008/hybrid_direct_broyden_tr_lm_v9/candidate.py"
    ),
    "champion_v0_search_literal_adapter": (
        HERE.parents[2] / "EXP-REAL61-008/dev41_literal_local_screen/adapter.py"
    ),
    "champion_v0_precision_runtime": (
        HERE.parents[2] / "EXP-REAL61-008/ad_inverse_broyden/precision_runtime.py"
    ),
    "champion_v0_restoration_worker": (
        HERE.parents[2]
        / "EXP-REAL61-008/roweq180_hp_restoration_integration_v1/worker.py"
    ),
    "champion_v0_restoration_adapter": (
        HERE.parents[2]
        / "EXP-REAL61-008/roweq180_hp_restoration_integration_v1/adapter.py"
    ),
    "champion_v0_restoration_candidate": (
        HERE.parents[2]
        / "EXP-REAL61-008/hp_failure_restoration_rescue_v6/candidate.py"
    ),
    "champion_v0_hp_schedule_bridge": (
        HERE.parents[2] / "EXP-REAL61-008/hp_precision_schedule_v11/bridge.py"
    ),
    "champion_v1_base_worker": HERE.parents[1] / "champion_v1/worker.py",
    "champion_v1_base_hp_bridge": (
        HERE.parents[1] / "champion_v1/approved_hp_bridge.py"
    ),
    "champion_v2_base_worker": HERE.parents[1] / "champion_v2/worker.py",
    "hp_scheduler_worker": HERE.parent / "hp_lock_scheduler/worker.py",
    "hp_scheduler_adapter": HERE.parent / "hp_lock_scheduler/adapter.py",
    "hp_scheduler_policy": HERE.parent / "hp_lock_scheduler/policy.py",
    "hp_scheduler_deadline_guard": (
        HERE.parent / "hp_lock_scheduler/deadline_guard.py"
    ),
    "hp_scheduler_parent_death_exec": (
        HERE.parent / "hp_lock_scheduler/pdeath_exec.py"
    ),
    "hp_scheduler_root_scoped_subprocess": (
        HERE.parent / "hp_lock_scheduler/root_scoped_subprocess.py"
    ),
    "hp_scheduler_dataset_runner": (
        HERE.parent / "hp_lock_scheduler/run_dataset.py"
    ),
    "base_dataset_runner": (
        ROOT
        / "research/experiments/EXP-OMC-G-PART01-V15-EVAL-001/run_dataset.py"
    ),
    "same_group_subprocess": (
        ROOT / "research/infrastructure/memory_safety/same_group_subprocess.py"
    ),
    "memory_limit_exec": (
        ROOT / "research/infrastructure/memory_safety/_limit_exec.py"
    ),
    "exact_coordinate_fallback_worker": (
        HERE.parent / "exact_coordinate_replay/fallback_worker.py"
    ),
    "exact_coordinate_candidate": (
        HERE.parent / "exact_coordinate_replay/candidate.py"
    ),
    "exact_coordinate_dag_compiler": (
        HERE.parents[2] / "EXP-REAL61-004/qqbar_exact_replay/dag_compile.py"
    ),
    "exact_coordinate_qqbar_worker": (
        HERE.parents[2] / "EXP-REAL61-004/qqbar_exact_replay/qqbar_worker.jl"
    ),
    "zero_dimensional_candidate": (
        HERE.parent / "zero_dimensional_authority/candidate.py"
    ),
    "zero_dimensional_manifest": (
        HERE.parent / "zero_dimensional_authority/IMPLEMENTATION_DIGESTS.json"
    ),
    "zero_dimensional_numeric_authority": (
        HERE.parents[2]
        / "EXP-REAL61-008/hp_target_first_fallback_integration_v1/adapter.py"
    ),
    "poc_closure_manifest": Path(__file__).resolve(),
}

FROZEN_SHARED_SHA256 = {
    "champion_v5_base": (
        "114db602b85ec340d4e602c52e463eb8d74796a7c0f889fe1cf692548c4544f0"
    ),
    "exact_coordinate_candidate": (
        "e0f24e605e7e7211d134ddea66e66adbb89307148a8f03c1afebd4a2c969c66f"
    ),
    "exact_coordinate_fallback_worker": (
        "44d6fa802dc51e7f58e5a72e48b434a62be84275c328bd605f0e9e2f6eb11900"
    ),
    "legacy_refinement_worker": (
        "14a107893f6db1b9ec113c28653a40b3817f274865b0fabc64e2a13702bdc7b3"
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    return os.path.relpath(path.resolve(), ROOT)


def _zero_manifest_members() -> Mapping[str, Path]:
    manifest_path = CANDIDATE_FILES["zero_dimensional_manifest"]
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    members = document.get("files") if isinstance(document, Mapping) else None
    if not isinstance(members, Mapping):
        raise ManifestError("zero-dimensional nested manifest is malformed")
    root = manifest_path.parent.resolve()
    output: dict[str, Path] = {}
    for relative in sorted(members):
        if not isinstance(relative, str):
            raise ManifestError("zero-dimensional manifest path is invalid")
        path = (root / relative).resolve()
        if root not in path.parents:
            raise ManifestError("zero-dimensional manifest path escapes root")
        output[f"zero_manifest_member:{relative}"] = path
    return output


def runtime_paths(arm: str) -> Mapping[str, Path]:
    if arm != ARM_NO_1280:
        raise ManifestError("candidate champion-v5 closure permits no-fresh-1280 only")
    paths = {**BASE.runtime_paths(arm), **CANDIDATE_FILES}
    resolved = {path.resolve() for path in paths.values()}
    for name, path in _zero_manifest_members().items():
        if path.resolve() not in resolved:
            paths[name] = path
            resolved.add(path.resolve())
    missing = {name: str(path) for name, path in paths.items() if not path.is_file()}
    if missing:
        raise ManifestError(f"candidate closure file missing: {missing}")
    drift: dict[str, dict[str, str]] = {}
    for name, expected in FROZEN_SHARED_SHA256.items():
        path = paths.get(name)
        observed = _sha256(path) if path is not None else "MISSING"
        if observed != expected:
            drift[name] = {"expected": expected, "observed": observed}
    if drift:
        raise ManifestError(f"frozen shared closure changed: {drift}")
    resolved_list = [path.resolve() for path in paths.values()]
    if len(resolved_list) != len(set(resolved_list)):
        raise ManifestError("candidate closure contains duplicate paths")
    return paths


def build_manifest(arm: str) -> dict[str, object]:
    base = BASE.build_manifest(arm)
    entries = [
        {
            "name": name,
            "path": _relative(path),
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for name, path in sorted(runtime_paths(arm).items())
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "arm": arm,
        "base_closure_sha256": base["closure_sha256"],
        "files": entries,
        "point_on_circle_semantic_repair_only": True,
        "optional_endpoint_canonicalization_enabled": False,
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return {
        **payload,
        "closure_sha256": hashlib.sha256(canonical).hexdigest(),
        "file_count": len(entries),
        "case_family_truth_or_target_read": False,
    }


def verify_environment(environment: Mapping[str, str]) -> dict[str, object]:
    arm = environment.get(ARM_ENV)
    expected = environment.get(CLOSURE_ENV)
    if arm != ARM_NO_1280:
        raise ManifestError("candidate closure arm is missing or invalid")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ManifestError("candidate closure digest is missing or invalid")
    observed = build_manifest(arm)
    if observed["closure_sha256"] != expected:
        raise ManifestError(
            "candidate closure mismatch: "
            f"expected={expected} observed={observed['closure_sha256']}"
        )
    return observed


__all__ = [
    "ARM_ENV",
    "ARMS",
    "ARM_NO_1280",
    "ARM_WITH_1280",
    "CLOSURE_ENV",
    "ManifestError",
    "SCHEMA_VERSION",
    "build_manifest",
    "runtime_paths",
    "verify_environment",
]
