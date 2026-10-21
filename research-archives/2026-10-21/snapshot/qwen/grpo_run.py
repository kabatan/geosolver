"""Resumable staged single-GPU GRPO, with immutable inputs and a wall-time cap.

Generation and training use separate processes. No hidden gradient-accumulation
division, adapter merge/unmerge on the learner, or implicit resume by config ID.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import os
import random
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from .answer_check import PARSER_VERSION, parse_numeric
from .common import digest, file_hash, now, write_json
from .grpo_stage import row_identity
from .models import locked_models


def order_training_rows(rows, config):
    """Return a deterministic order, optionally covering every configuration first."""
    rows = list(rows)
    rng = random.Random(config["seed"])
    order = config.get("training_order", "shuffle")
    if order == "shuffle":
        rng.shuffle(rows)
        return rows
    if order != "representatives_first":
        raise ValueError(f"Unknown training_order: {order}")
    representatives = [r for r in rows if r.get("variant", "v0") == "v0"]
    identities = {r["id"] for r in rows}
    if len(representatives) != len(identities) or {r["id"] for r in representatives} != identities:
        raise ValueError("representatives_first requires exactly one v0 row per configuration")
    remaining = [r for r in rows if r.get("variant", "v0") != "v0"]
    rng.shuffle(representatives)
    rng.shuffle(remaining)
    return representatives + remaining


def evaluation_source_paths(config):
    """Collect every declared evaluation source for the immutable run snapshot."""
    suites = config.get("evaluation_suites", {})
    if not isinstance(suites, dict) or any(
        not isinstance(suite, str) or not isinstance(path, str) or not path
        for suite, path in suites.items()
    ):
        raise ValueError("evaluation_suites must map suite names to source paths")
    paths = list(
        dict.fromkeys(str(Path(p)) for p in [*config.get("evaluation_files", []), *suites.values()])
    )
    for name in paths:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Frozen evaluation paths must be relative to the repository")
    return paths


def prepare(config, root):
    if (
        config.get("route") == "fp16_native"
        and not config.get("technical_calibration")
        and (not config.get("budget_ledger") or config.get("evaluation_reserve_hours", 0) <= 0)
    ):
        raise ValueError("The fast study requires the shared budget and evaluation reserve")
    data = Path(config["data"])
    rows = [json.loads(line) for line in data.read_text().splitlines() if line.strip()]
    if config.get("ids"):
        rows = [r for r in rows if r["id"] in config["ids"] and r.get("variant", "v0") == "v0"]
    if not rows or len({digest(row_identity(r)) for r in rows}) != len(rows):
        raise ValueError("Empty or duplicate problem identities")
    for row in rows:
        parse_numeric(row["answer_exact"])
        if row.get("split", "train") != "train":
            raise ValueError("An evaluation row was supplied to training")
    if config["samples"] < 2 or config["prompts_per_round"] < 1:
        raise ValueError("GRPO needs at least two completions per problem")
    if not 0 < config["max_completion"] <= 32512 or not config["lr"] > 0:
        raise ValueError("Invalid completion cap or learning rate")
    if config["kv_cache_dtype"] != "auto":
        raise ValueError("Only native-precision KV is allowed in the validated routes")
    rows = order_training_rows(rows, config)
    source = {str(p): file_hash(p) for p in sorted(Path("qwen").glob("*.py"))}
    evaluation_sources = {name: file_hash(name) for name in evaluation_source_paths(config)}
    if "evaluation_stages" in config:
        from .grpo_evaluate import resolve_evaluation_config

        stages = config["evaluation_stages"]
        if not isinstance(stages, dict) or not stages:
            raise ValueError("evaluation_stages must declare at least one stage")
        for stage, suites in stages.items():
            if not isinstance(stage, str) or not isinstance(suites, dict) or not suites:
                raise ValueError("Each evaluation stage must declare at least one suite")
            for suite in suites:
                protocol = resolve_evaluation_config(config, suite, stage_name=stage)
                if protocol["data"] not in evaluation_sources:
                    raise ValueError(
                        "Evaluation stage source must be included in the frozen inputs"
                    )
    manifest = {
        "config": config,
        "data_sha256": file_hash(data),
        "source_sha256": source,
        "evaluation_sha256": evaluation_sources,
        "model": locked_models(verify_weights=True)["qwen3_4b"],
        "parser_version": PARSER_VERSION,
        "versions": {
            distribution.metadata["Name"]: distribution.version
            for distribution in importlib.metadata.distributions()
            if distribution.metadata["Name"]
        },
    }
    root.mkdir(parents=True, exist_ok=True)
    path = root / "manifest.json"
    if path.exists():
        if json.loads(path.read_text()) != manifest:
            raise ValueError("Resume refused: config, data, code, model, or environment changed")
        frozen_rows = [
            json.loads(line)
            for line in (root / "input.jsonl").read_text().splitlines()
            if line.strip()
        ]
        if frozen_rows != rows:
            raise ValueError("Resume refused: frozen training inputs changed")
    else:
        write_json(path, manifest)
        (root / "input.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        )
        for name in [*source, *evaluation_sources, "qwen/models.json", str(data)]:
            target = root / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(name, target)
    groups = [
        rows[i : i + config["prompts_per_round"]]
        for i in range(0, len(rows), config["prompts_per_round"])
    ]
    return groups


def verify_checkpoint(directory):
    """Verify weights on every resume, and optimizer bytes after first commit."""
    directory = Path(directory)
    metrics = json.loads((directory / "COMPLETE.json").read_text())
    adapter = directory / "adapter/adapter_model.safetensors"
    optimizer = directory / "optimizer.pt"
    if file_hash(adapter) != metrics["adapter_sha256"] or not optimizer.is_file():
        raise ValueError("Incomplete or altered adapter/optimizer checkpoint")
    for path in directory.glob("detail-*.json"):
        detail = json.loads(path.read_text())
        if metrics.get("route") == "fp16_native":
            correction = detail.get("sampling_correction")
            if (
                not correction
                or not math.isfinite(correction["relative_ess"])
                or correction["relative_ess"] < 0.90
                or correction["clipped_fraction"] > 0.01
            ):
                raise ValueError("Unacceptable sampling correction in checkpoint")
            if not (directory / "scaler.json").exists():
                raise ValueError("Missing FP16 gradient scaler state")
        else:
            error = detail["engine_max_abs_error"]
            if not math.isfinite(error) or error > 1e-3:
                raise ValueError("Rollout/learner logprob mismatch; stop before the next round")
    hashes = {
        str(p.relative_to(directory)): file_hash(p)
        for p in sorted(directory.rglob("*"))
        if p.is_file() and p.name != "integrity.json"
    }
    integrity = directory / "integrity.json"
    if integrity.exists():
        if json.loads(integrity.read_text()) != hashes:
            raise ValueError("Checkpoint contents changed after commit")
    else:
        write_json(integrity, hashes)
    return str(directory / "adapter"), str(optimizer)


def run_worker(command, log, timeout):
    if timeout < 1:
        raise TimeoutError("Experiment wall-time budget exhausted")
    with Path(log).open("a") as stream:
        process = subprocess.Popen(
            command, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True
        )
        try:
            code = process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise
    if code:
        raise RuntimeError(f"Worker exited {code}; inspect {log}")


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("--config", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument(
        "--through-round",
        type=int,
        help="Run only the first N rounds; resume with the same frozen config",
    )
    args = ap.parse_args()
    config = json.loads(Path(args.config).read_text())
    through = args.through_round if args.through_round is not None else config["rounds"]
    if not 1 <= through <= config["rounds"]:
        raise ValueError("through-round is outside the fixed experiment horizon")
    root = Path(args.output).resolve()
    groups = prepare(config, root)
    if args.dry:
        print(
            json.dumps(
                {
                    "manifest": str(root / "manifest.json"),
                    "rounds_per_epoch": len(groups),
                    "max_rounds": config["rounds"],
                    "data_rows": sum(map(len, groups)),
                }
            )
        )
        return
    if not config.get("technical_calibration"):
        gate_path = Path(config["readiness_gate"])
        if not gate_path.exists():
            raise ValueError("Long experiment blocked: no completed calibration readiness record")
        gate = json.loads(gate_path.read_text())
        if not gate.get("technical_pass"):
            raise ValueError("Long experiment blocked: technical calibration has not passed")
        for path, expected in gate.get("source_sha256", {}).items():
            if file_hash(path) != expected:
                raise ValueError(f"Validated source changed: {path}")
        if gate.get("route", "fp32") != config.get("route", "fp32"):
            raise ValueError("Calibration route differs from requested training route")
    # Budget is cumulative across restarts. Completed rounds and failed worker
    # attempts remain in the journal; no silent reset of the time allowance.
    journal_path = root / "attempts.json"
    journal = json.loads(journal_path.read_text()) if journal_path.exists() else []
    if any(r.get("ended_utc") is None for r in journal):
        raise ValueError(
            "An unfinished attempt exists; inspect its process/logs before reconciling the journal"
        )
    used = sum(r["seconds"] for r in journal)
    remaining = config["wall_hours"] * 3600 - used
    started = time.monotonic()
    attempt = {
        "started_utc": now(),
        "ended_utc": None,
        "seconds": 0,
        "status": "running",
        "pid": os.getpid(),
    }
    journal.append(attempt)
    write_json(journal_path, journal)
    adapter = ""
    optimizer = ""

    def worker(command, log, timeout):
        if config.get("budget_ledger"):
            from .experiment_budget import run_budgeted

            run_budgeted(
                command,
                log,
                config["budget_ledger"],
                "training",
                timeout,
                reserve_seconds=config["evaluation_reserve_hours"] * 3600,
            )
        else:
            run_worker(command, log, timeout)

    try:
        for round_index in range(through):
            directory = root / f"round-{round_index:03}"
            directory.mkdir(exist_ok=True)
            complete = directory / "update/COMPLETE.json"
            if complete.exists():
                adapter, optimizer = verify_checkpoint(directory / "update")
                continue
            if (directory / "SKIPPED.json").exists():
                continue
            jobs = directory / "jobs.json"
            if not jobs.exists():
                write_json(jobs, groups[round_index % len(groups)])
            seed = config["seed"] + round_index
            command = [
                sys.executable,
                "-m",
                "qwen.grpo_stage",
                "generate",
                "--route",
                config.get("route", "fp32"),
                "--jobs",
                str(jobs),
                "--output",
                str(directory / "generation"),
                "--seed",
                str(seed),
                "--kv",
                config["kv_cache_dtype"],
                "--samples",
                str(config["samples"]),
                "--max-seqs",
                str(config["max_seqs"]),
                "--max-completion",
                str(config["max_completion"]),
            ]
            if adapter:
                command.extend(["--adapter", adapter])
            worker(command, directory / "generate.log", remaining - (time.monotonic() - started))
            rollouts = directory / "generation/rollouts.json"
            rows = json.loads(rollouts.read_text())
            if not any(r["advantage"] and r["valid_tokens"] for r in rows):
                write_json(
                    directory / "SKIPPED.json",
                    {"reason": "no valid nonzero advantage", "optimizer_step": False},
                )
                continue
            command = [
                sys.executable,
                "-m",
                "qwen.grpo_stage",
                "update",
                "--route",
                config.get("route", "fp32"),
                "--rollouts",
                str(rollouts),
                "--output",
                str(directory / "update"),
                "--seed",
                str(seed),
                "--lr",
                str(config["lr"]),
            ]
            if adapter:
                command.extend(["--adapter", adapter, "--optimizer", optimizer])
            if config.get("measure_after", False):
                command.append("--measure-after")
            worker(command, directory / "update.log", remaining - (time.monotonic() - started))
            adapter, optimizer = verify_checkpoint(directory / "update")
            print(json.dumps({"round": round_index, "complete": str(complete)}), flush=True)
        attempt["status"] = "complete"
        write_json(
            root / ("COMPLETE.json" if through == config["rounds"] else "SEGMENT.json"),
            {
                "adapter": adapter,
                "rounds_completed": through,
                "rounds_planned": config["rounds"],
                "utc": now(),
            },
        )
    except BaseException as exc:
        attempt["status"] = "failed"
        attempt["error"] = repr(exc)
        attempt["budget_stop"] = isinstance(exc, TimeoutError | subprocess.TimeoutExpired)
        raise
    finally:
        attempt["seconds"] = time.monotonic() - started
        attempt["ended_utc"] = now()
        write_json(journal_path, journal)


if __name__ == "__main__":
    main()
