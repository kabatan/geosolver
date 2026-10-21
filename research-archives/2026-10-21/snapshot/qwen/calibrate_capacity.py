"""Full-context memory test after saving a real optimizer; no optimizer step."""

import json
import time
from pathlib import Path

import torch

from .common import file_hash, write_json
from .grpo_loss import token_policy_loss
from .grpo_policy import completion_logps, load_policy, trainable


def main():
    root = Path("qwen/.runtime/exp02_tech")
    checkpoint = root / "live/round-000/update"
    rows = json.loads((root / "live/round-000/generation/rollouts.json").read_text())
    row = dict(max(rows, key=lambda r: len(r["completion_ids"])))
    cap = 32768 - len(row["prompt_ids"])
    row["completion_ids"] = (row["completion_ids"] * 3)[:cap]
    started = time.monotonic()
    model, _ = load_policy(checkpoint / "adapter")
    optimizer = torch.optim.AdamW(trainable(model), lr=1e-6, weight_decay=0, eps=1e-8)
    optimizer.load_state_dict(
        torch.load(checkpoint / "optimizer.pt", map_location="cuda", weights_only=True)
    )
    torch.cuda.reset_peak_memory_stats()
    lp = completion_logps(model, row, offload=True)
    loss = token_policy_loss(
        lp, lp.detach(), torch.tensor([0.5], device="cuda"), torch.ones_like(lp), cap
    )
    loss.backward()
    norm = torch.nn.utils.clip_grad_norm_(trainable(model), 1, error_if_nonfinite=True)
    torch.cuda.synchronize()
    report = {
        "context_tokens": len(row["prompt_ids"]) + cap,
        "completion_tokens": cap,
        "optimizer_state_loaded": True,
        "optimizer_steps_performed": 0,
        "gradient_norm": norm.item(),
        "peak_gpu_gib": torch.cuda.max_memory_allocated() / 2**30,
        "elapsed_seconds": time.monotonic() - started,
        "scope": "Synthetic repeated-token capacity fixture; not a natural training observation.",
        "source_sha256": {
            p: file_hash(p)
            for p in ("qwen/grpo_policy.py", "qwen/grpo_loss.py", "qwen/calibrate_capacity.py")
        },
    }
    write_json(root / "capacity.json", report)
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
