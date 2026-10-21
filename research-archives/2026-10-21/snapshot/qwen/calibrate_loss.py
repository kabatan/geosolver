"""CPU comparison of the executed loss against dense autograd and Liger."""

from __future__ import annotations

import json
from pathlib import Path

import torch

from .grpo_loss import frozen_head_logps, liger_policy_loss, token_policy_loss


def run():
    torch.set_num_threads(4)
    torch.manual_seed(20260922)
    results = []
    for scenario in ("lengths2_6", "variable", "clipping", "all_mask", "zero_adv", "reverse"):
        b, t, h, v = (2, 6, 7, 17) if scenario == "lengths2_6" else (16, 9, 7, 17)
        hidden = torch.randn(b, t, h)
        weight = torch.randn(v, h) / 3
        targets = torch.randint(v, (b, t))
        lengths = torch.tensor([2, 6]) if b == 2 else torch.arange(b) % t + 1
        mask = torch.arange(t)[None, :] < lengths[:, None]
        if b == 16:
            mask[3] = False  # a truncated completion
        if scenario == "all_mask":
            mask[:] = False
        adv = torch.tensor([0.5, -0.5] * (b // 2))
        if scenario == "zero_adv":
            adv.zero_()
        if scenario == "reverse":
            adv.neg_()
        old = (hidden @ weight.T / 0.6).log_softmax(-1).gather(-1, targets[..., None]).squeeze(-1)
        if scenario == "clipping":
            old += torch.linspace(-0.5, 0.5, t)
        denominator = mask.sum()
        ref_hidden = hidden.clone().requires_grad_()
        ref_logps = (
            (ref_hidden @ weight.T / 0.6).log_softmax(-1).gather(-1, targets[..., None]).squeeze(-1)
        )
        ref_loss = token_policy_loss(ref_logps, old, adv, mask, denominator)
        reference = torch.autograd.grad(ref_loss, ref_hidden)[0]
        for micro in (1, 2, 4, 16):
            if micro > b:
                continue
            for engine in ("bounded_head", "liger"):
                x = hidden.clone().requires_grad_()
                total = 0.0
                for start in range(0, b, micro):
                    sl = slice(start, start + micro)
                    if engine == "bounded_head":
                        lp = frozen_head_logps(x[sl], weight, targets[sl], chunk_size=3)
                        loss = token_policy_loss(lp, old[sl], adv[sl], mask[sl], denominator)
                    else:
                        loss = liger_policy_loss(
                            x[sl],
                            weight,
                            targets[sl],
                            old[sl],
                            adv[sl],
                            mask[sl],
                            denominator,
                            chunk_size=3,
                        )
                    loss.backward()
                    total += loss.item()
                error = (x.grad - reference).norm().item()
                rel = error / max(reference.norm().item(), 1e-30)
                passed = torch.isfinite(x.grad).all().item() and (rel <= 1e-5 or error <= 1e-7)
                results.append(
                    dict(
                        scenario=scenario,
                        micro=micro,
                        engine=engine,
                        relative_gradient_error=rel,
                        absolute_gradient_error=error,
                        loss_error=abs(total - ref_loss.item()),
                        passed=passed,
                    )
                )
    out = Path("qwen/.runtime/exp02_tech/loss_equivalence.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2) + "\n")
    assert all(r["passed"] for r in results), results
    print(
        f"PASS: {len(results)} gradient comparisons; max relative error "
        f"{max(r['relative_gradient_error'] for r in results):.3g}"
    )


if __name__ == "__main__":
    run()
