"""Small half-precision learner/actor tests, charged to the shared preparation budget."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .common import file_hash, write_json


def learner(out, precision, lr):
    import torch

    from .grpo_loss import frozen_head_logps, token_policy_loss
    from .grpo_policy import completion_hidden, completion_logps, load_policy, trainable

    rows = [
        json.loads(s)
        for s in Path("qwen/.runtime/exp02_tech/fixed/fixed_rollouts.jsonl")
        .read_text()
        .splitlines()
    ]
    model, tokenizer = load_policy(precision=precision)
    started = time.monotonic()
    denominator = sum(len(r["completion_ids"]) for r in rows)
    optimizer = torch.optim.AdamW(trainable(model), lr=lr, weight_decay=0, eps=1e-8)
    initial = [p.detach().cpu().clone() for p in trainable(model)]
    history = []
    for step in range(4):
        objective = 0.0
        with torch.no_grad():
            for r in rows:
                lp = completion_logps(model, r)
                if step == 0:
                    r["old_logps"] = lp.cpu().flatten().tolist()
                r[f"learner_step{step}_logps"] = lp.cpu().flatten().tolist()
                objective -= token_policy_loss(
                    lp,
                    torch.tensor([r["old_logps"]], device="cuda"),
                    torch.tensor([r["advantage"]], device="cuda"),
                    torch.ones_like(lp),
                    denominator,
                ).item()
                if step in (0, 3):
                    h, t = completion_hidden(model, r)
                    r[f"learner_step{step}_raw_logps"] = (
                        frozen_head_logps(
                            h, model.get_base_model().lm_head.weight, t, temperature=1
                        )
                        .cpu()
                        .flatten()
                        .tolist()
                    )
        history.append({"step": step, "objective": objective})
        print(json.dumps(history[-1]), flush=True)
        if step == 3:
            break
        optimizer.zero_grad(set_to_none=True)
        for r in rows:
            lp = completion_logps(model, r)
            loss = token_policy_loss(
                lp,
                torch.tensor([r["old_logps"]], device="cuda"),
                torch.tensor([r["advantage"]], device="cuda"),
                torch.ones_like(lp),
                denominator,
            )
            loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(trainable(model), 1, error_if_nonfinite=True)
        history[-1]["gradient_norm"] = norm.item()
        optimizer.step()
    delta = (
        sum(
            (p.detach().cpu() - b).double().square().sum().item()
            for p, b in zip(trainable(model), initial, strict=True)
        )
        ** 0.5
    )
    model.save_pretrained(out / "adapter")
    tokenizer.save_pretrained(out / "adapter")
    write_json(out / "rows.json", rows)
    report = {
        "precision": precision,
        "lr": lr,
        "history": history,
        "parameter_delta_l2": delta,
        "seconds": time.monotonic() - started,
        "adapter_sha256": file_hash(out / "adapter/adapter_model.safetensors"),
    }
    write_json(out / "learner.json", report)
    assert delta > 0 and history[-1]["objective"] > history[0]["objective"], report


def actor(out, precision):
    import torch
    from vllm import SamplingParams

    from .calibrate_forward import compare
    from .fast_engine import engine, request

    rows = json.loads((out / "rows.json").read_text())
    llm = engine(precision=precision)
    started = time.monotonic()
    values = {}
    for state, adapter in [
        ("base", ""),
        ("base_repeat", ""),
        ("trained", out / "adapter"),
        ("trained_repeat", out / "adapter"),
    ]:
        outputs = llm.generate(
            [{"prompt_token_ids": r["prompt_ids"] + r["completion_ids"]} for r in rows],
            SamplingParams(temperature=1, top_p=1, top_k=-1, max_tokens=1, prompt_logprobs=0),
            lora_request=request(adapter),
        )
        values[state] = [
            [
                p[token].logprob
                for p, token in zip(
                    o.prompt_logprobs[len(r["prompt_ids"]) :], r["completion_ids"], strict=True
                )
            ]
            for r, o in zip(rows, outputs, strict=True)
        ]

    def flat(name):
        return torch.tensor([x for a in values[name] for x in a])

    hf0 = torch.tensor(
        [x for r in rows for x in r.get("learner_step0_raw_logps", r.get("bf16_step0_raw_logps"))]
    )
    hf1 = torch.tensor(
        [x for r in rows for x in r.get("learner_step3_raw_logps", r.get("bf16_step3_raw_logps"))]
    )
    # Raw-temperature-one surrogate for the same fixed positive/negative answers.
    adv = torch.tensor([r["advantage"] for r in rows for _ in r["completion_ids"]])
    improvement = ((flat("trained") - flat("base")).exp() * adv - adv).mean().item()
    report = {
        "precision": precision,
        "base_engine": compare(hf0, flat("base")),
        "adapter_delta": compare(hf1 - hf0, flat("trained") - flat("base")),
        "base_repeat_max": (flat("base_repeat") - flat("base")).abs().max().item(),
        "trained_repeat_max": (flat("trained_repeat") - flat("trained")).abs().max().item(),
        "actor_raw_surrogate_improvement": improvement,
        "seconds": time.monotonic() - started,
        "values": values,
    }
    write_json(out / "actor.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "values"}), flush=True)


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("stage", choices=["learner", "actor"])
    ap.add_argument("--precision", choices=["float16", "bfloat16"], default="float16")
    ap.add_argument("--output", required=True)
    ap.add_argument("--lr", type=float, default=1e-6)
    args = ap.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    if args.stage == "learner":
        learner(out, args.precision, args.lr)
    else:
        actor(out, args.precision)


if __name__ == "__main__":
    main()
