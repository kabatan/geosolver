"""Exercise the scientific pause/resume flow without allocating a GPU."""

import json

import pytest

from qwen.common import digest, file_hash, read_json, write_json
from qwen.grpo_compare import read_rows
from qwen.grpo_stage import row_identity
from qwen.staged_readiness import inherit_budget
from qwen.staged_study import (
    DEFAULT_CONFIG,
    PRIMARY,
    PROOF_BOOL_FIELDS,
    SECONDARY,
    combine_blocks,
    cost_status,
    frozen_rows,
    grade_proofs,
    plan_cost,
    record_decision,
    run_study,
)


def test_plan_cost_uses_proof_blocks_and_soft_guideline():
    config = read_json(DEFAULT_CONFIG)
    cost = plan_cost(config, 0.685)
    assert 12 < cost["first_review_total_hours"] < 15
    assert 34 < cost["full_study_total_hours"] < 37
    assert cost["final_evaluation_cap_hours"] < config["evaluation_reserve_hours"]
    state = dict(
        rounds=10,
        tokens=3520000,
        generation_seconds=22000,
        generated_responses=160,
        update_seconds=2400,
        mixed_groups=2,
    )
    budget = dict(
        limit_seconds=48 * 3600, jobs=[dict(status="complete", charged_seconds=14 * 3600)]
    )
    status = cost_status(config, state, budget)
    assert status["can_afford_next_round_and_evaluation"]
    # Sparse mixed rewards is a scientific-review datum, not an automatic rejection.
    assert status["mixed_groups"] == 2


def test_migration_preserves_spent_time_and_rejects_research_fork(tmp_path):
    old, new = tmp_path / "old.json", tmp_path / "new.json"
    state = dict(
        limit_seconds=40 * 3600,
        preparation_limit_seconds=7200,
        created_utc="old",
        jobs=[dict(category="preparation", charged_seconds=2466, status="complete")],
    )
    write_json(old, state)
    migrated = inherit_budget(old, new, 48)
    assert migrated["jobs"] == state["jobs"]
    assert read_json(old) == state
    assert inherit_budget(old, new, 48) == migrated
    migrated["jobs"] = []
    write_json(new, migrated)
    with pytest.raises(ValueError, match="charges"):
        inherit_budget(old, new, 48)
    state["jobs"][0]["category"] = "training"
    write_json(old, state)
    with pytest.raises(ValueError, match="research GPU"):
        inherit_budget(old, tmp_path / "third.json", 48)


def fixture_study(tmp_path, monkeypatch):
    import qwen.staged_study as study

    root = tmp_path / "study"
    root.mkdir()
    config = read_json(DEFAULT_CONFIG)
    config["budget_ledger"] = str(tmp_path / "budget.json")
    write_json(config["budget_ledger"], {"limit_seconds": 48 * 3600, "jobs": []})
    state = dict(
        rounds=0,
        adapter="",
        tokens=0,
        generation_seconds=0,
        generated_responses=0,
        update_seconds=0,
        mixed_groups=0,
    )
    calls = {"train": [], "eval": []}
    monkeypatch.setattr(study, "progress", lambda training: dict(state))

    def train(command, check):
        assert check
        through = int(command[command.index("--through-round") + 1])
        assert through == state["rounds"] + 1
        calls["train"].append(through)
        adapter = root / f"adapter-{through}"
        adapter.mkdir()
        (adapter / "adapter_model.safetensors").write_bytes(str(through).encode())
        state.update(
            rounds=through,
            adapter=str(adapter),
            tokens=through * 16 * 22000,
            generation_seconds=through * 16 * 22000 / 188.85,
            generated_responses=through * 16,
            update_seconds=through * 240,
            mixed_groups=through * 2,
        )

    monkeypatch.setattr(study.subprocess, "run", train)

    def evaluate(config, training, out, stage, suite, adapter):
        path = out / "responses.jsonl"
        if path.exists():
            return
        calls["eval"].append((stage, suite))
        spec = config["evaluation_stages"][stage][suite]
        rows = []
        for problem_id in PRIMARY + SECONDARY if suite == "proof" else ("H01", "DA01"):
            job = dict(id=problem_id, variant="v0", problem="Prove " + problem_id)
            if suite == "numeric":
                job["answer_exact"] = "1"
            for sample in range(spec["samples"]):
                rows.append(
                    {
                        **job,
                        **row_identity(job),
                        "sample": sample,
                        "seed": spec["seed"],
                        "parser_version": "test",
                        "prompt_ids": [1],
                        "completion_cap": 32512,
                        "route": "fp16_native",
                        "logprobs_mode": "processed_logprobs",
                        "finish_reason": "stop",
                        "raw_text": "thinking</think> Valid proof.",
                        "verdict": bool(adapter),
                    }
                )
        frozen_rows(path, rows)

    monkeypatch.setattr(study, "evaluate", evaluate)

    def training_review(config, training, out, through):
        rows = [{"response_id": str(i)} for i in range(48)]
        frozen_rows(out / "responses.jsonl", rows)
        write_json(
            out / "protocol.json",
            {
                "responses_sha256": file_hash(out / "responses.jsonl"),
                "reasoning_valid": ["yes", "no", "uncertain", "no_final"],
                "geometric_value": ["yes", "no", "uncertain"],
            },
        )

    monkeypatch.setattr(study, "training_review", training_review)
    return config, root, state, calls


def supply_grades(root, phase="interim"):
    packet = root / f"{phase}_review"
    grades = [
        {
            "review_id": r["review_id"],
            "category": "complete",
            "method": "coordinates",
            "auxiliary_relation_proved": True,
            "evidence": "General calculation checked",
            **dict.fromkeys(PROOF_BOOL_FIELDS, True),
            "unsupported_core_claim": False,
            "reviewer": "test reviewer",
            "prior_exposure": False,
        }
        for r in read_rows(packet / "blinded.jsonl")
    ]
    frozen_rows(packet / "grades.jsonl", grades)
    if phase == "interim":
        audit = root / "training_review"
        frozen_rows(
            audit / "grades.jsonl",
            [
                {
                    **r,
                    "reasoning_valid": "yes",
                    "geometric_value": "no",
                    "evidence": "Checked",
                    "reviewer": "test reviewer",
                }
                for r in read_rows(audit / "responses.jsonl")
            ],
        )


@pytest.mark.parametrize("action,target,eval_calls", [("continue", 37, 8), ("finish", 10, 6)])
def test_pause_review_resume_and_final_reuses_exact_policy(
    tmp_path, monkeypatch, action, target, eval_calls
):
    config, root, state, calls = fixture_study(tmp_path, monkeypatch)
    first = run_study(config, root, "test_config.json")
    assert first["status"] == "awaiting_scientific_review"
    assert state["rounds"] == 10
    assert calls["train"] == list(range(1, 11))
    assert len(read_rows(root / "interim_review/blinded.jsonl")) == 48
    with pytest.raises(FileNotFoundError):
        record_decision(root, action, "Exploratory judgement", "reviewer")
    supply_grades(root)
    record_decision(root, action, "Exploratory judgement", "reviewer")
    end = run_study(config, root, "test_config.json")
    assert state["rounds"] == target
    assert len(calls["eval"]) == eval_calls
    assert len(read_rows(root / "final_review/blinded.jsonl")) == 96
    assert end["reward_condition"] == "C"
    before = digest(calls)
    assert run_study(config, root, "test_config.json") == end
    assert digest(calls) == before
    supply_grades(root, "final")
    summary = grade_proofs(root / "final_review")
    assert summary["by_problem"]["N01"]["base"]["n"] == 8
    assert summary["endpoints"]["same_configuration"]["trained"] == 1


def test_changed_review_prevents_continuation(tmp_path, monkeypatch):
    config, root, state, calls = fixture_study(tmp_path, monkeypatch)
    run_study(config, root, "test_config.json")
    supply_grades(root)
    record_decision(root, "continue", "Reason", "reviewer")
    path = root / "interim_review/grades.jsonl"
    grades = read_rows(path)
    grades[0]["category"] = "core_gap"
    path.write_text("".join(json.dumps(r) + "\n" for r in grades))
    with pytest.raises(ValueError, match="Grades changed"):
        run_study(config, root, "test_config.json")
    assert state["rounds"] == 10


def test_frozen_numeric_selection_is_exact_subset():
    config = read_json(DEFAULT_CONFIG)
    rows = read_rows(config["evaluation_suites"]["numeric"])
    full = {
        r["id"]: r for r in read_rows("benchmarks/humpty_configurations_v2/eval_variants.jsonl")
    }
    assert len(rows) == len({r["id"] for r in rows}) == 12
    assert [r["id"] for r in rows] == config["training_audit_ids"]
    assert all(r == full[r["id"]] for r in rows)


def test_duplicate_proof_block_identity_is_rejected(tmp_path):
    # A repeated sample within one block is not a second independent answer.
    r = dict(
        id="N01",
        variant="v0",
        prompt_sha256="a",
        label_sha256="b",
        sample=0,
        seed=1,
        parser_version="x",
        completion_cap=1,
        prompt_ids=[1],
    )
    frozen_rows(tmp_path / "bad.jsonl", [r, r])
    with pytest.raises(ValueError, match="Duplicate"):
        combine_blocks([tmp_path / "bad.jsonl"])
