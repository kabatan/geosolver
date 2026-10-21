"""Frozen FP32 base/adapter evaluation using the same rollout engine as training."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .common import file_hash, write_json
from .grpo_run import run_worker

SUITES = {
    "numeric": "benchmarks/humpty_configurations_v2/eval_variants.jsonl",
    "proof": "benchmarks/humpty_proof_evaluation_v2/evaluation_prompts.jsonl",
    "proof_hint": "benchmarks/humpty_proof_evaluation_v2/auxiliary_hint_prompts.jsonl",
}


def resolve_evaluation_config(config, suite, *, stage_name=None, samples=None, seed=None):
    """Resolve an evaluation block without loading models or starting workers.

    Stage samples and seeds are protocol values. Explicit CLI overrides must
    agree; omitted values inherit the frozen protocol. Legacy runs retain the
    original suite paths and default sampling settings.
    """
    suites = config.get("evaluation_suites", SUITES)
    if not isinstance(suites, dict) or suite not in suites:
        raise ValueError(f"Evaluation suite is not in the frozen protocol: {suite}")
    source = suites[suite]
    if not isinstance(source, str) or not source:
        raise ValueError("An evaluation suite requires a source path")
    path = Path(source)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Frozen evaluation paths must be relative to the repository")
    expected_n = config.get("evaluation_samples", {}).get(suite)
    expected_seed = None
    stages = config.get("evaluation_stages")
    if stages is not None:
        if not isinstance(stages, dict) or stage_name not in stages:
            raise ValueError("A declared evaluation stage name is required")
        stage = stages[stage_name]
        if not isinstance(stage, dict) or suite not in stage:
            raise ValueError(f"Suite {suite} is not enabled for evaluation stage {stage_name}")
        block = stage[suite]
        if not isinstance(block, dict) or set(block) != {"samples", "seed"}:
            raise ValueError("Each evaluation stage suite requires samples and seed")
        expected_n, expected_seed = block["samples"], block["seed"]
    elif stage_name is not None:
        raise ValueError("Evaluation stage was requested without a frozen stage protocol")
    if expected_n is not None and samples is not None and samples != expected_n:
        raise ValueError("Evaluation sample count differs from frozen protocol")
    if expected_seed is not None and seed is not None and seed != expected_seed:
        raise ValueError("Evaluation seed differs from frozen protocol")
    samples = samples if samples is not None else (expected_n if expected_n is not None else 8)
    seed = seed if seed is not None else (expected_seed if expected_seed is not None else 20261001)
    if type(samples) is not int or samples < 1 or type(seed) is not int or seed < 0:
        raise ValueError(
            "Evaluation samples must be positive and seed must be a nonnegative integer"
        )
    return {"data": str(path), "samples": samples, "seed": seed, "stage_name": stage_name}


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("--suite", required=True)
    ap.add_argument("--adapter", default="")
    ap.add_argument("--output", required=True)
    ap.add_argument("--samples", type=int)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--stage-name", help="Use one frozen evaluation_stages block")
    ap.add_argument("--wall-hours", type=float, default=24)
    ap.add_argument("--experiment", help="Use evaluation inputs frozen by this training run")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--route", choices=["fp32", "fp16_native"], default="fp32")
    ap.add_argument("--budget-ledger")
    args = ap.parse_args()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    config = {}
    manifest = None
    if args.experiment:
        experiment = Path(args.experiment)
        manifest = json.loads((experiment / "manifest.json").read_text())
        config = manifest["config"]
        args.route = config.get("route", "fp32")
        if config.get("budget_ledger"):
            args.budget_ledger = config["budget_ledger"]
    protocol = resolve_evaluation_config(
        config, args.suite, stage_name=args.stage_name, samples=args.samples, seed=args.seed
    )
    args.samples, args.seed = protocol["samples"], protocol["seed"]
    data_path = Path(protocol["data"])
    if manifest is not None:
        for name, expected_hash in manifest["source_sha256"].items():
            if file_hash(name) != expected_hash:
                raise ValueError(f"Frozen evaluation code changed: {name}")
        expected = manifest.get("evaluation_sha256", {}).get(str(data_path))
        if expected is None:
            raise ValueError("Evaluation source has no frozen hash in the training manifest")
        data_path = experiment / "source" / data_path
        if file_hash(data_path) != expected:
            raise ValueError("Frozen evaluation inputs were modified")
    rows = [json.loads(line) for line in data_path.read_text().splitlines() if line.strip()]
    rows = [
        {**r, "problem": r.get("problem", r.get("prompt")), "variant": r.get("variant", "v0")}
        for r in rows
    ]
    jobs = out / "jobs.json"
    if jobs.exists() and json.loads(jobs.read_text()) != rows:
        raise ValueError("Evaluation inputs have changed")
    write_json(jobs, rows)
    command = [
        sys.executable,
        "-m",
        "qwen.grpo_stage",
        "generate",
        "--route",
        args.route,
        "--jobs",
        str(jobs),
        "--output",
        str(out / "generation"),
        "--samples",
        str(args.samples),
        "--seed",
        str(args.seed),
        "--kv",
        "auto",
        "--max-seqs",
        "4" if args.route == "fp16_native" else "2",
    ]
    if args.adapter:
        command.extend(["--adapter", args.adapter])
    if args.dry:
        print(
            json.dumps(
                {
                    "suite": args.suite,
                    "stage_name": args.stage_name,
                    "problems": len(rows),
                    "responses": len(rows) * args.samples,
                    "input_sha256": file_hash(jobs),
                    "command": command,
                },
                ensure_ascii=False,
            )
        )
        return
    if args.budget_ledger:
        from .experiment_budget import run_budgeted

        run_budgeted(
            command, out / "generate.log", args.budget_ledger, "evaluation", args.wall_hours * 3600
        )
    else:
        run_worker(command, out / "generate.log", args.wall_hours * 3600)
    responses = json.loads((out / "generation/rollouts.json").read_text())
    export = out / "responses.jsonl"
    export.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in responses))
    summary = {
        "suite": args.suite,
        "stage_name": args.stage_name,
        "problems": len(rows),
        "responses": len(responses),
        "response_sha256": file_hash(export),
        "complete_proof_grading": "manual blinded review required",
    }
    if args.suite == "numeric":
        summary["correct"] = sum(r["reward"] for r in responses)
        summary["per_problem"] = [
            {
                "id": r["id"],
                "variant": r["variant"],
                "correct": sum(
                    x["reward"]
                    for x in responses
                    if x["id"] == r["id"] and x["variant"] == r["variant"]
                ),
                "n": args.samples,
            }
            for r in rows
        ]
        summary.pop("complete_proof_grading")
    write_json(out / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
