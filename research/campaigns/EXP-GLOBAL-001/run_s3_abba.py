#!/usr/bin/env python3
"""Resume-safe sequential S3 ABBA driver for development145 only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Mapping, Sequence


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
DEFAULT_RUNNER = HERE / "run_arm.py"
DEFAULT_FROZEN_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
DEFAULT_DATASET = Path(
    "/home/kabatan/work/solver-artifacts/experiment-freeze-20260727/"
    "product-145-20260727-v4/development145.jsonl"
)
DEFAULT_SOLVER_PYTHON = Path("/home/kabatan/work/solver/.venv/bin/python")
MANIFEST_NAME = "S3_ABBA_ORCHESTRATION.json"
FORBIDDEN = re.compile(r"(?:validation|sealed|holdout)", re.IGNORECASE)
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
FIXED = {
    "partition": "development",
    "jobs": 1,
    "total_seconds": 180.0,
    "search_seconds": 146.0,
    "starts": 256,
    "callbacks_per_start": 600,
    "aggregate_callback_cap": 153600,
}


class CampaignError(RuntimeError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_hash(value: object) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def guard_name(value: object, label: str) -> None:
    if FORBIDDEN.search(str(value)):
        raise CampaignError(f"{label} contains a forbidden holdout name")


def resolve_entrypoint(raw: str, manifest: Path, frozen_root: Path) -> Path:
    if raw.startswith("frozen://"):
        return (frozen_root / raw.removeprefix("frozen://")).resolve()
    value = Path(raw).expanduser()
    return (value if value.is_absolute() else manifest.parent / value).resolve()


def freeze_arm(manifest: Path, frozen_root: Path) -> dict[str, object]:
    manifest = manifest.expanduser().resolve()
    guard_name(manifest, "arm manifest path")
    if not manifest.is_file():
        raise CampaignError(f"arm manifest is unavailable: {manifest}")
    payload = manifest.read_bytes()
    document = json.loads(payload)
    fields = {"id", "base_commit", "entrypoint", "mechanism_hash"}
    if not isinstance(document, Mapping) or set(document) != fields:
        raise CampaignError("arm manifest must contain exactly four contract fields")
    if not all(isinstance(document[field], str) for field in fields):
        raise CampaignError("arm contract fields must be strings")
    guard_name(document["id"], "arm id")
    if not HEX40.fullmatch(str(document["base_commit"])):
        raise CampaignError("invalid arm base_commit")
    if not HEX64.fullmatch(str(document["mechanism_hash"])):
        raise CampaignError("invalid arm mechanism_hash")
    entrypoint = resolve_entrypoint(str(document["entrypoint"]), manifest, frozen_root)
    guard_name(entrypoint, "arm entrypoint path")
    if not entrypoint.is_file():
        raise CampaignError(f"arm entrypoint is unavailable: {entrypoint}")
    entrypoint_hash = sha256_file(entrypoint)
    if entrypoint_hash != document["mechanism_hash"]:
        raise CampaignError("arm entrypoint mechanism hash mismatch")
    return {
        "manifest_path": str(manifest),
        "manifest_sha256": sha256_bytes(payload),
        "contract": dict(document),
        "entrypoint": str(entrypoint),
        "entrypoint_sha256": entrypoint_hash,
    }


def check_arm(frozen: Mapping[str, object], frozen_root: Path) -> None:
    current = freeze_arm(Path(str(frozen["manifest_path"])), frozen_root)
    if current != dict(frozen):
        raise CampaignError("arm manifest or entrypoint changed after campaign freeze")


def build_legs(seeds: Sequence[int], raw_root: Path) -> list[dict[str, object]]:
    pattern = (
        ("a1", "control", 1),
        ("b1", "candidate", 1),
        ("b2", "candidate", 2),
        ("a2", "control", 2),
    )
    legs: list[dict[str, object]] = []
    ordinal = 0
    for seed in seeds:
        for code, arm, replicate in pattern:
            ordinal += 1
            leg_id = f"seed-{seed:02d}-{code}-{arm}"
            legs.append(
                {
                    "ordinal": ordinal,
                    "id": leg_id,
                    "seed": seed,
                    "arm": arm,
                    "replicate": replicate,
                    "output": str((raw_root / "legs" / leg_id).resolve()),
                    "status": "pending",
                }
            )
    return legs


def static_leg(leg: Mapping[str, object]) -> dict[str, object]:
    return {
        key: leg[key]
        for key in ("ordinal", "id", "seed", "arm", "replicate", "output")
    }


def expected_plan_fields(
    leg: Mapping[str, object], arm: Mapping[str, object], cpu: int, execute: bool
) -> dict[str, object]:
    return {
        "execute": execute,
        "arm": arm["contract"],
        "entrypoint": arm["entrypoint"],
        "entrypoint_sha256": arm["entrypoint_sha256"],
        "partition": FIXED["partition"],
        "case_count": 145,
        "canonical_formulations_verified": 145,
        "truth_passed_to_worker": False,
        "validation_or_sealed_supported": False,
        "jobs": FIXED["jobs"],
        "cpus": str(cpu),
        "total_seconds": FIXED["total_seconds"],
        "search_seconds": FIXED["search_seconds"],
        "starts": FIXED["starts"],
        "callbacks_per_start": FIXED["callbacks_per_start"],
        "aggregate_callback_cap": FIXED["aggregate_callback_cap"],
        "seed": leg["seed"],
    }


def validate_plan(
    document: object,
    leg: Mapping[str, object],
    arm: Mapping[str, object],
    cpu: int,
    execute: bool,
) -> Mapping[str, object]:
    if not isinstance(document, Mapping):
        raise CampaignError("run_arm emitted a malformed campaign plan")
    for key, expected in expected_plan_fields(leg, arm, cpu, execute).items():
        if document.get(key) != expected:
            raise CampaignError(f"campaign plan mismatch at {key}")
    for key in (
        "development_dataset_sha256",
        "selected_dataset_sha256",
        "archived_input_manifest_sha256",
        "runner_sha256",
    ):
        if not isinstance(document.get(key), str) or not HEX64.fullmatch(document[key]):
            raise CampaignError(f"campaign plan has invalid {key}")
    return document


def bind_dataset_hash(campaign: dict[str, object], plan: Mapping[str, object]) -> None:
    expected_development = campaign["config"]["development_dataset_sha256"]
    if plan.get("development_dataset_sha256") != expected_development:
        raise CampaignError("development dataset changed after campaign freeze")
    selected = plan["selected_dataset_sha256"]
    frozen_selected = campaign.get("selected_dataset_sha256")
    if frozen_selected is None:
        campaign["selected_dataset_sha256"] = selected
    elif frozen_selected != selected:
        raise CampaignError("selected development payload changed between legs")


def validate_result(
    document: object,
    plan: Mapping[str, object],
    leg: Mapping[str, object],
    arm: Mapping[str, object],
    cpu: int,
) -> None:
    if not isinstance(document, Mapping) or document.get("status") != "COMPLETE":
        raise CampaignError("leg RESULT is absent or incomplete")
    rows = document.get("rows")
    result_plan = document.get("plan")
    if not isinstance(rows, list) or len(rows) != 145 or not isinstance(
        result_plan, Mapping
    ):
        raise CampaignError("leg RESULT cardinality or plan is malformed")
    expected = {
        "execute": True,
        "dataset_sha256": plan["selected_dataset_sha256"],
        "case_count": 145,
        "jobs": 1,
        "cpus": [cpu],
        "total_seconds": FIXED["total_seconds"],
        "search_seconds": FIXED["search_seconds"],
        "starts": FIXED["starts"],
        "callbacks_per_start": FIXED["callbacks_per_start"],
        "aggregate_callback_cap": FIXED["aggregate_callback_cap"],
        "seed": leg["seed"],
        "worker": arm["entrypoint"],
        "worker_sha256": arm["entrypoint_sha256"],
        "truth_or_known_target_count_passed_to_solver": False,
        "formulation_content_modified": False,
    }
    for key, value in expected.items():
        if result_plan.get(key) != value:
            raise CampaignError(f"leg RESULT plan mismatch at {key}")


def command_for(
    campaign: Mapping[str, object], leg: Mapping[str, object], execute: bool
) -> list[str]:
    arm = campaign["arms"][leg["arm"]]
    config = campaign["config"]
    command = [
        str(config["launcher_python"]),
        str(campaign["runner"]["path"]),
        "--arm",
        str(arm["manifest_path"]),
        "--partition",
        "development",
        "--dataset",
        str(config["dataset"]),
        "--frozen-root",
        str(config["frozen_root"]),
        "--python",
        str(config["solver_python"]),
        "--output",
        str(leg["output"]),
        "--jobs",
        "1",
        "--cpus",
        str(config["cpu"]),
        "--total-seconds",
        "180",
        "--search-seconds",
        "146",
        "--starts",
        "256",
        "--callbacks-per-start",
        "600",
        "--aggregate-callback-cap",
        "153600",
        "--seed",
        str(leg["seed"]),
    ]
    if execute:
        command.append("--execute")
    return command


def completed_receipt(
    campaign: dict[str, object],
    output: Path,
    leg: Mapping[str, object],
    arm: Mapping[str, object],
    cpu: int,
) -> dict[str, object]:
    plan_path = output / "CAMPAIGN_PLAN.json"
    result_path = output / "RESULT.json"
    if not plan_path.is_file() or not result_path.is_file():
        raise CampaignError("existing leg output is partial; refusing resume")
    plan = validate_plan(load_json(plan_path), leg, arm, cpu, True)
    bind_dataset_hash(campaign, plan)
    validate_result(load_json(result_path), plan, leg, arm, cpu)
    return {
        "status": "completed",
        "campaign_plan_sha256": sha256_file(plan_path),
        "result_sha256": sha256_file(result_path),
        "selected_dataset_sha256": plan["selected_dataset_sha256"],
    }


def run_leg(
    campaign: dict[str, object],
    leg: dict[str, object],
    execute: bool,
) -> None:
    config = campaign["config"]
    frozen_root = Path(str(config["frozen_root"]))
    runner_path = Path(str(campaign["runner"]["path"]))
    if sha256_file(runner_path) != campaign["runner"]["sha256"]:
        raise CampaignError("run_arm.py changed after campaign freeze")
    for frozen_arm in campaign["arms"].values():
        check_arm(frozen_arm, frozen_root)
    arm = campaign["arms"][leg["arm"]]
    output = Path(str(leg["output"]))
    raw_root = Path(str(config["raw_root"]))
    if output.resolve() != output or not is_within(output, raw_root):
        raise CampaignError("leg output escaped the frozen raw root")
    if execute and output.exists():
        receipt = completed_receipt(campaign, output, leg, arm, int(config["cpu"]))
        previous = {key: leg.get(key) for key in receipt}
        if leg.get("status") == "completed" and previous != receipt:
            raise CampaignError("completed leg receipt changed; refusing resume")
        leg.update(receipt)
        leg["resume_verified"] = True
        return
    if execute and leg.get("status") == "completed":
        raise CampaignError("completed leg output disappeared")
    if not execute and output.exists():
        raise CampaignError("dry-plan leg output path already exists")

    completed = subprocess.run(
        command_for(campaign, leg, execute),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise CampaignError(
            f"run_arm failed for {leg['id']} with exit {completed.returncode}: "
            + completed.stderr[-500:]
        )
    if execute:
        receipt = completed_receipt(campaign, output, leg, arm, int(config["cpu"]))
        leg.update(receipt)
        leg["resume_verified"] = False
    else:
        try:
            plan = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise CampaignError("run_arm dry output is not JSON") from error
        validate_plan(plan, leg, arm, int(config["cpu"]), False)
        bind_dataset_hash(campaign, plan)
        leg.update(
            {
                "status": "dry_planned",
                "dry_plan_sha256": canonical_hash(plan),
                "selected_dataset_sha256": plan["selected_dataset_sha256"],
            }
        )


def prepare_campaign(arguments: argparse.Namespace) -> tuple[Path, dict[str, object]]:
    raw_root = arguments.raw_root.expanduser().resolve()
    runner = arguments.runner.expanduser().resolve()
    frozen_root = arguments.frozen_root.expanduser().resolve()
    dataset = arguments.dataset.expanduser().resolve()
    # Keep a virtual-environment launcher path intact.  Resolving the symlink
    # to its base interpreter drops the venv's site-packages and makes the
    # frozen NumPy/SciPy version probe fail before any leg can start.
    solver_python = arguments.python.expanduser().absolute()
    launcher_python = arguments.launcher_python.expanduser().resolve()
    for path, label in (
        (raw_root, "raw root"),
        (runner, "runner path"),
        (dataset, "dataset path"),
        (arguments.control_arm, "control arm path"),
        (arguments.candidate_arm, "candidate arm path"),
    ):
        guard_name(path, label)
    if is_within(raw_root, REPOSITORY):
        raise CampaignError("raw root must be outside the repository")
    if not runner.is_file():
        raise CampaignError(f"run_arm.py is unavailable: {runner}")
    if not dataset.is_file():
        raise CampaignError(f"development dataset is unavailable: {dataset}")
    if not frozen_root.is_dir():
        raise CampaignError(f"frozen root is unavailable: {frozen_root}")
    for executable in (solver_python, launcher_python):
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise CampaignError(f"Python executable is unavailable: {executable}")
    seeds = list(arguments.seeds)
    if not seeds or len(set(seeds)) != len(seeds) or any(seed < 0 for seed in seeds):
        raise CampaignError("seeds must be a nonempty list of unique nonnegative integers")
    if arguments.cpu < 0 or arguments.cpu > 15:
        raise CampaignError("explicit CPU must be in [0,15]")
    arms = {
        "control": freeze_arm(arguments.control_arm, frozen_root),
        "candidate": freeze_arm(arguments.candidate_arm, frozen_root),
    }
    config = {
        **FIXED,
        "cpu": arguments.cpu,
        "seeds": seeds,
        "raw_root": str(raw_root),
        "dataset": str(dataset),
        "development_dataset_sha256": sha256_file(dataset),
        "frozen_root": str(frozen_root),
        "solver_python": str(solver_python),
        "launcher_python": str(launcher_python),
        "truth_or_scores_passed_to_workers": False,
    }
    frozen = {
        "schema_version": "geotarget.exp-global-001-s3-abba/v1",
        "runner": {"path": str(runner), "sha256": sha256_file(runner)},
        "arms": arms,
        "config": config,
    }
    fingerprint = canonical_hash(frozen)
    planned_legs = build_legs(seeds, raw_root)
    manifest_path = raw_root / MANIFEST_NAME
    if manifest_path.exists():
        existing = load_json(manifest_path)
        if not isinstance(existing, Mapping):
            raise CampaignError("existing orchestration manifest is malformed")
        if existing.get("campaign_fingerprint") != fingerprint:
            raise CampaignError("existing orchestration manifest config/hash mismatch")
        if any(existing.get(key) != frozen[key] for key in frozen):
            raise CampaignError("existing orchestration frozen contract mismatch")
        existing_legs = existing.get("legs")
        if not isinstance(existing_legs, list) or [
            static_leg(leg) for leg in existing_legs
        ] != [static_leg(leg) for leg in planned_legs]:
            raise CampaignError("existing orchestration leg plan mismatch")
        if existing.get("status") == "failed":
            raise CampaignError("failed campaign requires a new raw root")
        campaign = dict(existing)
    else:
        if raw_root.exists() and any(raw_root.iterdir()):
            raise CampaignError("raw root is nonempty and has no orchestration manifest")
        raw_root.mkdir(parents=True, exist_ok=True)
        campaign = {
            **frozen,
            "campaign_fingerprint": fingerprint,
            "truth_or_scores_read_by_orchestrator": False,
            "status": "planned",
            "legs": planned_legs,
        }
        atomic_json(manifest_path, campaign)
    return manifest_path, campaign


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--control-arm", type=Path, required=True)
    value.add_argument("--candidate-arm", type=Path, required=True)
    value.add_argument("--raw-root", type=Path, required=True)
    value.add_argument("--cpu", type=int, required=True)
    value.add_argument("--seeds", type=int, nargs="+", default=list(range(5)))
    value.add_argument("--runner", type=Path, default=DEFAULT_RUNNER)
    value.add_argument("--frozen-root", type=Path, default=DEFAULT_FROZEN_ROOT)
    value.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    value.add_argument("--python", type=Path, default=DEFAULT_SOLVER_PYTHON)
    value.add_argument("--launcher-python", type=Path, default=Path(sys.executable))
    value.add_argument("--execute", action="store_true")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        manifest_path, campaign = prepare_campaign(arguments)
        campaign["status"] = "running" if arguments.execute else "dry_planning"
        atomic_json(manifest_path, campaign)
        for leg in campaign["legs"]:
            try:
                run_leg(campaign, leg, arguments.execute)
            except (CampaignError, OSError, json.JSONDecodeError) as error:
                leg["status"] = "failed"
                leg["failure"] = str(error)
                campaign["status"] = "failed"
                atomic_json(manifest_path, campaign)
                raise
            atomic_json(manifest_path, campaign)
        campaign["status"] = "complete" if arguments.execute else "dry_planned"
        atomic_json(manifest_path, campaign)
    except (CampaignError, OSError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
