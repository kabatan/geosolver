"""Protocol, cached-export and budget-stop regressions; no model/GPU loads."""

import copy
import subprocess

import pytest
from test_staged_study import fixture_study, supply_grades

from qwen.answer_check import PARSER_VERSION
from qwen.common import digest, file_hash, read_json, stable_seed, write_json
from qwen.grpo_compare import read_rows
from qwen.grpo_stage import row_identity
from qwen.staged_readiness import REQUIRED_TESTED_PATHS, validate_test_evidence
from qwen.staged_study import (
    DEFAULT_CONFIG,
    PRIMARY,
    SECONDARY,
    combine_blocks,
    evaluate,
    frozen_rows,
    record_decision,
    run_study,
    validate_evaluation_inputs,
    validate_evaluation_protocol,
)


@pytest.mark.parametrize("change", ["samples", "paired_seed", "same_block_seed", "extra_stage"])
def test_cost_contract_rejects_changed_sampling_protocol(change):
    config = read_json(DEFAULT_CONFIG)
    stages = config["evaluation_stages"]
    if change == "samples":
        stages["base0"]["proof"]["samples"] = 8
    elif change == "paired_seed":
        stages["interim"]["numeric"]["seed"] += 1
    elif change == "same_block_seed":
        stages["base1"]["proof"]["seed"] = stages["final1"]["proof"]["seed"] = stages["base0"][
            "proof"
        ]["seed"]
    else:
        stages["extra"] = copy.deepcopy(stages["base0"])
    with pytest.raises(ValueError):
        validate_evaluation_protocol(config)


def test_preparation_requires_all_costed_input_problems(tmp_path):
    config = read_json(DEFAULT_CONFIG)
    validate_evaluation_protocol(config)
    validate_evaluation_inputs(config)
    reduced = tmp_path / "numeric.jsonl"
    frozen_rows(reduced, read_rows(config["evaluation_suites"]["numeric"])[:-1])
    config["evaluation_suites"]["numeric"] = str(reduced)
    with pytest.raises(ValueError, match="exactly 12"):
        validate_evaluation_inputs(config)


def proof_rows(seed=10):
    rows = []
    for problem in PRIMARY + SECONDARY:
        job = {"id": problem, "variant": "v0", "problem": "Prove " + problem}
        for sample in range(4):
            rows.append(
                {
                    **job,
                    **row_identity(job),
                    "sample": sample,
                    "seed": stable_seed(seed, row_identity(job)) % (2**31),
                    "parser_version": PARSER_VERSION,
                    "prompt_ids": [1],
                    "completion_cap": 32512,
                    "adapter_sha256": "base",
                    "route": "fp16_native",
                    "logprobs_mode": "processed_logprobs",
                    "raw_text": "Proof.",
                    "finish_reason": "stop",
                }
            )
    return rows


def test_missing_proof_samples_and_changed_block_identities_are_rejected(tmp_path):
    first, second = tmp_path / "first.jsonl", tmp_path / "second.jsonl"
    rows = proof_rows()
    frozen_rows(first, rows)
    frozen_rows(second, rows[:-1])
    with pytest.raises(ValueError, match="six approved"):
        combine_blocks([first, second])
    second.unlink()
    changed = proof_rows(11)
    for row in changed:
        if row["id"] == "N01":
            row["prompt_sha256"] = "different problem"
    frozen_rows(second, changed)
    with pytest.raises(ValueError, match="identities differ"):
        combine_blocks([first, second])


def cached_evaluation(tmp_path):
    config = read_json(DEFAULT_CONFIG)
    config["evaluation_suites"]["proof"] = "fixtures/proof.jsonl"
    stage, suite = "base0", "proof"
    spec = config["evaluation_stages"][stage][suite]
    training, out = tmp_path / "training", tmp_path / "evaluation"
    rows = proof_rows(spec["seed"])
    jobs = [{k: row[k] for k in ("id", "variant", "problem")} for row in rows[::4]]
    source = training / "source/fixtures/proof.jsonl"
    frozen_rows(source, jobs)
    write_json(
        training / "manifest.json",
        {
            "evaluation_sha256": {"fixtures/proof.jsonl": file_hash(source)},
            "source_sha256": {"qwen/grpo_stage.py": "core source hash"},
        },
    )
    write_json(out / "jobs.json", jobs)
    frozen_rows(out / "responses.jsonl", rows)
    write_json(
        out / "generation/generation_manifest.json",
        {
            "jobs_sha256": file_hash(out / "jobs.json"),
            "adapter_sha256": "base",
            "samples": 4,
            "seed": spec["seed"],
            "route": "fp16_native",
            "kv": "auto",
            "max_completion": 32512,
            "max_seqs": 4,
            "parser_version": PARSER_VERSION,
            "source_sha256": "core source hash",
        },
    )
    write_json(
        out / "summary.json",
        {
            "response_sha256": file_hash(out / "responses.jsonl"),
            "suite": suite,
            "stage_name": stage,
            "responses": 24,
            "problems": 6,
        },
    )
    return config, training, out, stage, suite


@pytest.mark.parametrize("change", ["jobs", "route", "missing_response", "response_policy", "cap"])
def test_cached_evaluation_checks_frozen_identity_and_full_sampling_protocol(tmp_path, change):
    config, training, out, stage, suite = cached_evaluation(tmp_path)
    evaluate(config, training, out, stage, suite, "")
    if change == "jobs":
        jobs = read_json(out / "jobs.json")
        jobs[0]["problem"] = "Wrong problem"
        write_json(out / "jobs.json", jobs)
    elif change in {"route", "cap"}:
        context = read_json(out / "generation/generation_manifest.json")
        context["route" if change == "route" else "max_completion"] = (
            "fp32" if change == "route" else 8192
        )
        write_json(out / "generation/generation_manifest.json", context)
    else:
        rows = read_rows(out / "responses.jsonl")
        if change == "missing_response":
            rows.pop()
        else:
            rows[0]["adapter_sha256"] = "wrong policy"
        (out / "responses.jsonl").unlink()
        frozen_rows(out / "responses.jsonl", rows)
        summary = read_json(out / "summary.json")
        summary.update(response_sha256=file_hash(out / "responses.jsonl"), responses=len(rows))
        write_json(out / "summary.json", summary)
    with pytest.raises(ValueError):
        evaluate(config, training, out, stage, suite, "")


def test_early_operational_stop_pauses_without_retraining_and_reuses_review_policy(
    tmp_path, monkeypatch
):
    import qwen.staged_study as study

    config, root, state, calls = fixture_study(tmp_path, monkeypatch)
    original = study.cost_status

    def cost(config, state, budget):
        result = original(config, state, budget)
        result["can_afford_next_round_and_evaluation"] = state["rounds"] < 5
        return result

    monkeypatch.setattr(study, "cost_status", cost)
    first = run_study(config, root, "fixture.json")
    assert first["rounds"] == 5 and not first["reached_planned_review"]
    before = digest(calls)
    assert run_study(config, root, "fixture.json") == first
    assert digest(calls) == before
    supply_grades(root)
    record_decision(root, "continue", "Consider more data", "reviewer")
    # Evaluation expenditures can change after the immutable training-stop receipt.
    write_json(
        config["budget_ledger"],
        {"limit_seconds": 48 * 3600, "jobs": [{"status": "complete", "charged_seconds": 3600}]},
    )
    end = run_study(config, root, "fixture.json")
    assert end["rounds"] == 5 and calls["train"] == list(range(1, 6))
    assert len(read_rows(root / "final_review/blinded.jsonl")) == 96


@pytest.mark.parametrize("budget_stop", [True, False])
def test_worker_budget_failure_preserves_stable_checkpoint_but_other_failures_propagate(
    tmp_path, monkeypatch, budget_stop
):
    import qwen.staged_study as study

    config, root, state, calls = fixture_study(tmp_path, monkeypatch)
    original = study.subprocess.run

    def worker(command, check):
        target = int(command[command.index("--through-round") + 1])
        if target == 3:
            write_json(
                root / "training/attempts.json",
                [
                    {
                        "status": "failed",
                        "ended_utc": "finished",
                        "budget_stop": budget_stop,
                    }
                ],
            )
            raise subprocess.CalledProcessError(1, command)
        return original(command, check)

    monkeypatch.setattr(study.subprocess, "run", worker)
    if budget_stop:
        result = run_study(config, root, "fixture.json")
        assert result["rounds"] == 2 and result["status"] == "awaiting_scientific_review"
        assert read_json(root / "OPERATIONAL_STOP.json")["reason"] == "worker_budget_stop"
        supply_grades(root)
        record_decision(root, "finish", "Time fuse", "reviewer")
        assert run_study(config, root, "fixture.json")["rounds"] == 2
    else:
        with pytest.raises(subprocess.CalledProcessError):
            run_study(config, root, "fixture.json")
        assert not (root / "OPERATIONAL_STOP.json").exists()
    assert calls["train"] == [1, 2]


def test_unknown_decision_and_incomplete_test_receipts_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="Unknown"):
        record_decision(tmp_path, "expand", "reason", "reviewer")
    receipt = {
        "exit_code": 0,
        "integration_tests_passed": True,
        "lint_passed": True,
        "source_sha256": {},
    }
    with pytest.raises(ValueError, match="cover"):
        validate_test_evidence(receipt)
    receipt["source_sha256"] = {p: file_hash(p) for p in REQUIRED_TESTED_PATHS}
    validate_test_evidence(receipt)
    receipt["source_sha256"]["qwen/staged_study.py"] = "stale"
    with pytest.raises(ValueError, match="Source changed"):
        validate_test_evidence(receipt)
