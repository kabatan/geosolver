"""Regressions for data identity, reward boundaries and real token gradients."""

import json

import pytest

from qwen.diagnostics import problem_identity, resume_key, resume_keys, summarize
from qwen.grpo_stage import row_identity


def test_variants_do_not_collapse_on_resume(tmp_path):
    rows = [
        {"id": "H01", "variant": v, "problem": p, "answer_exact": a}
        for v, p, a in [("v0", "length=2", "4"), ("v1", "length=3", "9")]
    ]
    stored = [{**r, **problem_identity(r), "sample": 0} for r in rows]
    path = tmp_path / "raw.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in stored))
    assert len(resume_keys(path, rows)) == 2
    assert resume_key(stored[0]) != resume_key(stored[1])
    rows[1]["answer_exact"] = "10"
    with pytest.raises(ValueError, match="mismatch"):
        resume_keys(path, rows)


def test_legacy_generation_cannot_be_silently_resumed(tmp_path):
    path = tmp_path / "old.jsonl"
    path.write_text(json.dumps({"id": "H01", "sample": 0}))
    with pytest.raises(ValueError, match="Legacy"):
        resume_keys(path, [{"id": "H01", "problem": "x", "answer_exact": "1"}])


def test_summary_groups_by_actual_numeric_problem(tmp_path):
    path = tmp_path / "raw.jsonl"
    rows = []
    for v, verdict in [("v0", True), ("v1", False)]:
        row = {"id": "H01", "variant": v, "problem": v, "answer_exact": "1"}
        rows.append(
            {
                **row,
                **problem_identity(row),
                "sample": 0,
                "verdict": verdict,
                "output_tokens": 2,
                "finish_reason": "eos",
                "batch_elapsed_seconds": 1,
            }
        )
    path.write_text("\n".join(json.dumps(r) for r in rows))
    report = summarize(path)
    assert report["configs"] == 2
    assert not report["configs_mixed"]


def test_identity_includes_actual_prompt_and_label():
    row = {"id": "H01", "variant": "v0", "problem": "a", "answer_exact": "1"}
    assert row_identity(row) != row_identity({**row, "problem": "b"})
    assert row_identity(row) != row_identity({**row, "answer_exact": "2"})


def test_checkpoint_resume_detects_optimizer_tampering(tmp_path):
    from qwen.common import file_hash
    from qwen.grpo_run import verify_checkpoint

    adapter = tmp_path / "adapter/adapter_model.safetensors"
    adapter.parent.mkdir()
    adapter.write_bytes(b"saved adapter fixture")
    optimizer = tmp_path / "optimizer.pt"
    optimizer.write_bytes(b"saved optimizer fixture")
    (tmp_path / "COMPLETE.json").write_text(json.dumps({"adapter_sha256": file_hash(adapter)}))
    first = verify_checkpoint(tmp_path)
    assert verify_checkpoint(tmp_path) == first
    optimizer.write_bytes(b"wrong optimizer from another run")
    with pytest.raises(ValueError, match="changed"):
        verify_checkpoint(tmp_path)
    optimizer.write_bytes(b"saved optimizer fixture")
    (tmp_path / "detail-000.json").write_text(json.dumps({"engine_max_abs_error": 0.02}))
    with pytest.raises(ValueError, match="logprob mismatch"):
        verify_checkpoint(tmp_path)


def test_worker_deadline_stops_only_its_process_group(tmp_path):
    import subprocess
    import sys

    from qwen.grpo_run import run_worker

    with pytest.raises(subprocess.TimeoutExpired):
        run_worker(
            [sys.executable, "-c", "import time; time.sleep(10)"], tmp_path / "worker.log", 1.0
        )


def test_blind_review_requires_all_grades_and_preserves_key(tmp_path):
    from qwen.grpo_compare import blind, freeze_and_unblind

    row = {
        "id": "EV02",
        "sample": 0,
        "problem": "Prove it.",
        "raw_text": "A full final solution.",
        "finish_reason": "stop",
    }
    blind([(row, row)], tmp_path)
    records = [json.loads(line) for line in (tmp_path / "blinded.jsonl").read_text().splitlines()]
    grades = [
        {
            "review_id": r["review_id"],
            "category": "core_gap",
            "method": "coordinates",
            "auxiliary_relation_proved": False,
            "evidence": "Core relation is missing.",
        }
        for r in records
    ]
    path = tmp_path / "grades.jsonl"
    path.write_text(json.dumps(grades[0]))
    with pytest.raises(ValueError, match="Complete unique"):
        freeze_and_unblind(tmp_path)
    assert not (tmp_path / "grades_freeze.json").exists()
    path.write_text("\n".join(json.dumps(g) for g in grades))
    freeze_and_unblind(tmp_path)
    assert (tmp_path / "proof_summary.json").exists()
    grades[0]["category"] = "complete"
    path.write_text("\n".join(json.dumps(g) for g in grades))
    with pytest.raises(ValueError, match="Grades changed"):
        freeze_and_unblind(tmp_path)


def test_numeric_comparison_rejects_mismatched_prompts():
    from qwen.grpo_compare import paired

    row = {
        "id": "H01",
        "variant": "d1",
        "prompt_sha256": "a",
        "label_sha256": "b",
        "sample": 0,
        "seed": 1,
        "parser_version": "exact-numeric-v2",
        "completion_cap": 32512,
        "prompt_ids": [1, 2],
    }
    assert len(paired([row], [row])) == 1
    with pytest.raises(ValueError, match="inputs"):
        paired([row], [{**row, "prompt_sha256": "different problem"}])
    with pytest.raises(ValueError, match="route"):
        paired([{**row, "route": "fp16_native"}], [{**row, "route": "fp32"}])


def test_token_loss_and_chunked_backward():
    torch = pytest.importorskip("torch")
    from qwen.grpo_loss import frozen_head_logps, token_policy_loss

    torch.manual_seed(4)
    hidden = torch.randn(2, 6, 7, requires_grad=True)
    weight = torch.randn(17, 7)
    targets = torch.randint(17, (2, 6))
    mask = torch.tensor([[1, 1, 0, 0, 0, 0], [1, 1, 1, 1, 1, 1]])
    advantage = torch.tensor([0.5, -0.5])
    dense = (hidden @ weight.T / 0.6).log_softmax(-1).gather(-1, targets[..., None]).squeeze(-1)
    old = dense.detach()
    reference = torch.autograd.grad(token_policy_loss(dense, old, advantage, mask, 8), hidden)[0]
    x = hidden.detach().clone().requires_grad_()
    for i in range(2):
        logps = frozen_head_logps(x[i : i + 1], weight, targets[i : i + 1], chunk_size=2)
        token_policy_loss(
            logps, old[i : i + 1], advantage[i : i + 1], mask[i : i + 1], 8
        ).backward()
    torch.testing.assert_close(x.grad, reference, atol=1e-7, rtol=1e-5)
    y = hidden.detach().clone().requires_grad_()
    logps = frozen_head_logps(y, weight, targets, chunk_size=3)
    reverse = torch.autograd.grad(token_policy_loss(logps, old, -advantage, mask, 8), y)[0]
    torch.testing.assert_close(reverse, -reference, atol=1e-7, rtol=1e-5)
