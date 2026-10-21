"""Compare the FP32 memory-efficient attention with dense causal SDPA."""

import json
import time
from pathlib import Path

import torch
from torch.nn.attention import SDPBackend, sdpa_kernel

from .calibrate_forward import compare
from .common import file_hash, write_json
from .grpo_policy import fp32_attention


def main():
    torch.manual_seed(20260922)
    torch.backends.cuda.matmul.allow_tf32 = False
    started = time.monotonic()
    checks = []
    for length in (128, 1024):
        tensors = [
            torch.randn(1, h, length, 128, device="cuda", requires_grad=True) for h in (32, 8, 8)
        ]
        q, k, v = tensors
        cotangent = torch.randn(1, length, 32, 128, device="cuda")
        with sdpa_kernel(SDPBackend.MATH):
            dense = torch.nn.functional.scaled_dot_product_attention(
                q, k, v, is_causal=True, enable_gqa=True
            ).transpose(1, 2)
        gd = torch.autograd.grad((dense * cotangent).sum(), tensors)
        efficient, _ = fp32_attention(None, q, k, v, None)
        ge = torch.autograd.grad((efficient * cotangent).sum(), tensors)
        metrics = {
            "length": length,
            "forward": compare(dense, efficient),
            "gradients": [compare(a, b) for a, b in zip(gd, ge, strict=True)],
        }
        checks.append(metrics)
        assert metrics["forward"]["relative_l2"] < 1e-5
        assert all(m["relative_l2"] < 1e-5 for m in metrics["gradients"])
    del tensors, q, k, v, dense, efficient, gd, ge, cotangent
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    tensors = [torch.randn(1, h, 32768, 128, device="cuda", requires_grad=True) for h in (32, 8, 8)]
    output, _ = fp32_attention(None, *tensors, None)
    output.square().mean().backward()
    assert all(torch.isfinite(t.grad).all() for t in tensors)
    report = {
        "comparisons": checks,
        "length32768_backward_finite": True,
        "peak_gpu_gib": torch.cuda.max_memory_allocated() / 2**30,
        "elapsed_seconds": time.monotonic() - started,
        "source_sha256": {
            p: file_hash(p) for p in ("qwen/grpo_policy.py", "qwen/calibrate_attention.py")
        },
    }
    write_json(Path("qwen/.runtime/exp02_tech/attention.json"), report)
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
