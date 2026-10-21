"""Pre-training diagnostics for the Humpty numeric experiment.

Measures the untrained pinned model on the v2 training set: per-config
accuracy, response length, truncation at the generation cap, GRPO signal
(mixed-correctness groups), and generation throughput. A separate
--train-bench mode times forward+backward passes at realistic sequence
shapes to size the update side of a GRPO step. No training is performed;
the model weights are never modified.

Run as ``python -m qwen.diagnostics`` from the repository root.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .common import digest, now, stable_seed, write_json
from .inference import load_model, rendered
from .models import locked_models

DEFAULT_SYSTEM = "You are a helpful assistant."
EOS_FALLBACK = "<|im_end|>"


# ---------------------------------------------------------------- answer check

# Kept as public imports for existing experiment callers.
from .answer_check import PARSER_VERSION, answers_equal, extract_answer  # noqa: E402


def problem_identity(row):
    return {
        "variant": row.get("variant", "v0"),
        "prompt_sha256": digest(row.get("problem", row.get("prompt"))),
        "label_sha256": digest(row.get("answer_exact")),
        "parser_version": PARSER_VERSION,
    }


def resume_key(row, sample=None):
    return (
        row["id"],
        row["variant"],
        row["prompt_sha256"],
        row["label_sha256"],
        row["sample"] if sample is None else sample,
    )


def resume_keys(path, problems):
    """Legacy records are readable for summaries, never silently resumable."""
    allowed = {(r["id"], *problem_identity(r).values()) for r in problems}
    keys = set()
    if Path(path).exists():
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if any(
                k not in r for k in ("variant", "prompt_sha256", "label_sha256", "parser_version")
            ):
                raise ValueError("Legacy output cannot be resumed; use a new output path")
            if (
                r["id"],
                r["variant"],
                r["prompt_sha256"],
                r["label_sha256"],
                r["parser_version"],
            ) not in allowed:
                raise ValueError("Resume problem, label or parser mismatch")
            key = resume_key(r)
            if key in keys:
                raise ValueError("Duplicate response identity")
            keys.add(key)
    return keys


# ------------------------------------------------------------------ generation


def run_diagnostic_vllm(args):
    """Generate all responses through the offline vLLM engine.

    Uses the same pinned snapshot and sampling settings as the HF path; one
    request per problem with ``n = per_problem`` so prefill is shared.
    """
    import os

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams
    from vllm.inputs import TokensPrompt

    entry = locked_models()["qwen3_4b"]
    snapshot = getattr(args, "snapshot", "") or entry["snapshot_path"]
    tokenizer = AutoTokenizer.from_pretrained(
        snapshot, local_files_only=True, trust_remote_code=False
    )
    problems = [
        json.loads(line)
        for line in Path(args.problems).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if args.limit:
        problems = problems[: args.limit]
    done = resume_keys(args.output, problems)
    spec_config = None
    if args.spec_model:
        spec_config = {
            "method": "eagle3",
            "model": args.spec_model,
            "num_speculative_tokens": args.spec_tokens,
        }
    try:
        llm = LLM(
            model=snapshot,
            tokenizer=snapshot,
            dtype="bfloat16",
            max_model_len=args.context_limit,
            gpu_memory_utilization=args.vllm_memory_util,
            enforce_eager=False,
            trust_remote_code=False,
            kv_cache_dtype=args.kv_cache_dtype,
            speculative_config=spec_config,
            attention_backend=args.attn_backend or None,
            async_scheduling=args.async_scheduling,
            max_num_seqs=args.max_num_seqs,
        )
    except Exception:
        print("vLLM startup failed with CUDA graphs; retrying eager", flush=True)
        llm = LLM(
            model=snapshot,
            tokenizer=snapshot,
            dtype="bfloat16",
            max_model_len=args.context_limit,
            gpu_memory_utilization=args.vllm_memory_util,
            enforce_eager=True,
            trust_remote_code=False,
            kv_cache_dtype=args.kv_cache_dtype,
            speculative_config=spec_config,
            attention_backend=args.attn_backend or None,
            async_scheduling=args.async_scheduling,
            max_num_seqs=args.max_num_seqs,
        )
    requests = []
    for row in problems:
        prompt = row.get("problem") or row["prompt"]
        case = {"system": args.system, "prompt": prompt}
        ids = tokenizer(rendered(tokenizer, case), add_special_tokens=False).input_ids
        requests.append((row, ids))
    started = time.monotonic()
    outputs = llm.generate(
        [TokensPrompt(prompt_token_ids=ids) for _, ids in requests],
        [
            SamplingParams(
                n=args.per_problem,
                temperature=0.6,
                top_p=0.95,
                top_k=20,
                max_tokens=min(args.max_new_tokens, args.context_limit - len(ids)),
                seed=stable_seed("diag", row["id"], problem_identity(row)),
            )
            for row, ids in requests
        ],
    )
    elapsed = time.monotonic() - started
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as sink:
        for (row, ids), request_out in zip(requests, outputs, strict=True):
            for sample, completion in enumerate(request_out.outputs):
                if resume_key({**row, **problem_identity(row)}, sample) in done:
                    continue
                token_ids = list(completion.token_ids)
                finish = "eos" if completion.finish_reason == "stop" else "max_tokens"
                text = tokenizer.decode(token_ids, skip_special_tokens=False)
                expected = row.get("answer_exact")
                got = extract_answer(text) if expected else None
                record = {
                    "id": row["id"],
                    **problem_identity(row),
                    "sample": sample,
                    "prompt_ids": ids,
                    "completion_ids": token_ids,
                    "input_tokens": len(ids),
                    "output_tokens": len(token_ids),
                    "elapsed_seconds": elapsed,
                    "finish_reason": finish,
                    "extracted_answer": got,
                    "answer_exact": expected,
                    "verdict": answers_equal(got, expected) if expected else None,
                    "raw_text": text,
                    "batch_size": len(requests),
                    "batch_first_sample": -1,
                    "batch_elapsed_seconds": 0.0,
                    "engine": "vllm",
                    "utc": now(),
                }
                sink.write(json.dumps(record, ensure_ascii=False) + "\n")
        sink.flush()
    return out_path, elapsed


def generate_batch(torch, tokenizer, model, prompts, seed, max_new_tokens):
    from transformers import set_seed

    encoded = tokenizer(prompts, return_tensors="pt", add_special_tokens=False).to("cuda")
    n_input = encoded.input_ids.shape[1]
    set_seed(seed)
    started = time.monotonic()
    with torch.inference_mode():
        output = model.generate(
            **encoded,
            do_sample=True,
            temperature=0.6,
            top_p=0.95,
            top_k=20,
            max_new_tokens=max_new_tokens,
            use_cache=True,
            pad_token_id=tokenizer.eos_token_id,
        )
    torch.cuda.synchronize()
    elapsed = time.monotonic() - started
    eos_ids = model.generation_config.eos_token_id
    eos_ids = {eos_ids} if isinstance(eos_ids, int) else set(eos_ids)
    pad_id = tokenizer.eos_token_id
    rows = []
    for row in output[:, n_input:]:
        ids = row.tolist()
        # Sequences that finish early are padded with eos_id up to the batch's
        # longest generation; strip the whole trailing run (padding + real eos).
        trailing = 0
        while trailing < len(ids) and ids[len(ids) - 1 - trailing] == pad_id:
            trailing += 1
        real = ids[: len(ids) - trailing] if trailing else ids
        finish = "eos" if trailing or (real and real[-1] in eos_ids) else "max_tokens"
        rows.append({"ids": real, "finish_reason": finish})
    return n_input, elapsed, rows


def run_diagnostic(args):
    entry = locked_models()["qwen3_4b"]
    torch, tokenizer, model = load_model(entry)
    problems = [
        json.loads(line)
        for line in Path(args.problems).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if args.limit:
        problems = problems[: args.limit]
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = resume_keys(out_path, problems)
    with out_path.open("a", encoding="utf-8") as sink:
        for row in problems:
            pending = [
                i
                for i in range(args.per_problem)
                if resume_key({**row, **problem_identity(row)}, i) not in done
            ]
            while pending:
                take = pending[: args.batch]
                pending = pending[args.batch :]
                case = {"system": args.system, "prompt": row["problem"]}
                prompt = rendered(tokenizer, case)
                n_input, elapsed, outs = generate_batch(
                    torch,
                    tokenizer,
                    model,
                    [prompt] * len(take),
                    seed=stable_seed("diag", row["id"], problem_identity(row), take[0]),
                    max_new_tokens=min(
                        args.max_new_tokens,
                        args.context_limit
                        - len(tokenizer.encode(prompt, add_special_tokens=False)),
                    ),
                )
                for sample, out in zip(take, outs, strict=True):
                    text = tokenizer.decode(out["ids"], skip_special_tokens=False)
                    got = extract_answer(text)
                    record = {
                        "id": row["id"],
                        **problem_identity(row),
                        "sample": sample,
                        "completion_ids": out["ids"],
                        "input_tokens": n_input,
                        "output_tokens": len(out["ids"]),
                        "elapsed_seconds": elapsed,
                        "finish_reason": out["finish_reason"],
                        "extracted_answer": got,
                        "answer_exact": row["answer_exact"],
                        "verdict": answers_equal(got, row["answer_exact"]),
                        "raw_text": text,
                        "batch_size": len(take),
                        "batch_first_sample": take[0],
                        "batch_elapsed_seconds": elapsed,
                        "utc": now(),
                    }
                    sink.write(json.dumps(record, ensure_ascii=False) + "\n")
                sink.flush()
                print(
                    f"{row['id']} samples {take}: {elapsed:.1f}s "
                    f"(peak {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB)",
                    flush=True,
                )
    return out_path


# -------------------------------------------------------------- training bench


def run_train_bench(args):
    entry = locked_models()["qwen3_4b"]
    torch, tokenizer, model = load_model(entry)
    del tokenizer
    model.train()
    model.gradient_checkpointing_enable()
    model.config.use_cache = False
    results = []
    # logits over [B,L,V] dominate memory; keep total tokens modest and skip
    # the fp32-upcast loss path — the LM-head matmul is what we are timing.
    for batch, seqlen in [(1, 8192), (2, 4096), (4, 2048), (8, 1024)]:
        ids = torch.randint(1000, 150000, (batch, seqlen), device="cuda")
        for step in range(args.bench_steps + 1):
            model.zero_grad(set_to_none=True)
            torch.cuda.reset_peak_memory_stats()
            started = time.monotonic()
            out = model(input_ids=ids)
            out.logits.mean().backward()
            torch.cuda.synchronize()
            elapsed = time.monotonic() - started
            if step:
                results.append(
                    {
                        "batch": batch,
                        "seqlen": seqlen,
                        "tokens": batch * seqlen,
                        "seconds": elapsed,
                        "tokens_per_second": batch * seqlen / elapsed,
                        "peak_allocated_gib": torch.cuda.max_memory_allocated() / 2**30,
                    }
                )
        del ids
        torch.cuda.empty_cache()
    return results


# ------------------------------------------------------------------- reporting


def summarize(path, run_seconds=None):
    rows = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_id = {}
    for r in rows:
        key = r["id"] + (
            ":" + r["variant"] + ":" + r["prompt_sha256"][:12] if "prompt_sha256" in r else ""
        )
        by_id.setdefault(key, []).append(r)
    tok = [r["output_tokens"] for r in rows]
    trunc = [r for r in rows if r["finish_reason"] == "max_tokens"]
    verdicts = {"correct": 0, "incorrect": 0, "unparsed": 0}
    mixed, all_right, all_wrong = [], [], []
    for pid, group in by_id.items():
        n = sum(1 for r in group if r["verdict"] is True)
        if n == len(group):
            all_right.append(pid)
        elif n == 0:
            all_wrong.append(pid)
        else:
            mixed.append((pid, n, len(group)))
    for r in rows:
        if r["verdict"] is True:
            key = "correct"
        elif r["verdict"] is False:
            key = "incorrect"
        else:
            key = "unparsed"
        verdicts[key] += 1
    seen = set()
    gen_seconds = 0.0
    for r in rows:
        batch_key = (
            r["id"],
            r.get("variant"),
            r.get("prompt_sha256"),
            r.get("batch_first_sample", r["sample"]),
        )
        if batch_key not in seen:
            seen.add(batch_key)
            gen_seconds += r["batch_elapsed_seconds"]
    if run_seconds is not None:
        gen_seconds = run_seconds
    total_out = sum(r["output_tokens"] for r in rows)
    tok_sorted = sorted(tok)
    summary = {
        "responses": len(rows),
        "configs": len(by_id),
        "output_tokens": {
            "total": total_out,
            "mean": total_out / len(rows),
            "p50": tok_sorted[len(tok_sorted) // 2],
            "p90": tok_sorted[int(len(tok_sorted) * 0.9)],
            "max": tok_sorted[-1],
        },
        "truncated_max_tokens": len(trunc),
        "verdicts": verdicts,
        "configs_all_correct": all_right,
        "configs_all_wrong": all_wrong,
        "configs_mixed": mixed,
        "generation_seconds_wall": gen_seconds,
        "aggregate_tokens_per_second": total_out / gen_seconds if gen_seconds else None,
        "utc": now(),
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--problems",
        default="benchmarks/humpty_configurations_v2/training_problems.jsonl",
    )
    parser.add_argument("--per-problem", type=int, default=8)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--max-new-tokens", type=int, default=16384)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--system", default=DEFAULT_SYSTEM)
    parser.add_argument(
        "--output",
        default="qwen/.runtime/diagnostics/pretrain_responses.jsonl",
    )
    parser.add_argument("--summary", default="")
    parser.add_argument("--train-bench", action="store_true")
    parser.add_argument("--bench-steps", type=int, default=2)
    parser.add_argument("--summarize", type=Path, help="Only aggregate an existing JSONL")
    parser.add_argument("--engine", choices=["hf", "vllm"], default="hf")
    parser.add_argument("--vllm-memory-util", type=float, default=0.9)
    parser.add_argument("--context-limit", type=int, default=32768)
    parser.add_argument("--kv-cache-dtype", default="auto")
    parser.add_argument(
        "--snapshot",
        default="",
        help="Override the model snapshot directory (e.g. a merged LoRA checkpoint)",
    )
    parser.add_argument("--attn-backend", default="")
    parser.add_argument("--spec-model", default="")
    parser.add_argument("--spec-tokens", type=int, default=4)
    parser.add_argument("--async-scheduling", action="store_true")
    parser.add_argument("--max-num-seqs", type=int, default=256)
    args = parser.parse_args()

    if args.summarize:
        summary = summarize(args.summarize)
    elif args.train_bench:
        summary = {"train_bench": run_train_bench(args), "utc": now()}
    elif args.engine == "vllm":
        path, elapsed = run_diagnostic_vllm(args)
        summary = summarize(path, run_seconds=elapsed)
        summary["responses_path"] = str(path)
        summary["engine"] = "vllm"
    else:
        path = run_diagnostic(args)
        summary = summarize(path)
        summary["responses_path"] = str(path)
    if args.summary:
        write_json(args.summary, summary)
    sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
