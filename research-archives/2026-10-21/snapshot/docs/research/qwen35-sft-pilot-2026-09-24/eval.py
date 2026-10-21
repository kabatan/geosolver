"""Immutable Qwen3.5-9B proof evaluation, with an optional LoRA adapter."""
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

HERE = Path(__file__).resolve().parent
MODEL = Path("docs/research/qwen35-self-materials-2026-09-23/model.json")
PROTOCOL = Path("docs/research/qwen35-self-materials-2026-09-23/protocol.json")
ROOT = Path("qwen/.runtime/qwen35_sft_pilot_20260924")


def worker(args):
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams

    meta = json.loads(MODEL.read_text())
    protocol = json.loads(PROTOCOL.read_text())
    jobs = json.loads(Path(args.jobs).read_text())
    tokenizer = AutoTokenizer.from_pretrained(meta["snapshot"], local_files_only=True)
    params = dict(
        model=meta["snapshot"],
        dtype="bfloat16",
        kv_cache_dtype="auto",
        max_model_len=args.context,
        max_num_seqs=2,
        max_num_batched_tokens=1024,
        gpu_memory_utilization=0.85,
        enforce_eager=True,
        enable_prefix_caching=False,
        language_model_only=True,
        seed=2026092401,
    )
    if args.adapter:
        params.update(enable_lora=True, max_lora_rank=32)
    model = LLM(**params)
    lora = None
    if args.adapter:
        from vllm.lora.request import LoRARequest
        lora = LoRARequest("self_sft", 1, str(Path(args.adapter).resolve()))
    for job in jobs:
        prompt = tokenizer.apply_chat_template(
            [{"role": "user", "content": job["prompt"]}],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        ids = tokenizer.encode(prompt, add_special_tokens=False)
        assert len(ids) + args.cap <= args.context, job["id"]
        start = time.monotonic()
        result = model.generate(
            [{"prompt_token_ids": ids}],
            SamplingParams(
                n=args.samples,
                **protocol["sampling"],
                max_tokens=args.cap,
                seed=job["seed"],
            ),
            lora_request=lora,
        )[0]
        assert list(result.prompt_token_ids) == ids
        for sample, output in enumerate(result.outputs):
            raw = tokenizer.decode(output.token_ids, skip_special_tokens=False)
            final = raw.split("</think>", 1)[-1] if "</think>" in raw else raw
            write_json(
                Path(args.out) / f"{job['id']}-{sample}.json",
                dict(
                    id=job["id"],
                    sample=sample,
                    prompt=job["prompt"],
                    prompt_ids=ids,
                    seed=job["seed"],
                    model=meta["model_id"],
                    revision=meta["revision"],
                    adapter=args.adapter,
                    raw_text=raw,
                    final_text=final,
                    completion_ids=list(output.token_ids),
                    finish_reason=output.finish_reason,
                    elapsed_group_seconds=time.monotonic() - start,
                ),
            )
        print(json.dumps({"id": job["id"], "finish": [x.finish_reason for x in result.outputs]}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--samples", type=int, default=2)
    parser.add_argument("--cap", type=int, default=16384)
    parser.add_argument("--context", type=int, default=24576)
    parser.add_argument("--adapter")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args()
    if args.worker:
        return worker(args)
    out = ROOT / args.phase
    out.mkdir(parents=True, exist_ok=False)
    receipt = dict(
        status="running",
        start_utc=now(),
        updates=0,
        jobs_sha256=file_hash(args.jobs),
        model_metadata_sha256=file_hash(MODEL),
        protocol_sha256=file_hash(PROTOCOL),
        driver_sha256=file_hash(__file__),
        adapter=args.adapter,
        samples=args.samples,
        cap=args.cap,
        context=args.context,
    )
    write_json(out / "receipt.json", receipt)
    command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--jobs", str(Path(args.jobs).resolve()), "--phase", args.phase, "--samples", str(args.samples), "--cap", str(args.cap), "--context", str(args.context), "--out", str(out)]
    if args.adapter:
        command += ["--adapter", args.adapter]
    start = time.monotonic()
    try:
        with (out / "generate.log").open("w") as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=7200)
        receipt["status"] = "complete"
    except BaseException as error:
        receipt.update(status="failed", error=repr(error))
        raise
    finally:
        receipt.update(end_utc=now(), elapsed_seconds=time.monotonic() - start)
        write_json(out / "receipt.json", receipt)


if __name__ == "__main__":
    main()
