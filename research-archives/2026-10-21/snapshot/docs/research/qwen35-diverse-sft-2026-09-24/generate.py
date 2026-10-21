"""Checkpointed Qwen3.5-9B generation for the diverse SFT study."""

import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODEL = Path("docs/research/qwen35-self-materials-2026-09-23/model.json")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def worker(args):
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams

    meta = json.loads(MODEL.read_text())
    jobs = json.loads(Path(args.jobs).read_text())
    tokenizer = AutoTokenizer.from_pretrained(meta["snapshot"], local_files_only=True)
    settings = dict(
        model=meta["snapshot"], dtype="bfloat16", kv_cache_dtype="auto",
        max_model_len=args.context, max_num_seqs=max(2, args.samples),
        max_num_batched_tokens=1024, gpu_memory_utilization=0.85,
        enforce_eager=True, enable_prefix_caching=False,
        language_model_only=True, seed=2026092419,
    )
    if args.adapter:
        settings.update(enable_lora=True, max_lora_rank=32)
    model = LLM(**settings)
    lora = None
    if args.adapter:
        from vllm.lora.request import LoRARequest
        lora = LoRARequest("diverse_self_sft", 1, str(Path(args.adapter).resolve()))
    out = Path(args.out)
    for index, job in enumerate(jobs):
        prompt = tokenizer.apply_chat_template(
            job["messages"], tokenize=False, add_generation_prompt=True,
            enable_thinking=args.thinking)
        prompt_ids = tokenizer.encode(prompt, add_special_tokens=False)
        assert len(prompt_ids) + args.cap <= args.context, job["id"]
        tick = time.monotonic()
        result = model.generate(
            [{"prompt_token_ids": prompt_ids}],
            SamplingParams(n=args.samples, temperature=args.temperature,
                           top_p=args.top_p, top_k=args.top_k,
                           presence_penalty=args.presence_penalty,
                           max_tokens=args.cap, seed=job["seed"]),
            lora_request=lora,
        )[0]
        assert list(result.prompt_token_ids) == prompt_ids
        for sample, output in enumerate(result.outputs):
            raw = tokenizer.decode(output.token_ids, skip_special_tokens=False)
            final = raw.split("</think>", 1)[-1] if "</think>" in raw else raw
            write(out / f"{job['id']}-{sample}.json", job | {
                "sample": sample, "model": meta["model_id"],
                "revision": meta["revision"], "adapter": args.adapter,
                "prompt_ids": prompt_ids, "raw_text": raw,
                "final_text": final, "completion_ids": list(output.token_ids),
                "finish_reason": output.finish_reason,
                "elapsed_group_seconds": time.monotonic() - tick,
            })
        print(json.dumps({"index": index, "id": job["id"],
                          "finish": [x.finish_reason for x in result.outputs],
                          "tokens": [len(x.token_ids) for x in result.outputs],
                          "seconds": round(time.monotonic() - tick, 1)}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--cap", type=int, default=8192)
    parser.add_argument("--context", type=int, default=16384)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--presence-penalty", type=float, default=0.2)
    parser.add_argument("--thinking", action="store_true")
    parser.add_argument("--adapter")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    if args.worker:
        worker(args)
        return
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    job_path = Path(args.jobs)
    receipt = {
        "status": "running", "jobs_sha256": digest(job_path),
        "driver_sha256": digest(Path(__file__)), "model_metadata_sha256": digest(MODEL),
        "samples": args.samples, "cap": args.cap, "context": args.context,
        "temperature": args.temperature, "top_p": args.top_p,
        "top_k": args.top_k, "presence_penalty": args.presence_penalty,
        "thinking": args.thinking, "adapter": args.adapter,
        "start_unix": time.time(),
    }
    write(out / "receipt.json", receipt)
    command = [sys.executable, str(Path(__file__).resolve()), "--worker",
               "--jobs", str(job_path.resolve()), "--out", str(out.resolve()),
               "--samples", str(args.samples), "--cap", str(args.cap),
               "--context", str(args.context), "--temperature", str(args.temperature),
               "--top-p", str(args.top_p), "--top-k", str(args.top_k),
               "--presence-penalty", str(args.presence_penalty)]
    if args.thinking:
        command.append("--thinking")
    if args.adapter:
        command.extend(["--adapter", args.adapter])
    start = time.monotonic()
    try:
        with (out / "generate.log").open("w") as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=14400)
        receipt["status"] = "complete"
    except BaseException as error:
        receipt.update(status="failed", error=repr(error))
        raise
    finally:
        receipt.update(end_unix=time.time(), elapsed_seconds=time.monotonic()-start)
        write(out / "receipt.json", receipt)


if __name__ == "__main__":
    main()
