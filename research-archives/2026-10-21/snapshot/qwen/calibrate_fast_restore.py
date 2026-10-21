"""Restore a real FP16 update, then exercise full-context backward without stepping."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def main():
    import torch

    from .common import write_json
    from .grpo_loss import token_policy_loss
    from .grpo_policy import completion_logps, load_policy, trainable

    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("--round", required=True)
    args = ap.parse_args()
    root = Path(args.round)
    started = time.monotonic()
    rows = json.loads((root / "generation/rollouts.json").read_text())
    model, _ = load_policy(root / "update/adapter", precision="float16")
    parameters = trainable(model)
    optimizer = torch.optim.AdamW(parameters, lr=1e-6, weight_decay=0, eps=1e-8)
    saved = torch.load(root / "update/optimizer.pt", map_location="cpu", weights_only=True)
    optimizer.load_state_dict(saved)
    restored = optimizer.state_dict()
    optimizer_error = max(
        (value - restored["state"][key][name].cpu()).abs().max().item()
        for key, state in saved["state"].items()
        for name, value in state.items()
        if isinstance(value, torch.Tensor)
    )
    scaler_saved = json.loads((root / "update/scaler.json").read_text())
    scaler = torch.amp.GradScaler("cuda", init_scale=1024, growth_interval=1000000)
    scaler.load_state_dict(scaler_saved)
    assert scaler.state_dict() == scaler_saved
    errors = []
    with torch.no_grad():
        for path in sorted((root / "update").glob("detail-*.json")):
            detail = json.loads(path.read_text())
            actual = completion_logps(model, rows[detail["index"]]).cpu().flatten()
            expected = torch.tensor(detail["new_logps"])
            errors.append(
                {"index": detail["index"], "max_abs_error": (actual - expected).abs().max().item()}
            )
    reload_pass = optimizer_error == 0 and max(e["max_abs_error"] for e in errors) <= 1e-4
    report = {
        "optimizer_max_abs_error": optimizer_error,
        "scaler_exact_restore": True,
        "logprob_comparisons": errors,
        "optimizer_steps": sorted({s["step"].item() for s in saved["state"].values()}),
        "reload_pass": reload_pass,
        "restore_seconds": time.monotonic() - started,
    }
    write_json(root / "restore_capacity.json", report)
    assert reload_pass, report
    # Force the complete model context, independent of natural answer lengths.
    row = dict(max(rows, key=lambda r: len(r["completion_ids"])))
    cap = 32768 - len(row["prompt_ids"])
    row["completion_ids"] = (row["completion_ids"] * (cap // len(row["completion_ids"]) + 1))[:cap]
    optimizer.zero_grad(set_to_none=True)
    torch.cuda.reset_peak_memory_stats()
    start_capacity = time.monotonic()
    lp = completion_logps(model, row, offload=True)
    loss = token_policy_loss(
        lp, lp.detach(), torch.tensor([0.5], device="cuda"), torch.ones_like(lp), cap
    )
    scaler.scale(loss).backward()
    scaler.unscale_(optimizer)
    norm = torch.nn.utils.clip_grad_norm_(parameters, 1, error_if_nonfinite=True)
    torch.cuda.synchronize()
    report.update(
        {
            "context_tokens": len(row["prompt_ids"]) + cap,
            "optimizer_steps_performed": 0,
            "gradient_norm": norm.item(),
            "peak_gpu_gib": torch.cuda.max_memory_allocated() / 2**30,
            "capacity_seconds": time.monotonic() - start_capacity,
            "scope": "Reload against full pre-save logprobs; synthetic capacity fixture.",
            "capacity_pass": True,
        }
    )
    write_json(root / "restore_capacity.json", report)
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
