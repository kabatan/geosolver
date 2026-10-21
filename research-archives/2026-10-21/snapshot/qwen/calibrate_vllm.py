"""Measure fixed-token synchronized rollout policy against HF FP32 reference."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("--forward", default="qwen/.runtime/exp02_tech/forward")
    ap.add_argument("--adapter", default="qwen/.runtime/exp01/grpo01/final_adapter")
    ap.add_argument("--dtype", default="float32")
    ap.add_argument("--kv", default="auto")
    ap.add_argument("--output", default="qwen/.runtime/exp02_tech/vllm_forward.json")
    args = ap.parse_args()
    import torch
    from vllm import SamplingParams

    from .calibrate_forward import compare, write_json
    from .rollout_engine import engine, set_adapter

    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    forward = Path(args.forward)
    rows = json.loads((forward / "tokens.json").read_text())
    started = time.monotonic()
    if args.dtype != "float32":
        raise ValueError("Only the FP32 immutable-base synchronization is supported")
    llm = engine(args.kv)
    values = {}
    for state in ("base", "adapter", "repeat"):
        if state == "adapter":
            set_adapter(llm, args.adapter)
        outputs = llm.generate(
            [{"prompt_token_ids": r["input_ids"]} for r in rows],
            SamplingParams(temperature=0, max_tokens=1, prompt_logprobs=0),
        )
        values[state] = [
            [next(iter(p.values())).logprob for p in o.prompt_logprobs[-32:]] for o in outputs
        ]
    hf_base = torch.cat(
        [r["logps"].flatten() for r in torch.load(forward / "fp32_base.pt", weights_only=True)]
    )
    hf_adapter = torch.cat(
        [r["logps"].flatten() for r in torch.load(forward / "fp32_adapter.pt", weights_only=True)]
    )
    base, adapter = (torch.tensor(values[s]).flatten() for s in ("base", "adapter"))
    report = {
        "elapsed_seconds": time.monotonic() - started,
        "dtype": args.dtype,
        "kv": args.kv,
        "logprobs": values,
        "base_engine": compare(hf_base, base),
        "adapter_delta": compare(hf_adapter - hf_base, adapter - base),
        "repeat_max_abs": (torch.tensor(values["adapter"]) - torch.tensor(values["repeat"]))
        .abs()
        .max()
        .item(),
    }
    write_json(args.output, report)
    print(json.dumps({k: v for k, v in report.items() if k != "logprobs"}, indent=2), flush=True)


if __name__ == "__main__":
    main()
