"""Compare answer-hinted and unhinted next-token distributions on fixed rollouts.

Use after a round-one batch was sampled from the base policy and a later
checkpoint has been trained. This probe scores the first eight completions from
that unchanged batch under (q0) the base on the student prompt, (qhint) the same
base with the answer-hinted prompt, and (p) the updated adapter on the student
prompt. It uses one model copy and moves raw logits to CPU between forwards.

Run in the pilot's vLLM environment, for example:
  qwen/.runtime/vllm-venv/bin/python \
    docs/research/answer-opd-pilot-2026-09-26/distribution_probe.py \
    --batch ROUND1_BATCH.json --checkpoint TRAIN_OUTPUT_DIR --out PROBE_DIR
"""

import argparse
import gc
import hashlib
import json
import math
import time
from pathlib import Path

import torch


HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def finite(tensor, name):
    if not torch.isfinite(tensor).all().item():
        raise ValueError(f"Nonfinite values in {name}")


def load_inputs(args):
    config = json.loads(CONFIG_PATH.read_text())
    meta_path = Path(config["model_metadata"]).resolve()
    meta = json.loads(meta_path.read_text())
    if meta.get("model_id") != "Qwen/Qwen3.5-9B" or not Path(meta["snapshot"]).is_dir():
        raise ValueError("Expected the configured local Qwen3.5-9B snapshot")

    batch_path = Path(args.batch).resolve()
    checkpoint = Path(args.checkpoint).resolve()
    batch = json.loads(batch_path.read_text())
    if batch.get("round") != 1 or batch.get("policy_adapter_sha256") is not None:
        raise ValueError("Probe requires the unchanged base-policy round-one rollout batch")
    rows = batch.get("examples")
    if not isinstance(rows, list) or len(rows) < 8:
        raise ValueError("Round-one batch must contain at least eight examples")
    rows = rows[:8]

    adapter_file = checkpoint / "adapter" / "adapter_model.safetensors"
    adapter_config = checkpoint / "adapter" / "adapter_config.json"
    if not adapter_file.is_file() or not adapter_config.is_file():
        raise ValueError("Checkpoint must contain adapter/adapter_model.safetensors and adapter_config.json")
    checkpoint_receipt_path = checkpoint / "receipt.json"
    checkpoint_receipt = json.loads(checkpoint_receipt_path.read_text())
    adapter_sha = digest(adapter_file)
    if (checkpoint_receipt.get("status") != "complete" or
            checkpoint_receipt.get("model_revision") != meta["revision"] or
            checkpoint_receipt.get("adapter_sha256") != adapter_sha):
        raise ValueError("Checkpoint receipt is incomplete or does not match the adapter/model revision")

    seen = set()
    for row in rows:
        required = ("id", "student_prompt_ids", "teacher_prompt_ids", "completion_ids",
                    "finish_reason", "student_thinking", "teacher_thinking")
        if not isinstance(row, dict) or any(key not in row for key in required):
            raise ValueError("Incomplete round-one rollout row")
        if row["id"] in seen or not isinstance(row["id"], str):
            raise ValueError("Rollout IDs must be unique strings")
        seen.add(row["id"])
        if row["student_thinking"] is not False or row["teacher_thinking"] is not False:
            raise ValueError(f"{row['id']}: this probe is frozen to non-thinking mode")
        for field in ("student_prompt_ids", "teacher_prompt_ids", "completion_ids"):
            values = row[field]
            if (not isinstance(values, list) or not values or
                    any(type(token) is not int or token < 0 for token in values)):
                raise ValueError(f"{row['id']}: invalid {field}")
        if row["finish_reason"] not in ("stop", "eos", "end_of_sequence", "length"):
            raise ValueError(f"{row['id']}: unknown finish_reason {row['finish_reason']!r}")

    max_tokens = config["max_completion_tokens"]
    max_sequence = config["max_sequence_tokens"]
    prepared = []
    for row in rows:
        completion = row["completion_ids"][:max_tokens]
        if not completion:
            raise ValueError(f"{row['id']}: empty completion prefix")
        if (len(row["student_prompt_ids"]) + len(completion) > max_sequence or
                len(row["teacher_prompt_ids"]) + len(completion) > max_sequence):
            raise ValueError(f"{row['id']}: prompt plus completion exceeds configured context")
        prepared.append({**row, "completion_ids": completion})

    return dict(config=config, meta=meta, meta_path=meta_path, batch_path=batch_path,
                batch=batch, rows=prepared, checkpoint=checkpoint,
                checkpoint_receipt_path=checkpoint_receipt_path,
                adapter_file=adapter_file, adapter_sha=adapter_sha)


def forward_completion_logits(model, prompt_ids, completion_ids, device):
    """Return one BF16 CPU row per sampled token, aligned as in train_worker."""
    n = len(completion_ids)
    input_ids = torch.tensor([prompt_ids + completion_ids], dtype=torch.long, device=device)
    with torch.no_grad():
        output = model(input_ids=input_ids, use_cache=False, logits_to_keep=n + 1)
        logits = output.logits[0, :-1].detach()
    if logits.ndim != 2 or logits.shape[0] != n:
        raise AssertionError(
            f"Completion-token alignment failed: got {tuple(logits.shape)}, expected ({n}, vocab)"
        )
    cpu_logits = logits.to(device="cpu", dtype=torch.bfloat16).contiguous()
    finite(cpu_logits, "completion logits")
    del input_ids, output, logits
    gc.collect()
    torch.cuda.empty_cache()
    return cpu_logits


def streamed_kl_rows(q0_cpu, qhint_cpu, p_cpu, device, chunk_tokens=64):
    """Compute full-vocabulary FP32 KL in token chunks on ``device``.

    Raw completion logits remain CPU-offloaded. Each device transfer holds at
    most ``chunk_tokens`` rows but the entire vocabulary, avoiding thousands
    of tiny transfers along the vocabulary axis.
    """
    if q0_cpu.shape != qhint_cpu.shape or q0_cpu.shape != p_cpu.shape or q0_cpu.ndim != 2:
        raise ValueError("q0, qhint, and p completion-logit arrays must have identical [tokens,vocab] shapes")
    if chunk_tokens < 1:
        raise ValueError("chunk_tokens must be positive")
    n_tokens = q0_cpu.shape[0]
    row_chunks = {"kl_qhint_q0": [], "kl_qhint_p": [], "kl_q0_p": []}
    for start in range(0, n_tokens, chunk_tokens):
        end = min(start + chunk_tokens, n_tokens)
        x0 = q0_cpu[start:end].to(device=device, dtype=torch.float32)
        xh = qhint_cpu[start:end].to(device=device, dtype=torch.float32)
        xp = p_cpu[start:end].to(device=device, dtype=torch.float32)
        lp0 = torch.log_softmax(x0, dim=-1)
        lph = torch.log_softmax(xh, dim=-1)
        lpp = torch.log_softmax(xp, dim=-1)
        q0 = lp0.exp()
        qh = lph.exp()
        row_chunks["kl_qhint_q0"].append((qh * (lph - lp0)).sum(dim=-1).detach().cpu())
        row_chunks["kl_qhint_p"].append((qh * (lph - lpp)).sum(dim=-1).detach().cpu())
        row_chunks["kl_q0_p"].append((q0 * (lp0 - lpp)).sum(dim=-1).detach().cpu())
        del x0, xh, xp, lp0, lph, lpp, q0, qh

    rows = {name: torch.cat(chunks) for name, chunks in row_chunks.items()}
    for name, values in rows.items():
        finite(values, name)
        if float(values.min()) < -1e-4:
            raise AssertionError(f"Numerically negative KL for {name}: {float(values.min())}")
    return rows


def quartile_means(values):
    n = values.numel()
    if n == 0:
        return []
    points = [0, math.ceil(n / 4), math.ceil(n / 2), math.ceil(3 * n / 4), n]
    result = []
    for start, end in zip(points[:-1], points[1:]):
        if end > start:
            result.append(float(values[start:end].mean()))
        else:
            result.append(None)
    return result


def score_one(model, row, device, chunk_tokens, max_memory):
    started = time.monotonic()
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats(device)
    n = len(row["completion_ids"])
    model.eval()
    # The same PEFT-wrapped model is reused; disabling its one adapter gives q0
    # and qhint, then the enabled adapter gives p. There is no second base copy.
    with torch.no_grad(), model.disable_adapter():
        q0 = forward_completion_logits(model, row["student_prompt_ids"], row["completion_ids"], device)
        qhint = forward_completion_logits(model, row["teacher_prompt_ids"], row["completion_ids"], device)
    p = forward_completion_logits(model, row["student_prompt_ids"], row["completion_ids"], device)
    if q0.shape != qhint.shape or q0.shape != p.shape:
        raise AssertionError(f"{row['id']}: distribution token alignment differs")

    kl = streamed_kl_rows(q0, qhint, p, device, chunk_tokens=chunk_tokens)
    metrics = {}
    for name, token_values in kl.items():
        metrics[name] = {
            "mean_nats_per_completion_token": float(token_values.mean()),
            "quartile_means_nats_per_token": quartile_means(token_values),
            "minimum_token_kl_nats": float(token_values.min()),
            "maximum_token_kl_nats": float(token_values.max()),
        }
    if torch.cuda.is_available():
        max_memory = max(max_memory, torch.cuda.max_memory_allocated(device))
    result = {
        "id": row["id"],
        "source_id": row.get("source_id"),
        "variant": row.get("variant"),
        "completion_tokens_scored": n,
        "finish_reason": row["finish_reason"],
        "completion_sha256": hashlib.sha256(json.dumps(row["completion_ids"]).encode()).hexdigest(),
        "metrics": metrics,
        "peak_allocated_gib": torch.cuda.max_memory_allocated(device) / 2**30 if torch.cuda.is_available() else None,
        "seconds": time.monotonic() - started,
    }
    del q0, qhint, p, kl
    gc.collect()
    torch.cuda.empty_cache()
    return result, max_memory


def run(args):
    prepared = load_inputs(args)
    if not torch.cuda.is_available():
        raise RuntimeError("This measurement needs CUDA; no CPU fallback is defined")
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("The configured Qwen3.5 probe requires CUDA BF16 support")

    from peft import PeftModel
    from transformers import AutoModelForCausalLM

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    receipt = {
        "status": "running",
        "start_unix": time.time(),
        "driver_sha256": digest(__file__),
        "config_sha256": digest(CONFIG_PATH),
        "batch_sha256": digest(prepared["batch_path"]),
        "checkpoint_receipt_sha256": digest(prepared["checkpoint_receipt_path"]),
        "model_metadata_sha256": digest(prepared["meta_path"]),
        "model_revision": prepared["meta"]["revision"],
        "checkpoint": str(prepared["checkpoint"]),
        "checkpoint_adapter_sha256": prepared["adapter_sha"],
        "round_one_policy_adapter_sha256": prepared["batch"].get("policy_adapter_sha256"),
        "n_examples": len(prepared["rows"]),
        "ids": [row["id"] for row in prepared["rows"]],
        "distributions": {
            "q0": "frozen base, adapter disabled, unhinted student prompt",
            "qhint": "same frozen base, adapter disabled, numeric-answer-hinted prompt",
            "p": "updated PEFT adapter, enabled, unhinted student prompt",
        },
        "token_alignment": "same completion IDs; logits_to_keep=n+1; use logits[0, :-1], exactly as train_worker.py",
        "kl": "full-vocabulary FP32 KL at temperature 1, token-streamed in chunks of 64; logits CPU-offloaded as BF16",
        "model_copies": 1,
        "thinking": False,
        "device": torch.cuda.get_device_name(0),
        "events": [],
    }
    write_json(out / "receipt.json", receipt)
    started = time.monotonic()
    peak_memory = 0
    try:
        device = torch.device("cuda:0")
        model = AutoModelForCausalLM.from_pretrained(
            prepared["meta"]["snapshot"], dtype=torch.bfloat16, device_map="cuda",
            attn_implementation="sdpa", local_files_only=True)
        # Load one adapter into this base copy. The probe does not instantiate a
        # second frozen model or use the vLLM-mapped adapter for HF forwards.
        model = PeftModel.from_pretrained(
            model, prepared["checkpoint"] / "adapter", adapter_name="opd_probe", is_trainable=False)
        model.set_adapter("opd_probe")
        model.eval()
        for row in prepared["rows"]:
            event, peak_memory = score_one(model, row, device, args.chunk_tokens, peak_memory)
            receipt["events"].append(event)
            write_json(out / "receipt.json", receipt)
            print(json.dumps(event, ensure_ascii=False), flush=True)
        event_metrics = {}
        for name in ("kl_qhint_q0", "kl_qhint_p", "kl_q0_p"):
            vals = [event["metrics"][name]["mean_nats_per_completion_token"]
                    for event in receipt["events"]]
            event_metrics[name] = {
                "mean_across_examples": sum(vals) / len(vals),
                "per_example": vals,
            }
        receipt.update(status="complete", summary=event_metrics,
                       peak_allocated_gib=peak_memory / 2**30,
                       elapsed_seconds=time.monotonic() - started,
                       interpretation_note="This measures distribution movement on fixed base-policy prefixes; it does not score answer quality or teacher quality.")
    except BaseException as exc:
        receipt.update(status="failed", error=repr(exc))
        raise
    finally:
        receipt["end_unix"] = time.time()
        receipt["elapsed_seconds"] = time.monotonic() - started
        write_json(out / "receipt.json", receipt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True, help="Round-one base-policy rollout batch.json")
    parser.add_argument("--checkpoint", required=True, help="Completed train-worker output directory")
    parser.add_argument("--out", required=True, help="New output directory for the probe receipt")
    parser.add_argument("--chunk-tokens", type=int, default=64)
    args = parser.parse_args()
    if not 1 <= args.chunk_tokens <= 1024:
        parser.error("--chunk-tokens must be in [1, 1024]")
    run(args)
