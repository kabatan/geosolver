"""Create a fail-closed readiness record from completed calibration artifacts."""

from __future__ import annotations

import json
import math
from pathlib import Path

from .common import file_hash, now, write_json


def main():
    root = Path("qwen/.runtime/exp02_tech")
    required = {
        "loss": root / "loss_equivalence.json",
        "actor": root / "vllm_forward_ieee.json",
        "fixed": root / "fixed/fixed_update_metrics.json",
        "fixed_recheck": root / "fixed_efficient/fixed_update_metrics.json",
        "attention": root / "attention.json",
        "capacity": root / "capacity.json",
        "fixed_actor": root / "fixed_vllm.json",
        "live": root / "live/round-000/update/COMPLETE.json",
        "rollouts": root / "live/round-000/generation/rollouts.json",
        "reload": root / "live/round-000/reload_verification.json",
        "live_actor": root / "live_vllm.json",
        "review": root / "positive_answer_review.json",
        "manifest": root / "live/manifest.json",
        "update_manifest": root / "live/update_recovery_manifest.json",
        "resume_smoke": root / "resume_smoke_verification.json",
    }
    missing = [str(p) for p in required.values() if not p.exists()]
    if missing:
        write_json(
            root / "readiness.json", {"technical_pass": False, "missing": missing, "utc": now()}
        )
        raise SystemExit("Calibration is incomplete; missing " + ", ".join(missing))
    data = {k: json.loads(p.read_text()) for k, p in required.items()}
    checks = {}
    checks["loss_equivalence"] = all(r["passed"] for r in data["loss"])
    for label in ("actor", "fixed_actor", "live_actor"):
        metrics = data[label]
        delta = metrics["adapter_delta"]
        checks[label] = (
            delta["relative_l2"] <= 0.1
            and delta["cosine"] >= 0.95
            and metrics["repeat_max_abs"] <= 1e-4
            and metrics["base_engine"]["max_error"] <= 1e-3
        )
    fixed = data["fixed"]
    checks["fixed_update"] = (
        fixed["parameter_delta_l2"] > 0
        and fixed["history"][-1]["objective"] > fixed["history"][0]["objective"]
        and fixed["comparisons"]["bounded"]["relative_l2"] <= 1e-5
        and fixed["comparisons"]["liger"]["relative_l2"] <= 1e-4
    )
    recheck = data["fixed_recheck"]
    checks["fixed_after_attention_fix"] = (
        recheck["parameter_delta_l2"] > 0
        and recheck["history"][-1]["objective"] > recheck["history"][0]["objective"]
        and recheck["comparisons"]["bounded"]["relative_l2"] <= 1e-5
        and recheck["comparisons"]["liger"]["relative_l2"] <= 1e-4
    )
    checks["attention_equivalence"] = data["attention"]["length32768_backward_finite"] and all(
        r["forward"]["relative_l2"] <= 1e-5
        and all(g["relative_l2"] <= 1e-5 for g in r["gradients"])
        for r in data["attention"]["comparisons"]
    )
    capacity = data["capacity"]
    checks["full_context_with_optimizer"] = (
        capacity["context_tokens"] == 32768
        and capacity["optimizer_state_loaded"]
        and math.isfinite(capacity["gradient_norm"])
        and capacity["gradient_norm"] > 0
    )
    live = data["live"]
    checks["real_update"] = (
        math.isfinite(live["gradient_norm"])
        and live["gradient_norm"] > 0
        and live["parameter_delta_l2"] > 0
        and live["new_objective"] > live["old_objective"]
    )
    checks["valid_tokens"] = (
        sum(r["valid_tokens"] for r in data["rollouts"]) == live["valid_tokens"]
    )
    reload = data["reload"]
    checks["checkpoint_reload"] = (
        reload["optimizer_max_abs_error"] == 0
        and bool(reload["logprob_comparisons"])
        and max(r["max_abs_error"] for r in reload["logprob_comparisons"]) <= 1e-4
    )
    checks["completed_round_resume"] = (
        data["resume_smoke"]["rounds_completed"] == 1
        and data["resume_smoke"]["adapter_unchanged"]
        and data["resume_smoke"]["optimizer_unchanged"]
        and data["resume_smoke"]["workers_launched"] == 0
    )

    def identity(r):
        return r["id"], r["variant"], r["sample"]

    details = [
        json.loads(p.read_text())
        for p in sorted((root / "live/round-000/update").glob("detail-*.json"))
    ]
    checks["long_engine_agreement"] = bool(details) and all(
        math.isfinite(r["engine_max_abs_error"]) and r["engine_max_abs_error"] <= 1e-3
        for r in details
    )
    positive = {identity(r) for r in data["rollouts"] if r["reward"] == 1}
    reviews = data["review"]["reviews"]
    checks["positive_numeric_audit"] = (
        len(reviews) == len(positive)
        and {identity(r) for r in reviews} == positive
        and all(r["numeric_reward_correct"] for r in reviews)
    )
    core = [
        "qwen/grpo_loss.py",
        "qwen/grpo_policy.py",
        "qwen/grpo_stage.py",
        "qwen/rollout_engine.py",
    ]
    checks["executed_core_unchanged"] = all(
        file_hash(p) == data["update_manifest"]["source_sha256"][p] for p in core
    )
    checks["recovery_provenance"] = (
        data["update_manifest"]["original_manifest_sha256"] == file_hash(required["manifest"])
        and data["update_manifest"]["rollouts_sha256"] == file_hash(required["rollouts"])
        and data["update_manifest"]["attention_validation_sha256"]
        == file_hash(required["attention"])
        and all(
            data["manifest"]["source_sha256"][p] == file_hash(p)
            for p in core
            if p != "qwen/grpo_policy.py"
        )
    )
    files = core + [
        "qwen/grpo_run.py",
        "qwen/grpo_evaluate.py",
        "qwen/grpo_compare.py",
        "qwen/answer_check.py",
        "qwen/models.py",
        "qwen/models.json",
        "qwen/common.py",
    ]
    report = {
        "technical_pass": all(checks.values()),
        "checks": checks,
        "source_sha256": {p: file_hash(p) for p in files},
        "evidence_sha256": {str(p): file_hash(p) for p in required.values()},
        "positive_answers_with_false_math": sum(r["final_solution_math_error"] for r in reviews),
        "scope": "Technical readiness for an exploratory numeric-only transfer study. "
        "Not evidence of proof transfer or a solver-generated corpus.",
        "utc": now(),
    }
    write_json(root / "readiness.json", report)
    print(json.dumps(report, indent=2))
    if not report["technical_pass"]:
        raise SystemExit("Calibration did not pass all gates")
    write_json(
        root / "live/RECOVERED_COMPLETE.json",
        {
            "readiness_sha256": file_hash(root / "readiness.json"),
            "optimizer_updates": 1,
            "original_failed_attempt_preserved": True,
            "recovery_manifest_sha256": file_hash(required["update_manifest"]),
            "utc": now(),
        },
    )


if __name__ == "__main__":
    main()
