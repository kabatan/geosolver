"""Build the budgeted FP16 readiness gate from measured preparation artifacts."""

from __future__ import annotations

import ast
import json
import math
from pathlib import Path

from .common import file_hash, now, write_json
from .experiment_budget import remaining

ROOT = Path("qwen/.runtime/exp03_budgeted")
PREP = ROOT / "preparation"


def read(path):
    return json.loads(Path(path).read_text())


def code_tree(path):
    # Comments/docstrings do not affect the executed algorithm. Hash and record
    # any such changes; substantive source changes require revalidation.
    tree = ast.parse(Path(path).read_text())
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            and node.body
            and isinstance(node.body[0], ast.Expr)
        ):
            value = node.body[0].value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                node.body = node.body[1:]
    return ast.dump(tree, include_attributes=False)


def cost_estimate(generation, update, budget, capacity, safety=1.15):
    rates = {name: g["output_tokens"] / g["generation_seconds"] for name, g in generation.items()}
    train_rate = min(rates["base4"], rates["adapter4"])
    numeric_rate = min(train_rate, rates["adapter2"])
    # 22k from previous natural long-answer data; 32,512 for evaluation reserve.
    prep_used = sum(j["charged_seconds"] for j in budget["jobs"])
    # Budget ALL 16 completions as active, using the measured 32k backward
    # time per token and 512 prompt tokens per response. This is more costly
    # than the observed 10-active-response update. Include the entire measured
    # non-backward time (also includes the calibration-only after-measurement),
    # then round up to 30s. The previous 300s was an unmeasured placeholder.
    update_overhead = max(0, update["elapsed_seconds"] - update["forward_backward_seconds"])
    update_seconds = (
        math.ceil(
            (
                16 * (22000 + 512) * capacity["capacity_seconds"] / capacity["context_tokens"]
                + update_overhead
            )
            / 30
        )
        * 30
    )
    process_overhead = 60
    train = (592 * 22000 / train_rate + 37 * (update_seconds + process_overhead)) * safety
    evaluations = (148 * 22000 / numeric_rate + 48 * 22000 / train_rate + 4 * 60) * safety
    post_reserve = (74 * 32512 / numeric_rate + 24 * 32512 / train_rate + 120) * safety
    hours = (prep_used + train + evaluations) / 3600
    reserved_hours = (prep_used + train + evaluations / 2 + post_reserve) / 3600
    return {
        "measured_tokens_per_second": rates,
        "planning_training_tokens_per_second": train_rate,
        "planning_numeric_tokens_per_second": numeric_rate,
        "answer_length_assumption": 22000,
        "safety_factor": safety,
        "update_seconds_per_round": update_seconds,
        "update_time_basis": {
            "capacity_context_tokens": capacity["context_tokens"],
            "capacity_backward_seconds": capacity["capacity_seconds"],
            "active_responses_assumed": 16,
            "context_tokens_per_response_assumed": 22512,
            "measured_non_backward_seconds_included": update_overhead,
            "round_up_seconds": 30,
        },
        "process_overhead_seconds_per_round": process_overhead,
        "preparation_hours": prep_used / 3600,
        "estimated_training_hours": train / 3600,
        "estimated_before_after_evaluation_hours": evaluations / 3600,
        "estimated_total_hours": hours,
        "total_with_post_evaluation_reserve_hours": reserved_hours,
        "post_evaluation_reserve_seconds": post_reserve,
        "fits_40_hours": reserved_hours <= 40,
        "limitation": (
            "15% margin is a planning allowance, not a statistical bound. "
            "Hard worker budget and repeated cost gates are separate protections."
        ),
    }


def main():
    selection = read(PREP / "selected_calibration.json")
    fixed_root = PREP / selection["fixed"]
    natural_root = PREP / selection["natural"]
    files = {
        "learner": fixed_root / "learner.json",
        "actor": fixed_root / "actor.json",
        "fixed_rows": fixed_root / "rows.json",
        "natural": natural_root / "update/COMPLETE.json",
        "restore": natural_root / "restore_capacity.json",
        "tests": PREP / "tests.json",
        "resume": PREP / "resume_check.json",
        "review": PREP / "numeric_reward_review.json",
    }
    data = {name: read(path) for name, path in files.items()}
    budget = read(ROOT / "budget.json")
    remaining(budget)
    generation_paths = {
        "base4": PREP / "natural/generation/generation_metrics.json",
        "adapter4": PREP / "speed_adapter4/generation_metrics.json",
        "adapter2": PREP / "speed_adapter2/generation_metrics.json",
    }
    generation = {k: read(p) for k, p in generation_paths.items()}
    generation_manifests = {
        k: read(p.with_name("generation_manifest.json")) for k, p in generation_paths.items()
    }
    cost = cost_estimate(generation, data["natural"], budget, data["restore"])
    history = data["learner"]["history"]
    checks = {
        "fixed_objective_improved_each_step": all(
            a["objective"] < b["objective"] for a, b in zip(history[:-1], history[1:], strict=True)
        ),
        "selected_hyperparameters_match": data["learner"]["lr"]
        == data["natural"]["lr"]
        == selection["lr"],
        "fixed_adapter_changed": data["learner"]["parameter_delta_l2"] > 0,
        "natural_update_finite": math.isfinite(data["natural"]["gradient_norm"])
        and data["natural"]["gradient_norm"] > 0,
        "natural_adapter_changed": data["natural"]["parameter_delta_l2"] > 0,
        "natural_objective_improved": data["natural"]["new_objective"]
        > data["natural"]["old_objective"],
        "checkpoint_restore": data["restore"]["reload_pass"],
        "full_context_capacity": data["restore"]["capacity_pass"]
        and data["restore"]["context_tokens"] == 32768,
        "cpu_tests": data["tests"]["exit_code"] == 0,
        "resume_without_update": data["resume"]["workers_launched"] == 0
        and data["resume"]["checkpoint_unchanged"],
        "numeric_reward_review": data["review"]["all_numeric_rewards_match"],
        "within_preparation_budget": cost["preparation_hours"] <= 2,
        "cost_fits": cost["fits_40_hours"],
    }
    details = [read(p) for p in sorted((natural_root / "update").glob("detail-*.json"))]
    checks["correction_acceptable"] = bool(details) and all(
        d["sampling_correction"]["relative_ess"] >= 0.90
        and d["sampling_correction"]["clipped_fraction"] <= 0.01
        for d in details
    )
    rollouts_path = PREP / "natural/generation/rollouts.json"
    checks["natural_provenance"] = (
        data["natural"]["route"] == "fp16_native"
        and data["natural"]["rollouts_sha256"] == file_hash(rollouts_path)
        and data["review"]["rollouts_sha256"] == file_hash(rollouts_path)
        and data["natural"]["adapter_sha256"]
        == file_hash(natural_root / "update/adapter/adapter_model.safetensors")
    )
    checks["speed_measurements_use_selected_policy"] = all(
        m["route"] == "fp16_native"
        and m["max_seqs"] == 4
        and m["max_completion"] == 32512
        and m["samples"] == (2 if k == "adapter2" else 4)
        and m["adapter_sha256"] == ("base" if k == "base4" else data["natural"]["adapter_sha256"])
        for k, m in generation_manifests.items()
    )
    # Positive adapter movement must exceed base-run drift for every repeated
    # pairing. This is a directional calibration, not FP32 delta equivalence.
    values = data["actor"]["values"]
    advantages = [r["advantage"] for r in data["fixed_rows"] for _ in r["completion_ids"]]
    flat = {k: [x for row in v for x in row] for k, v in values.items()}

    def improvement(base, trained):
        return sum(
            (math.exp(b - a) - 1) * adv
            for a, b, adv in zip(flat[base], flat[trained], advantages, strict=True)
        ) / len(advantages)

    drift = abs(improvement("base", "base_repeat"))
    changes = {
        f"{a}_to_{b}": improvement(a, b)
        for a in ("base", "base_repeat")
        for b in ("trained", "trained_repeat")
    }
    checks["actor_direction_exceeds_control"] = min(changes.values()) > drift
    core = ["qwen/grpo_policy.py", "qwen/grpo_loss.py", "qwen/grpo_stage.py", "qwen/fast_engine.py"]
    archived = PREP / "source_natural"
    original_hashes = read(archived / "manifest.json")
    checks["executed_core_unchanged"] = all(
        file_hash(archived / p) == original_hashes[p] and code_tree(p) == code_tree(archived / p)
        for p in core
    )
    checks["tested_driver_unchanged"] = all(
        file_hash(p) == h for p, h in data["tests"]["source_sha256"].items()
    )
    sources = [str(p) for p in sorted(Path("qwen").glob("*.py"))] + ["qwen/models.json"]
    evidence_paths = [*files.values(), *generation_paths.values(), rollouts_path]
    evidence_paths += [p.with_name("generation_manifest.json") for p in generation_paths.values()]
    evidence = {str(p): file_hash(p) for p in evidence_paths}
    report = {
        "technical_pass": all(checks.values()),
        "route": "fp16_native",
        "utc": now(),
        "validated_lr": data["natural"]["lr"],
        "selected_calibration": selection,
        "checks": checks,
        "cost": cost,
        "actor_direction": changes,
        "actor_base_drift": drift,
        "source_sha256": {p: file_hash(p) for p in sources},
        "evidence_sha256": evidence,
        "budget_created_utc": budget["created_utc"],
        "preparation_jobs": budget["jobs"],
        "executed_source_sha256": {p: original_hashes[p] for p in core},
        "scope": (
            "Technical/cost readiness only. Native FP16 actor and learner differ numerically; "
            "token-truncated IS is an approximation. No evidence of proof transfer yet."
        ),
    }
    write_json(ROOT / "readiness.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["technical_pass"]:
        raise SystemExit("Fast route is not ready")


if __name__ == "__main__":
    main()
