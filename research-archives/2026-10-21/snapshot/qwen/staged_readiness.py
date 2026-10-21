"""CPU-only transfer of existing GPU calibration to the revised study driver.

The numerical learner/actor/reward code must remain byte-identical. Changes to
ordering/evaluation orchestration require fresh CPU integration-test evidence.
The old ledger and gate remain intact; all old charges enter the new ledger.
"""

from __future__ import annotations

import argparse
import importlib.metadata
from pathlib import Path

from .common import file_hash, now, read_json, write_json
from .experiment_budget import remaining
from .staged_study import (
    DEFAULT_CONFIG,
    frozen_json,
    plan_cost,
    validate_evaluation_inputs,
    validate_evaluation_protocol,
)

DRIVER_CHANGES = {"qwen/grpo_run.py", "qwen/grpo_evaluate.py"}
REQUIRED_TESTED_PATHS = DRIVER_CHANGES | {
    "qwen/staged_study.py",
    "qwen/staged_readiness.py",
    "tests/test_staged_study.py",
    "tests/test_staged_inputs.py",
    "tests/test_staged_guards.py",
}


def validate_test_evidence(tests):
    if (
        tests.get("exit_code") != 0
        or not tests.get("integration_tests_passed")
        or not tests.get("lint_passed")
    ):
        raise ValueError("Fresh orchestration integration tests and lint are required")
    hashes = tests.get("source_sha256", {})
    if not isinstance(hashes, dict) or not hashes.keys() >= REQUIRED_TESTED_PATHS:
        raise ValueError("Test evidence does not cover the changed drivers and staged tests")
    for path, expected in hashes.items():
        if file_hash(path) != expected:
            raise ValueError(f"Source changed after tests: {path}")


def inherit_budget(old_path, new_path, hours):
    old = read_json(old_path)
    remaining(old)
    prefix = old["jobs"]
    if any(j["category"] != "preparation" for j in prefix):
        raise ValueError("Legacy study already performed research GPU work; do not fork accounting")
    provenance = {
        "path": str(old_path),
        "sha256": file_hash(old_path),
        "old_limit_seconds": old["limit_seconds"],
        "reason": "User clarified24–40h is a guideline; preserve all charges with48h fuse.",
    }
    if Path(new_path).exists():
        current = read_json(new_path)
        if (
            current["migration"] != provenance
            or current["jobs"][: len(prefix)] != prefix
            or current["limit_seconds"] != hours * 3600
        ):
            raise ValueError("Imported charges or operational limit changed")
        remaining(current)
        return current
    new = {**old, "created_utc": now(), "limit_seconds": hours * 3600, "migration": provenance}
    write_json(new_path, new)
    return new


def build(config_path, tests_path):
    config = read_json(config_path)
    if Path(config_path).resolve() != Path(config["config_path"]).resolve():
        raise ValueError("Readiness config path differs from the frozen configuration target")
    validate_evaluation_protocol(config)
    validate_evaluation_inputs(config)
    legacy = config["calibration_gate"]
    old = read_json(legacy)
    if not old["technical_pass"]:
        raise ValueError("GPU calibration did not pass")
    changes = []
    for path, expected in old["source_sha256"].items():
        current = file_hash(path)
        if current != expected:
            if path not in DRIVER_CHANGES:
                raise ValueError(f"GPU-calibrated code changed outside reviewed drivers: {path}")
            changes.append({"path": path, "calibrated_sha256": expected, "current_sha256": current})
    for path, expected in old["evidence_sha256"].items():
        if file_hash(path) != expected:
            raise ValueError(f"Original calibration evidence changed: {path}")
    tests = read_json(tests_path)
    validate_test_evidence(tests)
    old_manifest = read_json(config["calibration_environment_manifest"])
    versions = {}
    for name in ("torch", "transformers", "peft", "vllm"):
        versions[name] = importlib.metadata.version(name)
        if versions[name] != old_manifest["versions"][name]:
            raise ValueError(f"Calibrated GPU environment changed: {name}")
    budget = inherit_budget(
        config["previous_budget_ledger"], config["budget_ledger"], config["wall_hours"]
    )
    source_paths = sorted(str(p) for p in Path("qwen").glob("*.py"))
    source_paths += ["qwen/models.json", str(config_path), *config["protocol_files"]]
    source_paths += list(config["evaluation_suites"].values()) + [config["data"]]
    cost = plan_cost(config, sum(j["charged_seconds"] for j in budget["jobs"]) / 3600)
    if config["evaluation_reserve_hours"] < cost["final_evaluation_cap_hours"]:
        raise ValueError("Final evaluation reserve is too small")
    evidence_paths = [
        legacy,
        tests_path,
        config["previous_budget_ledger"],
        config["calibration_environment_manifest"],
        tests["log_path"],
        tests["lint_log_path"],
    ]
    evidence_paths += sorted(p for p in REQUIRED_TESTED_PATHS if p.startswith("tests/"))
    if not tests.get("lint_passed"):
        raise ValueError("Changed orchestration files failed lint")
    gate = {
        "technical_pass": True,
        "route": old["route"],
        "validated_lr": old["validated_lr"],
        "config_sha256": file_hash(config_path),
        "budget_created_utc": budget["created_utc"],
        "inherited_jobs": old["preparation_jobs"],
        "cost": cost,
        "source_sha256": {p: file_hash(p) for p in source_paths},
        "evidence_sha256": {str(p): file_hash(p) for p in evidence_paths},
        "legacy_gpu_calibration_sha256": file_hash(legacy),
        "reviewed_driver_changes": changes,
        "gpu_core_unchanged": True,
        "versions": versions,
        "scope": "Existing real GPU update/reload/capacity evidence reused because numerical "
        "core is unchanged. Revised scheduling, evaluation and resume verified on CPU. "
        "No new GPU experiment or V/G reward condition has run.",
    }
    frozen_json(config["readiness_gate"], gate)
    return gate


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--tests", default="qwen/.runtime/exp03_staged/preparation/tests.json")
    args = ap.parse_args()
    gate = build(args.config, args.tests)
    print({"technical_pass": gate["technical_pass"], "cost": gate["cost"]})


if __name__ == "__main__":
    main()
