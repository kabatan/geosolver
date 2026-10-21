"""Prepare or run the frozen study within one preparation/train/evaluation budget.

The default is preparation only. --run explicitly starts GPU work. All stopping
rules are based on cost and usable reward signal, never proof/dev performance.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .common import file_hash, now, write_json
from .experiment_budget import remaining
from .grpo_compare import blind, numeric, paired, read_rows
from .grpo_run import prepare, verify_checkpoint


def validate_config(config, gate, budget):
    expected = {
        "route": "fp16_native",
        "prompts_per_round": 4,
        "samples": 4,
        "rounds": 37,
        "max_seqs": 4,
        "max_completion": 32512,
        "kv_cache_dtype": "auto",
        "lr": gate["validated_lr"],
        "evaluation_samples": {"numeric": 2, "proof": 4},
    }
    if any(config.get(k) != v for k, v in expected.items()):
        raise ValueError("Study settings differ from the validated cost/protocol contract")
    if config.get("technical_calibration") or not gate.get("technical_pass"):
        raise ValueError("Completed technical calibration is required")
    if gate.get("route") != config["route"]:
        raise ValueError("Readiness precision route differs")
    if budget["limit_seconds"] != 40 * 3600 or budget["preparation_limit_seconds"] != 2 * 3600:
        raise ValueError("Budget must include preparation within the fixed 40-hour limit")
    if budget["created_utc"] != gate["budget_created_utc"]:
        raise ValueError("Budget ledger was replaced")
    prefix = gate["preparation_jobs"]
    if budget["jobs"][: len(prefix)] != prefix:
        raise ValueError("Preparation charges changed or disappeared")
    remaining(budget)
    if config["evaluation_reserve_hours"] * 3600 < gate["cost"]["post_evaluation_reserve_seconds"]:
        raise ValueError("Post-evaluation reserve is below the validated estimate")
    if not gate["cost"]["fits_40_hours"]:
        raise ValueError("Measured route does not fit the cost ceiling")
    for path, expected_hash in gate["source_sha256"].items():
        if file_hash(path) != expected_hash:
            raise ValueError(f"Validated source changed: {path}")


def progress(training):
    rounds, adapter, generated, tokens, mixed, seconds_update, active_tokens = (
        0,
        "",
        0,
        0,
        0,
        0.0,
        0,
    )
    generation_seconds = 0.0
    for directory in sorted(training.glob("round-???")):
        metrics = directory / "generation/generation_metrics.json"
        if metrics.exists():
            g = json.loads(metrics.read_text())
            generated += len(json.loads((directory / "generation/rollouts.json").read_text()))
            tokens += g["output_tokens"]
            generation_seconds += g["generation_seconds"]
            mixed += g["mixed_groups"]
        complete = directory / "update/COMPLETE.json"
        if complete.exists():
            adapter, _ = verify_checkpoint(directory / "update")
            m = json.loads(complete.read_text())
            seconds_update += m["elapsed_seconds"]
            active_tokens += m["valid_tokens"]
            rounds += 1
        elif (directory / "SKIPPED.json").exists():
            rounds += 1
        else:
            break
    return {
        "rounds": rounds,
        "adapter": adapter,
        "generated_responses": generated,
        "tokens": tokens,
        "generation_seconds": generation_seconds,
        "mixed_groups": mixed,
        "update_seconds": seconds_update,
        "valid_tokens": active_tokens,
    }


def forecast(config, state, budget_remaining):
    completed = state["rounds"]
    left = config["rounds"] - completed
    if not completed or not state["tokens"] or not state["generation_seconds"]:
        raise ValueError("A completed segment with measured generation is required")
    observed_rate = state["tokens"] / state["generation_seconds"]
    rate = min(observed_rate, config["planning"]["training_tokens_per_second"])
    length = max(22000, state["tokens"] / state["generated_responses"])
    seconds_round = (
        length * 16 / rate
        + max(state["update_seconds"] / completed, config["planning"]["update_seconds_per_round"])
        + config["planning"]["process_overhead_seconds_per_round"]
    )
    train_remaining = left * seconds_round * config["planning"]["safety_factor"]
    reserve = config["evaluation_reserve_hours"] * 3600
    enough_signal = state["mixed_groups"] >= config["minimum_mixed_groups_after_five"]
    return {
        "utc": now(),
        "completed_rounds": completed,
        "estimated_training_seconds_remaining": train_remaining,
        "reserved_evaluation_seconds": reserve,
        "budget_seconds_remaining": budget_remaining,
        "observed_tokens_per_second": observed_rate,
        "planning_answer_length": length,
        "enough_reward_signal": enough_signal,
        "continue": enough_signal and train_remaining + reserve <= budget_remaining,
        "rule": "Fixed cost/signal gate; no dev or proof scores used for checkpoint selection.",
    }


def evaluation(config, training, out, suite, adapter):
    # The stage worker can resume saved groups. A finished export is immutable.
    summary = out / "summary.json"
    if summary.exists():
        s = json.loads(summary.read_text())
        if s["response_sha256"] != file_hash(out / "responses.jsonl"):
            raise ValueError("Completed evaluation was changed")
        context = json.loads((out / "generation/generation_manifest.json").read_text())
        expected_adapter = (
            file_hash(Path(adapter) / "adapter_model.safetensors") if adapter else "base"
        )
        if (
            context["adapter_sha256"] != expected_adapter
            or context["samples"] != config["evaluation_samples"][suite]
        ):
            raise ValueError("Completed evaluation uses a different policy/sample count")
        return
    command = [
        sys.executable,
        "-m",
        "qwen.grpo_evaluate",
        "--suite",
        suite,
        "--samples",
        str(config["evaluation_samples"][suite]),
        "--seed",
        str(config["evaluation_seed"]),
        "--experiment",
        str(training),
        "--output",
        str(out),
        "--wall-hours",
        "40",
    ]
    if adapter:
        command += ["--adapter", adapter]
    subprocess.run(command, check=True)


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("--config", default="qwen/configs/exp03_budgeted.json")
    ap.add_argument("--output", default="qwen/.runtime/exp03_budgeted/study")
    ap.add_argument("--run", action="store_true", help="Start the prepared long experiment")
    args = ap.parse_args()
    config = json.loads(Path(args.config).read_text())
    root = Path(args.output).resolve()
    training = root / "training"
    gate = json.loads(Path(config["readiness_gate"]).read_text())
    ledger = Path(config["budget_ledger"])
    budget = json.loads(ledger.read_text())
    validate_config(config, gate, budget)
    groups = prepare(config, training)
    if len(groups) != 37 or sum(map(len, groups)) != 148:
        raise ValueError("The approved 37-configuration/148-problem training set changed")
    contract = {
        "config_sha256": file_hash(args.config),
        "readiness_sha256": file_hash(config["readiness_gate"]),
        "training_manifest_sha256": file_hash(training / "manifest.json"),
        "budget_created_utc": budget["created_utc"],
    }
    ready = root / "PREPARED.json"
    if ready.exists() and json.loads(ready.read_text()) != contract:
        raise ValueError("Prepared study changed")
    write_json(ready, contract)
    if not args.run:
        print(
            json.dumps(
                {
                    "prepared": str(ready),
                    "gpu_experiment_started": False,
                    "remaining_gpu_hours": remaining(budget) / 3600,
                }
            )
        )
        return
    if (root / "COMPLETE.json").exists():
        print((root / "COMPLETE.json").read_text())
        return
    # Both arms use the new route; exp01 outputs are not the matched baseline.
    for suite in ("proof", "numeric"):
        evaluation(config, training, root / f"base_{suite}", suite, "")
    decision_path = root / "STOP.json"
    while not decision_path.exists():
        state = progress(training)
        if state["rounds"] == config["rounds"]:
            break
        if state["rounds"] >= 5:
            decision = forecast(config, state, remaining(json.loads(ledger.read_text())))
            write_json(root / f"cost-check-{state['rounds']:03}.json", decision)
            if not decision["continue"]:
                write_json(
                    decision_path, {**decision, "reason": "cost_or_insufficient_reward_signal"}
                )
                break
        through = min(config["rounds"], max(5, state["rounds"] + 1))
        command = [
            sys.executable,
            "-m",
            "qwen.grpo_run",
            "--config",
            args.config,
            "--output",
            str(training),
            "--through-round",
            str(through),
        ]
        result = subprocess.run(command)
        if result.returncode:
            journal = json.loads((training / "attempts.json").read_text())
            if journal[-1].get("budget_stop"):
                write_json(decision_path, {"reason": "budget_reserve_reached", "utc": now()})
                break
            # Preserve the last fully committed checkpoint and all failure logs.
            # Do not spend reserved evaluation money automatically after a
            # numerical/identity failure, which requires diagnosis first.
            raise RuntimeError(
                "Training interrupted; inspect logs. Budget and completed rounds remain resumable."
            )
    state = progress(training)
    adapter = state["adapter"]
    if not adapter:
        write_json(
            root / "NO_UPDATE.json", {"reason": "No valid optimizer update; no transfer claim."}
        )
        print("No adapter was updated. Stopped without redundant base-vs-base evaluation.")
        return
    for suite in ("proof", "numeric"):
        evaluation(config, training, root / f"trained_{suite}", suite, adapter)
    numeric_pairs = paired(
        read_rows(root / "base_numeric/responses.jsonl"),
        read_rows(root / "trained_numeric/responses.jsonl"),
    )
    write_json(root / "numeric_summary.json", numeric(numeric_pairs))
    packet = root / "proof_review"
    packet.mkdir(exist_ok=True)
    if not (packet / "blinded.jsonl").exists():
        blind(
            paired(
                read_rows(root / "base_proof/responses.jsonl"),
                read_rows(root / "trained_proof/responses.jsonl"),
            ),
            packet,
        )
    budget = json.loads(ledger.read_text())
    write_json(
        root / "COMPLETE.json",
        {
            "rounds_completed": state["rounds"],
            "adapter": adapter,
            "gpu_hours_including_preparation": sum(j["charged_seconds"] for j in budget["jobs"])
            / 3600,
            "proof_grading": "48 blinded responses await mathematical review; no conclusion yet.",
            "utc": now(),
        },
    )
    print((root / "COMPLETE.json").read_text())


if __name__ == "__main__":
    main()
