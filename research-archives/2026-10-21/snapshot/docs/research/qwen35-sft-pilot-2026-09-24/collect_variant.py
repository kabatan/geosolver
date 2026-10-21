"""Exploratory Qwen3.5-9B self-material generation with explicit decoding knobs."""
import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from qwen.common import file_hash, now, write_json

MODEL = Path("docs/research/qwen35-self-materials-2026-09-23/model.json")
ROOT = Path("qwen/.runtime/qwen35_sft_pilot_20260924")


def worker(args):
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams
    meta = json.loads(MODEL.read_text())
    jobs = json.loads(Path(args.jobs).read_text())
    tokenizer = AutoTokenizer.from_pretrained(meta["snapshot"], local_files_only=True)
    requests = []
    settings = []
    for job in jobs:
        prompt = tokenizer.apply_chat_template(job["messages"], tokenize=False,
                                               add_generation_prompt=True,
                                               enable_thinking=args.thinking)
        ids = tokenizer.encode(prompt, add_special_tokens=False)
        assert len(ids) + args.cap <= args.context, job["id"]
        requests.append(dict(prompt_token_ids=ids))
        settings.append(SamplingParams(n=1, temperature=args.temperature,
                                       top_p=args.top_p, top_k=args.top_k,
                                       presence_penalty=args.presence_penalty,
                                       max_tokens=args.cap, seed=job["seed"]))
    write_json(Path(args.out) / "token-preflight.json", [dict(id=j["id"], prompt_tokens=len(q["prompt_token_ids"]))
                                                       for j,q in zip(jobs, requests)])
    model = LLM(model=meta["snapshot"], dtype="bfloat16", kv_cache_dtype="auto",
                max_model_len=args.context, max_num_seqs=2, max_num_batched_tokens=1024,
                gpu_memory_utilization=0.85, enforce_eager=True,
                enable_prefix_caching=False, language_model_only=True, seed=2026092415)
    start = time.monotonic()
    results = model.generate(requests, settings)
    duration = time.monotonic() - start
    for job, request, result in zip(jobs, requests, results):
        assert list(result.prompt_token_ids) == request["prompt_token_ids"]
        output = result.outputs[0]
        raw = tokenizer.decode(output.token_ids, skip_special_tokens=False)
        final = raw.split("</think>", 1)[-1] if "</think>" in raw else raw
        write_json(Path(args.out) / (job["id"] + ".json"), job | dict(
            model=meta["model_id"], revision=meta["revision"],
            prompt_ids=request["prompt_token_ids"], raw_text=raw,
            final_text=final, completion_ids=list(output.token_ids),
            tokens=len(output.token_ids), finish_reason=output.finish_reason,
            batch_generation_seconds=duration))
        print(json.dumps(dict(id=job["id"], tokens=len(output.token_ids),
                              finish=output.finish_reason)), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--cap", type=int, default=8192)
    parser.add_argument("--context", type=int, default=16384)
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--presence-penalty", type=float, default=0.0)
    parser.add_argument("--thinking", action="store_true")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args()
    if args.worker:
        return worker(args)
    out = ROOT / args.phase
    out.mkdir(parents=True, exist_ok=False)
    receipt = dict(status="running", start_utc=now(), updates=0,
                   jobs_sha256=file_hash(args.jobs), driver_sha256=file_hash(__file__),
                   model_metadata_sha256=file_hash(MODEL), cap=args.cap,
                   context=args.context, temperature=args.temperature,
                   top_p=args.top_p, top_k=args.top_k,
                   presence_penalty=args.presence_penalty, thinking=args.thinking)
    write_json(out / "receipt.json", receipt)
    command = [sys.executable, str(Path(__file__).resolve()), "--worker",
               "--jobs", str(Path(args.jobs).resolve()), "--phase", args.phase,
               "--cap", str(args.cap), "--context", str(args.context),
               "--temperature", str(args.temperature), "--top-p", str(args.top_p),
               "--top-k", str(args.top_k), "--presence-penalty", str(args.presence_penalty),
               "--out", str(out)]
    if args.thinking:
        command.append("--thinking")
    start = time.monotonic()
    try:
        with (out / "generate.log").open("w") as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=3600)
        receipt["status"] = "complete"
    except BaseException as error:
        receipt.update(status="failed", error=repr(error))
        raise
    finally:
        receipt.update(end_utc=now(), elapsed_seconds=time.monotonic()-start)
        write_json(out / "receipt.json", receipt)
        print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
