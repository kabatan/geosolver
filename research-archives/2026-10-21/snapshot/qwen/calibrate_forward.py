"""Fixed-token, non-generative adapter precision audit (explicit GPU CLI)."""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.metadata
import json
import os
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from .models import locked_models


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def fixtures(tokenizer):
    rows = [
        json.loads(x)
        for x in Path("benchmarks/humpty_configurations_v2/training_variants.jsonl")
        .read_text()
        .splitlines()
    ]
    result = []
    for key in ("H01", "H02", "DA05", "DB02"):
        row = next(r for r in rows if r["id"] == key and r["variant"] == "v0")
        prompt = tokenizer.apply_chat_template(
            [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": row["problem"]},
            ],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=True,
        )
        suffix = "</think>\n\\boxed{" + row["answer_exact"] + "}"
        result.append(
            {
                **row,
                "prompt_ids": tokenizer.encode(prompt, add_special_tokens=False),
                "input_ids": tokenizer.encode(prompt + suffix, add_special_tokens=False),
            }
        )
    return result


def compare(a, b):
    import torch

    a, b = a.double().flatten(), b.double().flatten()
    an, bn = a.norm(), b.norm()
    return {
        "reference_rms": a.square().mean().sqrt().item(),
        "candidate_rms": b.square().mean().sqrt().item(),
        "max_error": (a - b).abs().max().item(),
        "relative_l2": ((a - b).norm() / an.clamp_min(1e-30)).item(),
        "cosine": (torch.dot(a, b) / (an * bn).clamp_min(1e-30)).item(),
    }


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("--output", default="qwen/.runtime/exp02_tech/forward")
    ap.add_argument("--adapter", default="qwen/.runtime/exp01/grpo01/final_adapter")
    ap.add_argument("--merged", default="qwen/.runtime/exp01/merged_grpo01")
    args = ap.parse_args()
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    snapshot = locked_models()["qwen3_4b"]["snapshot_path"]
    tok = AutoTokenizer.from_pretrained(snapshot, local_files_only=True)
    data = fixtures(tok)
    write_json(out / "tokens.json", data)
    results = {}

    def load(dtype, path=snapshot):
        return (
            AutoModelForCausalLM.from_pretrained(
                path, dtype=dtype, local_files_only=True, attn_implementation="sdpa"
            )
            .to("cuda")
            .eval()
        )

    def capture(model, name):
        values = []
        with torch.inference_mode():
            for row in data:
                ids = torch.tensor([row["input_ids"]], device="cuda")
                n = min(32, ids.shape[1] - 1)
                logits = (
                    model(input_ids=ids, use_cache=False, logits_to_keep=n + 1)
                    .logits[:, :-1]
                    .float()
                )
                logps = logits.log_softmax(-1).gather(-1, ids[:, -n:, None]).squeeze(-1)
                values.append({"id": row["id"], "logits": logits.cpu(), "logps": logps.cpu()})
        torch.save(values, out / (name + ".pt"))
        results[name] = values
        print(json.dumps({"captured": name, "elapsed": time.monotonic() - started}), flush=True)

    def release(model):
        del model
        gc.collect()
        torch.cuda.empty_cache()

    model = load(torch.float32)
    capture(model, "fp32_base")
    capture(model, "fp32_repeat")
    model = PeftModel.from_pretrained(model, args.adapter).eval()
    with model.disable_adapter():
        capture(model, "fp32_disabled")
    capture(model, "fp32_adapter")
    model = model.merge_and_unload(safe_merge=True)
    capture(model, "fp32_merged")
    del model
    release(None)

    model = load(torch.bfloat16)
    capture(model, "bf16_base")
    model = PeftModel.from_pretrained(model, args.adapter).eval()
    with model.disable_adapter():
        capture(model, "bf16_disabled")
    capture(model, "bf16_adapter")
    model.save_pretrained(out / "adapter_reload")
    del model
    release(None)
    model = PeftModel.from_pretrained(load(torch.bfloat16), out / "adapter_reload").eval()
    capture(model, "bf16_reload")
    del model
    release(None)
    if args.merged:
        model = load(torch.bfloat16, args.merged)
        capture(model, "bf16_historical_merge")
        del model
        release(None)
    comparisons = {}
    for name, base in [
        ("fp32_merged", "fp32_base"),
        ("bf16_adapter", "bf16_base"),
        ("bf16_historical_merge", "bf16_base"),
    ]:
        if name not in results:
            continue
        comparisons[name] = {}
        for kind in ("logits", "logps"):
            reference = torch.cat(
                [
                    (a[kind] - b[kind]).flatten()
                    for a, b in zip(results["fp32_adapter"], results["fp32_base"], strict=True)
                ]
            )
            candidate = torch.cat(
                [
                    (a[kind] - b[kind]).flatten()
                    for a, b in zip(results[name], results[base], strict=True)
                ]
            )
            comparisons[name][kind] = compare(reference, candidate)
    controls = {}
    for a, b in [
        ("fp32_base", "fp32_repeat"),
        ("fp32_base", "fp32_disabled"),
        ("bf16_base", "bf16_disabled"),
        ("bf16_adapter", "bf16_reload"),
    ]:
        controls[a + "_vs_" + b] = max(
            (x["logits"] - y["logits"]).abs().max().item()
            for x, y in zip(results[a], results[b], strict=True)
        )
    report = {
        "elapsed_seconds": time.monotonic() - started,
        "comparisons": comparisons,
        "controls_max_abs": controls,
        "adapter_sha256": digest(Path(args.adapter) / "adapter_model.safetensors"),
        "versions": {
            p: importlib.metadata.version(p)
            for p in ("torch", "transformers", "peft", "trl", "vllm", "liger-kernel")
        },
    }
    write_json(out / "adapter_forward_comparison.json", report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
