import json
import subprocess
import sys

import pytest

from qwen.experiment_budget import initialize, remaining, run_budgeted


def test_budget_counts_failed_and_completed_workers_across_restart(tmp_path):
    ledger = tmp_path / "budget.json"
    initialize(ledger, hours=1, preparation_hours=0.5)
    run_budgeted([sys.executable, "-c", "pass"], tmp_path / "a.log", ledger, "preparation", 2)
    with pytest.raises(RuntimeError, match="exited"):
        run_budgeted(
            [sys.executable, "-c", "raise SystemExit(2)"], tmp_path / "b.log", ledger, "training", 2
        )
    state = initialize(ledger, hours=1, preparation_hours=0.5)
    assert [j["status"] for j in state["jobs"]] == ["complete", "failed"]
    assert remaining(state) < 3600
    assert remaining(state, "preparation") < 1800
    with pytest.raises(ValueError, match="immutable"):
        initialize(ledger, hours=2)


def test_reserving_evaluation_budget_prevents_training_launch(tmp_path):
    ledger = tmp_path / "budget.json"
    initialize(ledger, hours=1)
    with pytest.raises(TimeoutError, match="reserved"):
        run_budgeted(
            [sys.executable, "-c", "pass"],
            tmp_path / "no.log",
            ledger,
            "training",
            reserve_seconds=3600,
        )
    assert not (tmp_path / "no.log").exists()


def test_deadline_kills_worker_and_keeps_charge(tmp_path):
    ledger = tmp_path / "budget.json"
    initialize(ledger)
    with pytest.raises(subprocess.TimeoutExpired):
        run_budgeted(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            tmp_path / "timeout.log",
            ledger,
            "preparation",
            0.5,
        )
    state = json.loads(ledger.read_text())
    assert state["jobs"][0]["status"] == "failed"
    assert 0 < state["jobs"][0]["charged_seconds"] < 2


def test_stale_running_entry_is_not_silently_free(tmp_path):
    ledger = tmp_path / "budget.json"
    state = initialize(ledger)
    state["jobs"].append({"status": "running", "charged_seconds": 0})
    with pytest.raises(ValueError, match="Unfinished"):
        remaining(state)


def test_sampling_correction_matches_direct_weighted_gradient():
    torch = pytest.importorskip("torch")
    from qwen.grpo_loss import sampling_correction, token_policy_loss

    old = torch.tensor([[-2.0, -1.0, -0.5]])
    sampling = old - torch.tensor([[0.2, -0.2, 1.0]])
    weights, metrics = sampling_correction(old, sampling)
    torch.testing.assert_close(weights, torch.tensor([[0.2, -0.2, 1.0]]).exp().clamp(max=2))
    x = old.clone().requires_grad_()
    loss = token_policy_loss(
        x, old, torch.tensor([0.5]), torch.ones_like(x), 3, importance_weights=weights
    )
    loss.backward()
    torch.testing.assert_close(x.grad, -0.5 * weights / 3)
    assert metrics["clipped_fraction"] == pytest.approx(1 / 3)


def test_scaled_half_precision_head_matches_dense_autograd():
    torch = pytest.importorskip("torch")
    from qwen.grpo_loss import frozen_head_logps, token_policy_loss

    torch.manual_seed(32)
    hidden = torch.randn(2, 7, 9, dtype=torch.float16, requires_grad=True)
    weight = torch.randn(29, 9, dtype=torch.float16)
    targets = torch.randint(29, (2, 7))
    logits = (hidden @ weight.T).float() / 0.6
    dense = logits.log_softmax(-1).gather(-1, targets[..., None]).squeeze(-1)
    old = dense.detach()
    importance = torch.linspace(0.7, 1.3, 14).reshape(2, 7)
    adv = torch.tensor([0.5, -0.5])
    mask = torch.tensor([[1, 1, 1, 0, 0, 0, 0], [1, 1, 1, 1, 1, 1, 1]])
    reference_loss = token_policy_loss(dense, old, adv, mask, 10, importance_weights=importance)
    reference = torch.autograd.grad(reference_loss * 1024, hidden)[0]
    chunked = hidden.detach().clone().requires_grad_()
    lp = frozen_head_logps(chunked, weight, targets, chunk_size=3)
    loss = token_policy_loss(lp, old, adv, mask, 10, importance_weights=importance)
    (loss * 1024).backward()
    # FP16 cancellation makes relative error at individual near-zero entries
    # misleading. Require the whole gradient error to stay below one FP16
    # epsilon; this still detects a missing scale, denominator or IS weight.
    relative_error = (chunked.grad.float() - reference.float()).norm() / reference.float().norm()
    assert relative_error < torch.finfo(torch.float16).eps
    torch.testing.assert_close(lp, dense, rtol=1e-5, atol=1e-5)
    assert torch.isfinite(chunked.grad).all()
