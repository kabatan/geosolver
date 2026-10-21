"""Outcome-only transfer study with a fixed round-10 scientific review.

Preparation is the default. --run performs GPU work, stopping for analysis at
round 10. A recorded scientific decision (not a new permission request) selects
continuation or a matched final evaluation. V/G rewards are never enabled here.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .answer_check import PARSER_VERSION, final_text
from .common import digest, file_hash, read_json, stable_seed, write_json
from .experiment_budget import remaining
from .grpo_compare import blind, freeze_and_unblind, numeric, paired, read_rows
from .grpo_evaluate import resolve_evaluation_config
from .grpo_run import prepare
from .grpo_stage import row_identity
from .study_run import progress

DEFAULT_CONFIG = "qwen/configs/exp03_staged.json"
DEFAULT_ROOT = "qwen/.runtime/exp03_staged/study"
PRIMARY = ("N01", "N02", "AP01")
SECONDARY = ("EV02", "DU01", "OB01")
PROOF_BOOL_FIELDS = (
    "core_proved",
    "core_applied_correctly",
    "auxiliary_constructed",
    "auxiliary_useful",
    "unsupported_core_claim",
)


def frozen_json(path, value):
    path = Path(path)
    if path.exists():
        if read_json(path) != value:
            raise ValueError(f"Frozen artifact changed: {path}")
    else:
        write_json(path, value)


def frozen_rows(path, rows):
    path = Path(path)
    if path.exists():
        if read_rows(path) != rows:
            raise ValueError(f"Frozen response export changed: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def validate_evaluation_protocol(config):
    expected = {
        "base0": {"proof", "numeric"},
        "base1": {"proof"},
        "interim": {"proof", "numeric"},
        "final0": {"proof", "numeric"},
        "final1": {"proof"},
    }
    stages = config.get("evaluation_stages", {})
    if set(stages) != set(expected) or set(config.get("evaluation_suites", {})) != {
        "proof",
        "numeric",
    }:
        raise ValueError("Evaluation stages/suites differ from the costed protocol")
    for name, suites in expected.items():
        if not isinstance(stages[name], dict) or set(stages[name]) != suites:
            raise ValueError("Evaluation stages/suites differ from the costed protocol")
        for suite in suites:
            spec = resolve_evaluation_config(config, suite, stage_name=name)
            if spec["samples"] != (4 if suite == "proof" else 2):
                raise ValueError("Evaluation sample counts differ from the costed protocol")
    for suite in ("proof", "numeric"):
        if len({stages[s][suite]["seed"] for s in ("base0", "interim", "final0")}) != 1:
            raise ValueError("Paired evaluation stages must use identical seeds")
    if stages["base1"]["proof"]["seed"] != stages["final1"]["proof"]["seed"]:
        raise ValueError("Paired evaluation stages must use identical seeds")
    if stages["base0"]["proof"]["seed"] == stages["base1"]["proof"]["seed"]:
        raise ValueError("Proof blocks must use different seeds")


def validate_suite_rows(config, suite, rows):
    expected = set(PRIMARY + SECONDARY) if suite == "proof" else set(config["training_audit_ids"])
    size = 6 if suite == "proof" else 12
    if len(expected) != size or len(rows) != size or {r["id"] for r in rows} != expected:
        raise ValueError(f"Frozen {suite} suite must contain exactly {size} approved problems")
    if any(not isinstance(r.get("problem", r.get("prompt")), str) for r in rows):
        raise ValueError("Evaluation problem text is missing")


def validate_evaluation_inputs(config):
    for suite, source in config["evaluation_suites"].items():
        validate_suite_rows(config, suite, read_rows(source))


def validate(config, gate, budget):
    validate_evaluation_protocol(config)
    validate_evaluation_inputs(config)
    expected = {
        "route": "fp16_native",
        "samples": 4,
        "prompts_per_round": 4,
        "rounds": 37,
        "review_round": 10,
        "training_order": "representatives_first",
        "reward_condition": "C",
        "max_seqs": 4,
        "max_completion": 32512,
        "kv_cache_dtype": "auto",
        "lr": gate["validated_lr"],
    }
    if any(config.get(k) != v for k, v in expected.items()):
        raise ValueError("Staged study differs from the validated outcome-only protocol")
    if not gate.get("technical_pass") or config.get("technical_calibration"):
        raise ValueError("Completed technical and orchestration verification is required")
    if gate["config_sha256"] != file_hash(config["config_path"]):
        raise ValueError("Configuration changed after readiness")
    if budget["limit_seconds"] != config["wall_hours"] * 3600:
        raise ValueError("Operational time fuse differs from frozen configuration")
    if budget["created_utc"] != gate["budget_created_utc"]:
        raise ValueError("Budget ledger was replaced")
    prefix = gate["inherited_jobs"]
    if budget["jobs"][: len(prefix)] != prefix:
        raise ValueError("Earlier preparation charges were removed or changed")
    remaining(budget)
    for path, expected_hash in gate["source_sha256"].items():
        if file_hash(path) != expected_hash:
            raise ValueError(f"Validated source changed: {path}")
    for path, expected_hash in gate["evidence_sha256"].items():
        if file_hash(path) != expected_hash:
            raise ValueError(f"Readiness evidence changed: {path}")


def plan_cost(config, prep_hours=0.0):
    validate_evaluation_protocol(config)
    p = config["planning"]
    length, margin = p["answer_tokens"], p["safety_factor"]
    train_rate, numeric_rate = p["training_tokens_per_second"], p["numeric_tokens_per_second"]
    per_round = (
        (
            16 * length / train_rate
            + p["update_seconds_per_round"]
            + p["process_overhead_seconds_per_round"]
        )
        * margin
        / 3600
    )

    # Base: 48 proofs +24 numeric; interim:24+24; final:48+24.
    def evaluation_cost(proofs, numerics, workers, cap=length):
        return (
            (proofs * cap / train_rate + numerics * cap / numeric_rate + workers * 60)
            * margin
            / 3600
        )

    base = evaluation_cost(48, 24, 3)
    interim = evaluation_cost(24, 24, 2)
    final = evaluation_cost(48, 24, 3)
    return {
        "preparation_hours": prep_hours,
        "first_review_total_hours": prep_hours + base + 10 * per_round + interim,
        "full_study_total_hours": prep_hours + base + 37 * per_round + interim + final,
        "training_hours": 37 * per_round,
        "evaluation_hours": base + interim + final,
        "final_evaluation_cap_hours": evaluation_cost(48, 24, 3, config["max_completion"]),
        "planning_range_hours": config["planning_range_hours"],
        "operational_fuse_hours": config["wall_hours"],
        "limitation": "Extrapolation from small calibration samples, not a runtime guarantee. "
        "Human/AI mathematical grading and future judge API costs are separate.",
    }


def cost_status(config, state, budget):
    p = config["planning"]
    observed = (
        state["tokens"] / state["generation_seconds"]
        if state["generation_seconds"]
        else p["training_tokens_per_second"]
    )
    length = max(p["answer_tokens"], state["tokens"] / max(1, state["generated_responses"]))
    per_round = (
        16 * length / min(observed, p["training_tokens_per_second"])
        + max(p["update_seconds_per_round"], state["update_seconds"] / max(1, state["rounds"]))
        + p["process_overhead_seconds_per_round"]
    ) * p["safety_factor"]
    used = sum(j["charged_seconds"] for j in budget["jobs"])
    reserve = config["evaluation_reserve_hours"] * 3600
    projection = (used + (config["rounds"] - state["rounds"]) * per_round + reserve) / 3600
    return {
        "rounds": state["rounds"],
        "charged_hours": used / 3600,
        "projected_total_with_evaluation_reserve_hours": projection,
        "above_planning_guideline": projection > max(config["planning_range_hours"]),
        "can_afford_next_round_and_evaluation": remaining(budget) >= per_round + reserve,
        "mixed_groups": state["mixed_groups"],
        "note": "40 hours is advisory. Only the operational fuse and real failures stop workers; "
        "sparse reward or absent early transfer is evidence for the round-10 review.",
    }


def evaluate(config, training, out, stage, suite, adapter):
    spec = config["evaluation_stages"][stage][suite]
    manifest = read_json(training / "manifest.json")
    source = str(Path(config["evaluation_suites"][suite]))
    frozen_source = training / "source" / source
    if manifest.get("evaluation_sha256", {}).get(source) != file_hash(frozen_source):
        raise ValueError("Frozen staged evaluation input changed or has no hash")
    jobs = [
        {**r, "problem": r.get("problem", r.get("prompt")), "variant": r.get("variant", "v0")}
        for r in read_rows(frozen_source)
    ]
    validate_suite_rows(config, suite, jobs)
    summary = out / "summary.json"
    if summary.exists():
        saved = read_json(summary)
        context = read_json(out / "generation/generation_manifest.json")
        adapter_hash = file_hash(Path(adapter) / "adapter_model.safetensors") if adapter else "base"
        if (
            saved["response_sha256"] != file_hash(out / "responses.jsonl")
            or saved.get("suite") != suite
            or saved.get("stage_name") != stage
            or read_json(out / "jobs.json") != jobs
            or context["jobs_sha256"] != file_hash(out / "jobs.json")
            or context["adapter_sha256"] != adapter_hash
            or context["samples"] != spec["samples"]
            or context["seed"] != spec["seed"]
            or context["route"] != config["route"]
            or context["kv"] != "auto"
            or context["max_completion"] != config["max_completion"]
            or context["max_seqs"] != config["max_seqs"]
            or context["parser_version"] != PARSER_VERSION
            or context["source_sha256"] != manifest["source_sha256"]["qwen/grpo_stage.py"]
        ):
            raise ValueError("Completed staged evaluation changed")
        rows = read_rows(out / "responses.jsonl")
        expected = {
            (*row_identity(job).values(), sample): job
            for job in jobs
            for sample in range(spec["samples"])
        }
        actual = {}
        for row in rows:
            identity = row_identity(row)
            key = (*identity.values(), row["sample"])
            if (
                key in actual
                or key not in expected
                or any(row[k] != v for k, v in identity.items())
            ):
                raise ValueError("Cached evaluation response identities changed")
            if (
                row["adapter_sha256"] != adapter_hash
                or row["route"] != config["route"]
                or row["parser_version"] != PARSER_VERSION
                or row["logprobs_mode"] != "processed_logprobs"
                or row["seed"] != stable_seed(spec["seed"], identity) % (2**31)
                or row["completion_cap"]
                != min(config["max_completion"], 32768 - len(row["prompt_ids"]))
            ):
                raise ValueError("Cached evaluation response protocol changed")
            actual[key] = row
        if (
            actual.keys() != expected.keys()
            or saved["responses"] != len(rows)
            or saved["problems"] != len(jobs)
        ):
            raise ValueError("Cached evaluation response counts differ from the protocol")
        return
    command = [
        sys.executable,
        "-m",
        "qwen.grpo_evaluate",
        "--suite",
        suite,
        "--stage-name",
        stage,
        "--experiment",
        str(training),
        "--output",
        str(out),
        "--wall-hours",
        str(config["wall_hours"]),
    ]
    if adapter:
        command += ["--adapter", adapter]
    subprocess.run(command, check=True)
    if not summary.exists():
        raise RuntimeError("Evaluation worker returned without a completed summary")
    evaluate(config, training, out, stage, suite, adapter)


def combine_blocks(paths):
    rows = []
    identities = None
    for block, path in enumerate(paths):
        part = read_rows(path)
        paired(part, part)  # Detect duplicated identities before reporting missing samples.
        signatures = {}
        for r in part:
            signatures.setdefault(r["id"], set()).add(
                (r["variant"], r["prompt_sha256"], r["label_sha256"])
            )
        if (
            len(part) != 24
            or set(signatures) != set(PRIMARY + SECONDARY)
            or any(len(v) != 1 for v in signatures.values())
            or any(
                {r["sample"] for r in part if r["id"] == problem} != set(range(4))
                for problem in signatures
            )
        ):
            raise ValueError("Each proof block requires six approved problems with four samples")
        if identities is not None and signatures != identities:
            raise ValueError("Proof problem identities differ between blocks")
        identities = signatures
        for r in part:
            if not 0 <= r["sample"] < 4:
                raise ValueError("Proof blocks must contain four samples per problem")
            rows.append({**r, "sample": 4 * block + r["sample"], "evaluation_block": block})
    # Reuse paired validation to detect duplicate/missing block identities later.
    paired(rows, rows)
    return rows


def proof_packet(base_paths, trained_paths, out):
    sources = {str(p): file_hash(p) for p in [*base_paths, *trained_paths]}
    out.mkdir(parents=True, exist_ok=True)
    frozen_json(out / "sources.json", sources)
    if not (out / "blinded.jsonl").exists():
        pairs = paired(combine_blocks(base_paths), combine_blocks(trained_paths))
        blind(pairs, out)
        protocol = read_json(out / "protocol.json")
        protocol["required_grade_fields"] += [*PROOF_BOOL_FIELDS, "reviewer", "prior_exposure"]
        protocol["primary_problems"] = list(PRIMARY)
        protocol["secondary_problems"] = list(SECONDARY)
        protocol["interpretation"] = (
            "Same-configuration untrained proofs are a meaningful primary signal. "
            "Other-configuration transfer is a distinct secondary endpoint."
        )
        write_json(out / "protocol.json", protocol)


def grade_proofs(out):
    grades = read_rows(out / "grades.jsonl")
    for grade in grades:
        if (
            any(not isinstance(grade.get(k), bool) for k in PROOF_BOOL_FIELDS)
            or not grade.get("reviewer")
            or not isinstance(grade.get("prior_exposure"), bool)
        ):
            raise ValueError("Each proof grade needs Boolean ability fields and reviewer metadata")
        if grade["category"] == "complete" and (
            not grade["core_proved"] or grade["unsupported_core_claim"]
        ):
            raise ValueError("Complete proof conflicts with its core-relation assessment")
    freeze_and_unblind(out)
    key = read_json(out / "identity_key.json")
    result = {}
    for grade in grades:
        identity = key[grade["review_id"]]
        counts = result.setdefault(identity["id"], {}).setdefault(
            identity["model"],
            {
                "n": 0,
                "complete": 0,
                **dict.fromkeys(PROOF_BOOL_FIELDS, 0),
            },
        )
        counts["n"] += 1
        counts["complete"] += grade["category"] == "complete"
        for name in PROOF_BOOL_FIELDS:
            counts[name] += grade[name]
    summary = {"by_problem": result, "endpoints": {}}
    for name, ids in (("same_configuration", PRIMARY), ("other_configuration", SECONDARY)):
        summary["endpoints"][name] = {
            model: sum(result[i][model]["complete"] / result[i][model]["n"] for i in ids) / len(ids)
            for model in ("base", "trained")
        }
    summary["limitation"] = (
        "Exploratory, three problems per endpoint; repetitions are not independent problems. "
        "No claim about concepts absent from pretraining."
    )
    frozen_json(out / "ability_summary.json", summary)
    return summary


def training_review(config, training, out, through):
    """Export final submitted explanations; retain raw traces separately for diagnosis."""
    records, sources = [], {}
    wanted = set(config["training_audit_ids"])
    for i in range(through):
        path = training / f"round-{i:03}/generation/rollouts.json"
        if not path.exists():
            continue
        sources[str(path)] = file_hash(path)
        for r in read_json(path):
            if r["id"] in wanted and r["variant"] == "v0":
                records.append(
                    {
                        "response_id": digest(
                            {
                                "id": r["id"],
                                "variant": r["variant"],
                                "seed": r["seed"],
                                "sample": r["sample"],
                            }
                        )[:20],
                        "id": r["id"],
                        "variant": r["variant"],
                        "sample": r["sample"],
                        "problem": r["problem"],
                        "answer_correct": r["verdict"],
                        "final_answer": final_text(r["raw_text"]),
                        "finish_reason": r["finish_reason"],
                        "source": str(path),
                        "raw_text_sha256": digest(r["raw_text"]),
                    }
                )
    out.mkdir(parents=True, exist_ok=True)
    frozen_json(out / "sources.json", sources)
    frozen_rows(out / "responses.jsonl", records)
    frozen_json(
        out / "protocol.json",
        {
            "responses_sha256": file_hash(out / "responses.jsonl"),
            "selection": "All four v0 answers of 12 preregistered structural configurations; "
            "selected without reward or proof performance. Expected 48 at round 10.",
            "required_fields": [
                "response_id",
                "reasoning_valid",
                "geometric_value",
                "evidence",
                "reviewer",
            ],
            "reasoning_valid": ["yes", "no", "uncertain", "no_final"],
            "geometric_value": ["yes", "no", "uncertain"],
            "scope": "Offline diagnostic only. Never fed into C rewards or proof correctness. "
            "Final explanation validity is distinct from errors retracted within thinking.",
        },
    )


def freeze_training_review(out):
    protocol = read_json(out / "protocol.json")
    if file_hash(out / "responses.jsonl") != protocol["responses_sha256"]:
        raise ValueError("Training review inputs changed")
    rows, grades = read_rows(out / "responses.jsonl"), read_rows(out / "grades.jsonl")
    if len(rows) != len(grades) or {r["response_id"] for r in rows} != {
        g["response_id"] for g in grades
    }:
        raise ValueError("Complete unique training review grades are required")
    for g in grades:
        if (
            g.get("reasoning_valid") not in protocol["reasoning_valid"]
            or g.get("geometric_value") not in protocol["geometric_value"]
            or not g.get("evidence")
            or not g.get("reviewer")
        ):
            raise ValueError("Training review needs validity, geometric value, and evidence")
    receipt = {
        "grades_sha256": file_hash(out / "grades.jsonl"),
        "responses_sha256": file_hash(out / "responses.jsonl"),
    }
    frozen_json(out / "grades_freeze.json", receipt)
    return receipt


def record_decision(root, action, reason, reviewer):
    if action not in {"continue", "finish"}:
        raise ValueError("Unknown scientific review decision")
    if not reason.strip() or not reviewer.strip():
        raise ValueError("Scientific decision needs a rationale and reviewer")
    pending = read_json(root / "REVIEW_REQUIRED.json")
    grade_proofs(root / "interim_review")
    audit = freeze_training_review(root / "training_review")
    decision = {
        "action": action,
        "rationale": reason,
        "reviewer": reviewer,
        "review_state_sha256": digest(pending),
        "proof_grades_sha256": file_hash(root / "interim_review/grades.jsonl"),
        "training_grades_sha256": audit["grades_sha256"],
        "note": "Exploratory resource decision. A null result at round10 does not refute transfer.",
    }
    frozen_json(root / "DECISION.json", decision)
    return decision


def run_study(config, root, config_path):
    training = root / "training"
    if (root / "COMPLETE.json").exists():
        return read_json(root / "COMPLETE.json")
    decision_path = root / "DECISION.json"
    review_path = root / "REVIEW_REQUIRED.json"
    if review_path.exists() and not decision_path.exists():
        pending = read_json(review_path)
        state = progress(training)
        if (
            state["rounds"] != pending["rounds"]
            or file_hash(Path(state["adapter"]) / "adapter_model.safetensors")
            != pending["adapter_sha256"]
            or file_hash(root / "interim_review/blinded.jsonl") != pending["proof_packet_sha256"]
            or file_hash(root / "training_review/responses.jsonl")
            != pending["training_packet_sha256"]
        ):
            raise ValueError("Scientific review checkpoint or inputs changed")
        return {"status": "awaiting_scientific_review", **pending}
    for stage, suite in (("base0", "proof"), ("base1", "proof"), ("base0", "numeric")):
        evaluate(config, training, root / f"{stage}_{suite}", stage, suite, "")

    def train_until(target):
        stop_path = root / "OPERATIONAL_STOP.json"
        if stop_path.exists():
            return False
        while progress(training)["rounds"] < target:
            state = progress(training)
            report = cost_status(config, state, read_json(config["budget_ledger"]))
            write_json(root / "cost_status.json", report)
            if not report["can_afford_next_round_and_evaluation"]:
                frozen_json(
                    root / "OPERATIONAL_STOP.json",
                    {
                        "rounds": state["rounds"],
                        "reason": "operational_fuse_reserve",
                        **report,
                    },
                )
                return False
            journal_path = training / "attempts.json"
            attempts_before = len(read_json(journal_path)) if journal_path.exists() else 0
            try:
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "qwen.grpo_run",
                        "--config",
                        str(config_path),
                        "--output",
                        str(training),
                        "--through-round",
                        str(state["rounds"] + 1),
                    ],
                    check=True,
                )
            except subprocess.CalledProcessError:
                attempts = read_json(journal_path) if journal_path.exists() else []
                if (
                    len(attempts) <= attempts_before
                    or attempts[-1].get("budget_stop") is not True
                    or attempts[-1].get("status") != "failed"
                    or not attempts[-1].get("ended_utc")
                ):
                    raise
                state = progress(training)
                frozen_json(
                    stop_path,
                    {
                        "rounds": state["rounds"],
                        "reason": "worker_budget_stop",
                        "attempt_sha256": digest(attempts[-1]),
                    },
                )
                return False
        return True

    if not decision_path.exists():
        reached = train_until(config["review_round"])
        state = progress(training)
        if not state["adapter"]:
            training_review(config, training, root / "training_review", state["rounds"])
            status = {
                "status": "no_update",
                "rounds": state["rounds"],
                "note": "No parameter update; do not infer proof transfer.",
            }
            frozen_json(root / "NO_UPDATE.json", status)
            return status
        for suite in ("proof", "numeric"):
            evaluate(
                config, training, root / f"interim_{suite}", "interim", suite, state["adapter"]
            )
        proof_packet(
            [root / "base0_proof/responses.jsonl"],
            [root / "interim_proof/responses.jsonl"],
            root / "interim_review",
        )
        frozen_json(
            root / "interim_numeric_summary.json",
            numeric(
                paired(
                    read_rows(root / "base0_numeric/responses.jsonl"),
                    read_rows(root / "interim_numeric/responses.jsonl"),
                )
            ),
        )
        training_review(config, training, root / "training_review", state["rounds"])
        pending = {
            "rounds": state["rounds"],
            "adapter": state["adapter"],
            "adapter_sha256": file_hash(Path(state["adapter"]) / "adapter_model.safetensors"),
            "reached_planned_review": reached,
            "proof_packet_sha256": file_hash(root / "interim_review/blinded.jsonl"),
            "training_packet_sha256": file_hash(root / "training_review/responses.jsonl"),
        }
        frozen_json(root / "REVIEW_REQUIRED.json", pending)
        return {"status": "awaiting_scientific_review", **pending}

    decision = read_json(decision_path)
    pending = read_json(root / "REVIEW_REQUIRED.json")
    # Revalidate grades and their immutable receipt on every continuation.
    record_decision(root, decision["action"], decision["rationale"], decision["reviewer"])
    if decision["review_state_sha256"] != digest(pending):
        raise ValueError("Decision is not for this review checkpoint")
    if decision["action"] == "continue":
        train_until(config["rounds"])
    elif decision["action"] != "finish":
        raise ValueError("Unknown scientific review decision")
    state = progress(training)
    same_as_interim = (
        file_hash(Path(state["adapter"]) / "adapter_model.safetensors") == pending["adapter_sha256"]
    )
    # If finishing at the reviewed checkpoint, reuse its matching 4-answer block.
    final0 = "interim" if same_as_interim else "final0"
    if same_as_interim:
        for suite in ("proof", "numeric"):
            evaluate(
                config, training, root / f"interim_{suite}", "interim", suite, state["adapter"]
            )
    if not same_as_interim:
        for suite in ("proof", "numeric"):
            evaluate(config, training, root / f"final0_{suite}", "final0", suite, state["adapter"])
    evaluate(config, training, root / "final1_proof", "final1", "proof", state["adapter"])
    proof_packet(
        [root / "base0_proof/responses.jsonl", root / "base1_proof/responses.jsonl"],
        [root / f"{final0}_proof/responses.jsonl", root / "final1_proof/responses.jsonl"],
        root / "final_review",
    )
    frozen_json(
        root / "final_numeric_summary.json",
        numeric(
            paired(
                read_rows(root / "base0_numeric/responses.jsonl"),
                read_rows(root / f"{final0}_numeric/responses.jsonl"),
            )
        ),
    )
    budget = read_json(config["budget_ledger"])
    complete = {
        "status": "generation_complete_grading_pending",
        "rounds": state["rounds"],
        "adapter": state["adapter"],
        "reward_condition": "C",
        "gpu_hours_including_preparation": sum(j["charged_seconds"] for j in budget["jobs"]) / 3600,
        "proof_grading": "96 blinded answers in final_review; 48 interim answers were exploratory.",
        "future_reward_arms": "Not started. Compare matched continuation controls separately.",
    }
    frozen_json(root / "COMPLETE.json", complete)
    return complete


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--output", default=DEFAULT_ROOT)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--decision", choices=["continue", "finish"])
    ap.add_argument("--reason", default="")
    ap.add_argument("--reviewer", default="")
    ap.add_argument("--grade", choices=["interim", "final"])
    args = ap.parse_args()
    config, root = read_json(args.config), Path(args.output).resolve()
    if Path(args.config).resolve() != Path(config["config_path"]).resolve():
        raise ValueError("CLI config path differs from the frozen configuration target")
    gate = read_json(config["readiness_gate"])
    budget = read_json(config["budget_ledger"])
    validate(config, gate, budget)
    groups = prepare(config, root / "training")
    first = [r for g in groups[:10] for r in g]
    if len(groups) != 37 or len({r["id"] for r in first}) != 37:
        raise ValueError("First ten rounds must cover all37 approved configurations")
    frozen_json(
        root / "PREPARED.json",
        {
            "config_sha256": file_hash(args.config),
            "readiness_sha256": file_hash(config["readiness_gate"]),
            "training_manifest_sha256": file_hash(root / "training/manifest.json"),
            "budget_created_utc": budget["created_utc"],
        },
    )
    if args.grade:
        print(json.dumps(grade_proofs(root / f"{args.grade}_review"), ensure_ascii=False))
    if args.decision:
        print(
            json.dumps(
                record_decision(root, args.decision, args.reason, args.reviewer), ensure_ascii=False
            )
        )
    if args.run:
        print(json.dumps(run_study(config, root, args.config), ensure_ascii=False))
    elif not args.grade and not args.decision:
        print(
            json.dumps(
                {
                    "prepared": str(root / "PREPARED.json"),
                    "gpu_experiment_started": False,
                    "cost": gate["cost"],
                    "remaining_operational_hours": remaining(budget) / 3600,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
