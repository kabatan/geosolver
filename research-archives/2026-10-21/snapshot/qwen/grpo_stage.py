"""Isolated generation/update workers used by grpo_run (one GPU at a time)."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

from .answer_check import PARSER_VERSION, answers_equal, extract_answer
from .common import digest, file_hash, stable_seed, write_json


def row_identity(row):
    return {
        "id": row["id"],
        "variant": row.get("variant", "v0"),
        "prompt_sha256": digest(row.get("problem", row.get("prompt"))),
        "label_sha256": digest(row.get("answer_exact")),
    }


def generate(args):
    from transformers import AutoTokenizer
    from vllm import SamplingParams

    from .models import locked_models
    from .rollout_engine import engine, set_adapter

    started = time.monotonic()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    jobs = json.loads(Path(args.jobs).read_text())
    adapter_hash = (
        file_hash(Path(args.adapter) / "adapter_model.safetensors") if args.adapter else "base"
    )
    context = {
        "jobs_sha256": file_hash(args.jobs),
        "adapter_sha256": adapter_hash,
        "seed": args.seed,
        "kv": args.kv,
        "max_completion": args.max_completion,
        "samples": args.samples,
        "route": args.route,
        "max_seqs": args.max_seqs,
        "parser_version": PARSER_VERSION,
        "source_sha256": file_hash(__file__),
    }
    manifest = out / "generation_manifest.json"
    if manifest.exists() and json.loads(manifest.read_text()) != context:
        raise ValueError("Generation resume mismatch: inputs/policy/settings/code changed")
    write_json(manifest, context)
    pending = [(i, r) for i, r in enumerate(jobs) if not (out / f"group-{i:03}.json").exists()]
    if pending:
        tokenizer = AutoTokenizer.from_pretrained(
            locked_models()["qwen3_4b"]["snapshot_path"], local_files_only=True
        )
        request_kwargs = {}
        if args.route == "fp16_native":
            from .fast_engine import engine as fast_engine
            from .fast_engine import request

            llm = fast_engine(seed=args.seed, max_seqs=args.max_seqs)
            request_kwargs["lora_request"] = request(args.adapter)
        else:
            llm = engine(kv=args.kv, seed=args.seed, max_seqs=args.max_seqs)
        if args.adapter and args.route == "fp32":
            sync_start = time.monotonic()
            sync = set_adapter(llm, args.adapter)
            write_json(
                out / "sync.json", {"seconds": time.monotonic() - sync_start, "result": sync}
            )
        for index, row in pending:
            prompt = tokenizer.apply_chat_template(
                [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": row["problem"]},
                ],
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=True,
            )
            ids = tokenizer.encode(prompt, add_special_tokens=False)
            cap = min(args.max_completion, 32768 - len(ids))
            if cap < 1:
                raise ValueError("Prompt exceeds context limit")
            seed = stable_seed(args.seed, row_identity(row)) % (2**31)
            t = time.monotonic()
            result = llm.generate(
                [{"prompt_token_ids": ids}],
                SamplingParams(
                    n=args.samples,
                    temperature=0.6,
                    top_p=0.95,
                    top_k=20,
                    max_tokens=cap,
                    seed=seed,
                    logprobs=0,
                ),
                **request_kwargs,
            )[0]
            elapsed = time.monotonic() - t
            records = []
            for sample, completion in enumerate(result.outputs):
                tokens = list(completion.token_ids)
                raw = tokenizer.decode(tokens, skip_special_tokens=False)
                # Template may prefill <think>; never reward an intermediate box.
                closed = "</think>" in raw
                extracted = extract_answer(raw) if closed else None
                expected = row.get("answer_exact")
                verdict = answers_equal(extracted, expected) if expected is not None else None
                reward = float(verdict is True)
                records.append(
                    {
                        **row,
                        **row_identity(row),
                        "sample": sample,
                        "prompt_ids": ids,
                        "completion_ids": tokens,
                        "raw_text": raw,
                        (
                            "rollout_sampling_logps"
                            if args.route == "fp16_native"
                            else "rollout_raw_logps"
                        ): [
                            p[token].logprob
                            for p, token in zip(completion.logprobs, tokens, strict=True)
                        ],
                        "finish_reason": completion.finish_reason,
                        "completion_cap": cap,
                        "think_closed": closed,
                        "extracted_answer": extracted,
                        "verdict": verdict,
                        "reward": reward,
                        "seed": seed,
                        "adapter_sha256": adapter_hash,
                        "route": args.route,
                        "logprobs_mode": "processed_logprobs"
                        if args.route == "fp16_native"
                        else "raw_logprobs",
                        "parser_version": PARSER_VERSION,
                        "generation_seconds_group": elapsed,
                    }
                )
            mean_reward = sum(r["reward"] for r in records) / len(records)
            for record in records:
                record["advantage"] = record["reward"] - mean_reward
                record["valid_tokens"] = (
                    len(record["completion_ids"]) if record["finish_reason"] == "stop" else 0
                )
            write_json(out / f"group-{index:03}.json", records)
            print(
                json.dumps(
                    {
                        "group": index,
                        "id": row["id"],
                        "rewards": [r["reward"] for r in records],
                        "lengths": [len(r["completion_ids"]) for r in records],
                        "seconds": elapsed,
                    }
                ),
                flush=True,
            )
    records = [
        r for i in range(len(jobs)) for r in json.loads((out / f"group-{i:03}.json").read_text())
    ]
    write_json(out / "rollouts.json", records)
    write_json(
        out / "generation_metrics.json",
        {
            "elapsed_seconds_this_process": time.monotonic() - started,
            "generation_seconds": sum(
                json.loads((out / f"group-{i:03}.json").read_text())[0]["generation_seconds_group"]
                for i in range(len(jobs))
            ),
            "output_tokens": sum(len(r["completion_ids"]) for r in records),
            "correct": sum(r["reward"] for r in records),
            "mixed_groups": sum(
                0
                < sum(
                    r["reward"]
                    for r in records
                    if r["id"] == j["id"] and r["variant"] == j.get("variant", "v0")
                )
                < args.samples
                for j in jobs
            ),
        },
    )


def update(args):
    import torch

    from .grpo_loss import frozen_head_logps, sampling_correction, token_policy_loss
    from .grpo_policy import completion_hidden, completion_logps, load_policy, trainable

    started = time.monotonic()
    out = Path(args.output)
    if (out / "COMPLETE.json").exists():
        raise ValueError("Completed update is immutable; choose a new directory")
    out.mkdir(parents=True, exist_ok=True)
    rows = json.loads(Path(args.rollouts).read_text())
    if any(r["parser_version"] != PARSER_VERSION for r in rows):
        raise ValueError("Incompatible reward parser")
    expected_hash = (
        file_hash(Path(args.adapter) / "adapter_model.safetensors") if args.adapter else "base"
    )
    if any(r["adapter_sha256"] != expected_hash for r in rows):
        raise ValueError("Off-policy input: rollout adapter does not match learner")
    if any(r.get("route", "fp32") != args.route for r in rows):
        raise ValueError("Rollout/learner precision route mismatch")
    denominator = sum(r["valid_tokens"] for r in rows)
    active = [i for i, r in enumerate(rows) if r["valid_tokens"] and r["advantage"] != 0]
    if not active:
        raise ValueError("No mixed-reward, untruncated signal; no technical update was performed")
    model, tokenizer = load_policy(
        args.adapter or None,
        seed=args.seed,
        precision="float16" if args.route == "fp16_native" else "float32",
    )
    parameters = trainable(model)
    optimizer = torch.optim.AdamW(parameters, lr=args.lr, weight_decay=0.0, eps=1e-8)
    if args.optimizer:
        optimizer.load_state_dict(
            torch.load(args.optimizer, map_location="cuda", weights_only=True)
        )
    before = [p.detach().cpu().clone() for p in parameters]
    optimizer.zero_grad(set_to_none=True)
    scaler = torch.amp.GradScaler(
        "cuda", enabled=args.route == "fp16_native", init_scale=1024, growth_interval=1000000
    )
    if args.optimizer and args.route == "fp16_native":
        scaler.load_state_dict(
            json.loads(Path(args.optimizer).with_name("scaler.json").read_text())
        )
    details = []
    forward_backward_seconds = 0.0
    for index in active:
        row = rows[index]
        t = time.monotonic()
        hidden, targets = completion_hidden(model, row, offload=True)
        lp = frozen_head_logps(hidden, model.get_base_model().lm_head.weight, targets)
        # One update per fresh rollout. Before the first optimizer step this
        # teacher-forced policy is exactly the old learner; detach, don't
        # retain a second model or do a redundant full forward pass.
        old = lp.detach()
        adv = torch.tensor([row["advantage"]], device="cuda")
        weights, correction = None, None
        if args.route == "fp16_native":
            sampled_all = torch.tensor([row["rollout_sampling_logps"]], device="cuda")
            weights, correction = sampling_correction(old, sampled_all)
            if correction["relative_ess"] < 0.90 or correction["clipped_fraction"] > 0.01:
                raise ValueError(f"Excessive sampling/learner mismatch: {correction}")
        loss = token_policy_loss(
            lp, old, adv, torch.ones_like(lp), denominator, importance_weights=weights
        )
        # Compare engines at raw temperature 1 on a fixed subset, since vLLM
        # raw_logprobs are pre-temperature and pre-top-k/top-p.
        positions = torch.linspace(0, lp.shape[1] - 1, min(32, lp.shape[1]), device="cuda").long()
        with torch.no_grad():
            raw_lp = (
                frozen_head_logps(
                    hidden[:, positions],
                    model.get_base_model().lm_head.weight,
                    targets[:, positions],
                    temperature=1,
                )
                .flatten()
                .cpu()
            )
        old_cpu = old.flatten().cpu()
        scaler.scale(loss).backward()
        del hidden, targets, lp, old, loss
        torch.cuda.synchronize()
        elapsed = time.monotonic() - t
        forward_backward_seconds += elapsed
        sampled = torch.tensor(row.get("rollout_raw_logps", row.get("rollout_sampling_logps")))[
            positions.cpu()
        ]
        detail = {
            "index": index,
            **row_identity(row),
            "sample": row["sample"],
            "advantage": row["advantage"],
            "old_logps": old_cpu.tolist(),
            "engine_positions": positions.cpu().tolist(),
            "learner_raw_logps": raw_lp.tolist(),
            (
                "rollout_sampling_logps_selected"
                if correction is not None
                else "rollout_raw_logps_selected"
            ): sampled.tolist(),
            "engine_mean_abs_error": (raw_lp - sampled).abs().mean().item()
            if correction is None
            else None,
            "engine_max_abs_error": (raw_lp - sampled).abs().max().item()
            if correction is None
            else None,
            "sampling_correction": correction,
            "importance_weights": weights.cpu().flatten().tolist() if weights is not None else None,
            "forward_backward_seconds": elapsed,
        }
        details.append(detail)
        write_json(out / f"detail-{index:03}.json", detail)
        print(json.dumps({k: v for k, v in detail.items() if not isinstance(v, list)}), flush=True)
    scaler.unscale_(optimizer)
    norm = torch.nn.utils.clip_grad_norm_(parameters, 1.0, error_if_nonfinite=True)
    scaler.step(optimizer)
    scaler.update()
    delta = (
        sum(
            (p.detach().cpu() - b).double().square().sum().item()
            for p, b in zip(parameters, before, strict=True)
        )
        ** 0.5
    )
    if not delta > 0:
        raise ValueError("Optimizer did not modify any parameter")
    save_started = time.monotonic()
    model.save_pretrained(out / "adapter")
    tokenizer.save_pretrained(out / "adapter")
    torch.save(optimizer.state_dict(), out / "optimizer.pt")
    if args.route == "fp16_native":
        write_json(out / "scaler.json", scaler.state_dict())
    save_seconds = time.monotonic() - save_started
    # Full old/new objective is deliberately measured in calibration. Routine
    # long runs can omit this extra forward, but keep old per-token logps.
    new_objective, old_objective = 0.0, 0.0
    if args.measure_after:
        with torch.no_grad():
            for detail in details:
                row = rows[detail["index"]]
                lp = completion_logps(model, row)
                old = torch.tensor([detail["old_logps"]], device="cuda")
                adv = torch.tensor([row["advantage"]], device="cuda")
                weights = (
                    torch.tensor([detail["importance_weights"]], device="cuda")
                    if detail["importance_weights"] is not None
                    else None
                )
                new_objective -= token_policy_loss(
                    lp, old, adv, torch.ones_like(lp), denominator, importance_weights=weights
                ).item()
                old_objective -= token_policy_loss(
                    old, old, adv, torch.ones_like(lp), denominator, importance_weights=weights
                ).item()
                detail["new_logps"] = lp.flatten().cpu().tolist()
                write_json(out / f"detail-{detail['index']:03}.json", detail)
    metrics = {
        "elapsed_seconds": time.monotonic() - started,
        "valid_tokens": denominator,
        "active_responses": len(active),
        "responses": len(rows),
        "gradient_norm": norm.item(),
        "parameter_delta_l2": delta,
        "forward_backward_seconds": forward_backward_seconds,
        "save_seconds": save_seconds,
        "peak_gpu_gib": torch.cuda.max_memory_allocated() / 2**30,
        "old_objective": old_objective if args.measure_after else None,
        "new_objective": new_objective if args.measure_after else None,
        "adapter_sha256": file_hash(out / "adapter/adapter_model.safetensors"),
        "rollouts_sha256": file_hash(args.rollouts),
        "seed": args.seed,
        "lr": args.lr,
        "route": args.route,
        "engine_correction": "token_truncate_cap2_processed_sampling_logps"
        if args.route == "fp16_native"
        else "none; raw engine discrepancy measured",
    }
    write_json(out / "COMPLETE.json", metrics)
    print(json.dumps(metrics), flush=True)


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("stage", choices=["generate", "update"])
    ap.add_argument("--jobs")
    ap.add_argument("--rollouts")
    ap.add_argument("--output", required=True)
    ap.add_argument("--adapter", default="")
    ap.add_argument("--optimizer", default="")
    ap.add_argument("--seed", type=int, default=20260922)
    ap.add_argument("--kv", default="auto")
    ap.add_argument("--samples", type=int, default=4)
    ap.add_argument("--max-seqs", type=int, default=4)
    ap.add_argument("--max-completion", type=int, default=32512)
    ap.add_argument("--lr", type=float, default=1e-6)
    ap.add_argument("--measure-after", action="store_true")
    ap.add_argument("--route", choices=["fp32", "fp16_native"], default="fp32")
    args = ap.parse_args()
    (generate if args.stage == "generate" else update)(args)


if __name__ == "__main__":
    main()
