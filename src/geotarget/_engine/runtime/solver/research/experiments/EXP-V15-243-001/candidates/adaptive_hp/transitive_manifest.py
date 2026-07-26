"""Deterministic digest closure for the adaptive HP execution implementation.

The closure covers the candidate bridge/worker, semantic-parity implementation,
every repository HP backend selected by the portfolio and its authority chain,
plus the Python source trees that provide the solver semantics loaded by those
research modules.  It intentionally excludes case data, truth, results, caches,
compiled bytecode, and environment-dependent site-packages.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Mapping


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
GEOSOLVER_ROOT = ROOT.parent / "geosolver"

ARM_WITH_1280 = "ADAPTIVE_WITH_FRESH_1280"
ARM_NO_1280 = "ADAPTIVE_WITHOUT_FRESH_1280"
ARMS = (ARM_WITH_1280, ARM_NO_1280)

CLOSURE_ENV = "GEOTARGET_ADAPTIVE_HP_TRANSITIVE_CLOSURE_SHA256"
ARM_ENV = "GEOTARGET_ADAPTIVE_HP_TRANSITIVE_ARM"
SCHEMA_VERSION = "geotarget.exp-v15-243-001.adaptive-hp-transitive-manifest/v1"


class ManifestError(RuntimeError):
    """A required implementation file or execution pin is unavailable."""


_COMMON_FILES = {
    "candidate_portfolio_adapter": HERE / "adapter.py",
    "candidate_champion_adapter": HERE / "champion_adapter.py",
    "candidate_composition_worker": HERE / "champion_composition_worker.py",
    "candidate_bridge_contract": HERE / "bridge_contract.py",
    "candidate_transitive_manifest": Path(__file__).resolve(),
    "champion_semantic_compatibility": (
        ROOT
        / "research/experiments/EXP-V15-243-001/champion_v0/"
        "hp_semantic_compat.py"
    ),
    "semantic_parity_implementation": (
        ROOT
        / "research/experiments/EXP-V15-243-001/candidates/"
        "hp_semantic_parity/semantic_parity.py"
    ),
    "frozen_endpoint_bridge": (
        ROOT
        / "research/experiments/EXP-REAL61-008/"
        "hp_endpoint_bridge_v10/run_one_endpoint.py"
    ),
    "guarded_subprocess": (
        ROOT / "research/infrastructure/memory_safety/safe_subprocess.py"
    ),
    "thin_runner": (
        ROOT
        / "research/experiments/EXP-REAL61-008/"
        "hp_precision_schedule_v11/run_candidate_one.py"
    ),
    "thin_candidate": (
        ROOT
        / "research/experiments/EXP-REAL61-008/"
        "hp_precision_schedule_v11/candidate.py"
    ),
    "undamped_first_candidate": (
        ROOT
        / "research/experiments/EXP-REAL61-008/"
        "hp_undamped_first_candidate/candidate.py"
    ),
    "authority_adapter": (
        ROOT
        / "research/experiments/EXP-REAL61-008/"
        "dev41_target_hp_adapter/adapter.py"
    ),
    "target_stability_candidate": (
        ROOT
        / "research/experiments/EXP-REAL61-006/"
        "adaptive_hp_escalation/target_stable_candidate.py"
    ),
    "fresh_1280_candidate": (
        ROOT
        / "research/experiments/EXP-REAL61-006/"
        "adaptive_hp_escalation/candidate.py"
    ),
    "target_stability_worker": (
        ROOT
        / "research/experiments/EXP-REAL61-006/"
        "adaptive_hp_escalation/target_stable_worker.py"
    ),
    "adaptive_hp_common_worker": (
        ROOT
        / "research/experiments/EXP-REAL61-006/"
        "adaptive_hp_escalation/worker.py"
    ),
    "semismooth_hp_candidate": (
        ROOT
        / "research/experiments/EXP-REAL61-005/"
        "nearroot_semismooth_hp/candidate.py"
    ),
    "rrqr_refiner_candidate": (
        ROOT
        / "research/experiments/EXP-REAL61-004/"
        "hp_independent_rrqr_refiner_v3/candidate.py"
    ),
    "refinement_bridge_worker": (
        ROOT
        / "research/experiments/EXP-REAL61-004/"
        "refinement_bridge/worker.py"
    ),
    "refinement_bridge_helpers": (
        ROOT
        / "research/experiments/EXP-REAL61-004/"
        "refinement_bridge/bridge.py"
    ),
    "legacy_refinement_worker": (
        ROOT
        / "research/experiments/EXP-REAL61-001/"
        "refine_proposals_worker.py"
    ),
    "legacy_runtime": (
        ROOT
        / "research/experiments/EXP-REAL61-001/"
        "legacy61_runtime.py"
    ),
    "target_numerical_authority": (
        ROOT
        / "research/experiments/EXP-REAL61-004/"
        "target_only_numerical_authority_v3/adapter.py"
    ),
    "numerical_success_policy": (
        ROOT
        / "research/experiments/EXP-REAL61-004/"
        "NUMERICAL_SUCCESS_POLICY_V3.json"
    ),
    "numerical_semantics": (
        ROOT
        / "research/experiments/EXP-REAL61-004/"
        "minimal_numerical_180_worker/numerical_semantics.py"
    ),
    "owned_pslq": (
        ROOT
        / "research/experiments/EXP-REAL61-003/"
        "owned_pslq/owned_pslq.py"
    ),
    "broyden_runner": (
        ROOT
        / "research/experiments/EXP-REAL61-008/"
        "hp_combined_broyden_publicgate_v17/run_candidate_one.py"
    ),
    "broyden_candidate": (
        ROOT
        / "research/experiments/EXP-REAL61-008/"
        "hp_combined_broyden_publicgate_v17/candidate.py"
    ),
    "public_gate_runner": (
        ROOT
        / "research/experiments/EXP-REAL61-008/"
        "public_gate_progressive_hp_v16/run_candidate_one.py"
    ),
    "public_gate_candidate": (
        ROOT
        / "research/experiments/EXP-REAL61-008/"
        "public_gate_progressive_hp_v16/candidate.py"
    ),
    "quasi_newton_integration": (
        ROOT
        / "research/experiments/EXP-REAL61-008/"
        "hp_quasi_newton_v16/integrated_candidate.py"
    ),
    "quasi_newton_kernel": (
        ROOT
        / "research/experiments/EXP-REAL61-008/"
        "hp_quasi_newton_v16/candidate.py"
    ),
}

_ARM_FILES = {
    ARM_WITH_1280: {
        "candidate_bridge_entry": HERE / "champion_bridge.py",
    },
    ARM_NO_1280: {
        "candidate_bridge_entry_no_1280": HERE / "champion_bridge_no_1280.py",
        "candidate_composition_worker_no_1280": (
            HERE / "champion_composition_worker_no_1280.py"
        ),
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    return os.path.relpath(path.resolve(), ROOT)


def _source_tree_files() -> dict[str, Path]:
    roots = {
        "geosolver_source": GEOSOLVER_ROOT / "src/geosolver",
        "solver_python_source": ROOT / "python/src",
    }
    files: dict[str, Path] = {}
    for prefix, source_root in roots.items():
        if not source_root.is_dir():
            raise ManifestError(f"required source tree is unavailable: {source_root}")
        for path in sorted(source_root.rglob("*.py")):
            relative = path.relative_to(source_root).as_posix()
            files[f"{prefix}:{relative}"] = path
    return files


def runtime_paths(arm: str) -> Mapping[str, Path]:
    if arm not in ARMS:
        raise ManifestError(f"unknown adaptive HP arm: {arm}")
    paths = {**_COMMON_FILES, **_ARM_FILES[arm], **_source_tree_files()}
    missing = {
        name: str(path)
        for name, path in paths.items()
        if not path.is_file()
    }
    if missing:
        raise ManifestError(f"transitive implementation file missing: {missing}")
    resolved = [path.resolve() for path in paths.values()]
    if len(resolved) != len(set(resolved)):
        duplicates = sorted(
            str(path)
            for path in set(resolved)
            if resolved.count(path) > 1
        )
        raise ManifestError(f"duplicate transitive implementation paths: {duplicates}")
    return paths


def build_manifest(arm: str) -> dict[str, object]:
    entries = [
        {
            "name": name,
            "path": _relative(path),
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for name, path in sorted(runtime_paths(arm).items())
    ]
    closure_payload = {
        "schema_version": SCHEMA_VERSION,
        "arm": arm,
        "files": entries,
    }
    canonical = json.dumps(
        closure_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return {
        **closure_payload,
        "closure_sha256": hashlib.sha256(canonical).hexdigest(),
        "file_count": len(entries),
        "case_family_truth_or_target_read": False,
    }


def verify_environment(
    environment: Mapping[str, str],
) -> dict[str, object]:
    arm = environment.get(ARM_ENV)
    expected = environment.get(CLOSURE_ENV)
    if arm not in ARMS:
        raise ManifestError("transitive implementation arm is missing or invalid")
    if (
        not isinstance(expected, str)
        or len(expected) != 64
        or any(character not in "0123456789abcdef" for character in expected)
    ):
        raise ManifestError("transitive implementation closure is missing or invalid")
    observed = build_manifest(arm)
    if observed["closure_sha256"] != expected:
        raise ManifestError(
            "transitive implementation closure mismatch: "
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
