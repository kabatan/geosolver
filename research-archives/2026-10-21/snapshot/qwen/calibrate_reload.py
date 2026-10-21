"""Check a real saved optimizer/adapter against pre-save long-token logprobs."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch

from .common import write_json
from .grpo_loss import frozen_head_logps
from .grpo_policy import completion_hidden, load_policy, trainable


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("--round", default="qwen/.runtime/exp02_tech/live/round-000")
    args = ap.parse_args()
    root = Path(args.round)
    started = time.monotonic()
    rows = json.loads((root / "generation/rollouts.json").read_text())
    model, _ = load_policy(root / "update/adapter")
    parameters = trainable(model)
    optimizer = torch.optim.AdamW(parameters, lr=1e-6, weight_decay=0, eps=1e-8)
    saved = torch.load(root / "update/optimizer.pt", map_location="cpu", weights_only=True)
    optimizer.load_state_dict(saved)
    restored = optimizer.state_dict()
    optimizer_error = 0.0
    for key, state in saved["state"].items():
        for name, value in state.items():
            if isinstance(value, torch.Tensor):
                optimizer_error = max(
                    optimizer_error, (value - restored["state"][key][name].cpu()).abs().max().item()
                )
    errors = []
    with torch.no_grad():
        for path in sorted((root / "update").glob("detail-*.json")):
            detail = json.loads(path.read_text())
            if "new_logps" not in detail:
                raise ValueError("This check requires the measured pre-save update logprobs")
            row = rows[detail["index"]]
            hidden, targets = completion_hidden(model, row)
            indices = torch.tensor(detail["engine_positions"], device="cuda")
            actual = (
                frozen_head_logps(
                    hidden[:, indices], model.get_base_model().lm_head.weight, targets[:, indices]
                )
                .cpu()
                .flatten()
            )
            expected = torch.tensor(detail["new_logps"])[indices.cpu()]
            errors.append(
                {"index": detail["index"], "max_abs_error": (actual - expected).abs().max().item()}
            )
            del hidden, targets, actual
    report = {
        "optimizer_max_abs_error": optimizer_error,
        "logprob_comparisons": errors,
        "optimizer_parameters": len(saved["state"]),
        "optimizer_steps": sorted({s["step"].item() for s in saved["state"].values()}),
        "elapsed_seconds": time.monotonic() - started,
    }
    write_json(root / "reload_verification.json", report)
    assert optimizer_error == 0 and max(x["max_abs_error"] for x in errors) <= 1e-4, report
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
