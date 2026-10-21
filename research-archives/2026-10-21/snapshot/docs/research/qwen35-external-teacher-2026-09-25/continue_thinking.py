"""Exploratory forced-final continuation of length-stopped Qwen thinking traces."""

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

MODEL = Path("docs/research/qwen35-self-materials-2026-09-23/model.json")
EARLY_STOP = (
    "\n\n Considering the limited time by the user, I have to give the "
    "solution based on the thinking directly now.\n</think>\n\n"
)


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--adapter")
    parser.add_argument("--cap", type=int, default=16384)
    parser.add_argument("--context", type=int, default=102400)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    prior_receipt = json.loads((input_dir / "receipt.json").read_text())
    assert prior_receipt["status"] == "complete"
    assert prior_receipt["thinking"] is True
    assert prior_receipt["cap"] == 81920
    assert prior_receipt["context"] == 90112
    assert args.cap == 16384 and args.context == 102400
    sources = []
    for path in sorted(input_dir.glob("*.json")):
        if path.name == "receipt.json":
            continue
        row = json.loads(path.read_text())
        if row["finish_reason"] == "length" and "</think>" not in row["raw_text"]:
            assert len(row["completion_ids"]) == 81920
            assert row["adapter"] == args.adapter
            sources.append((path, row))
    assert sources, "No eligible unfinished Thinking traces"

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    receipt = {
        "status": "running",
        "input_receipt_sha256": digest(input_dir / "receipt.json"),
        "input_files_sha256": {path.name: digest(path) for path, _ in sources},
        "n_inputs": len(sources),
        "cap": args.cap,
        "context": args.context,
        "adapter": args.adapter,
        "early_stop_sha256": digest_bytes(EARLY_STOP.encode()),
        "start_unix": time.time(),
    }
    write(out / "receipt.json", receipt)
    tick = time.monotonic()
    try:
        from transformers import AutoTokenizer
        from vllm import LLM, SamplingParams

        meta = json.loads(MODEL.read_text())
        tokenizer = AutoTokenizer.from_pretrained(meta["snapshot"],
                                                  local_files_only=True)
        forced_ids = tokenizer.encode(EARLY_STOP, add_special_tokens=False)
        close_ids = tokenizer.encode("</think>", add_special_tokens=False)
        assert len(close_ids) == 1 and forced_ids.count(close_ids[0]) == 1
        settings = dict(
            model=meta["snapshot"], dtype="bfloat16", kv_cache_dtype="auto",
            max_model_len=args.context, max_num_seqs=2,
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
            lora = LoRARequest("diverse_self_sft", 1,
                               str(Path(args.adapter).resolve()))
        for path, source in sources:
            assert source["model"] == meta["model_id"]
            assert source["revision"] == meta["revision"]
            prefix_ids = source["prompt_ids"] + source["completion_ids"] + forced_ids
            assert len(prefix_ids) + args.cap <= args.context
            result = model.generate(
                [{"prompt_token_ids": prefix_ids}],
                SamplingParams(n=1, temperature=1.0, top_p=0.95, top_k=20,
                               presence_penalty=1.5, max_tokens=args.cap,
                               seed=source["seed"]),
                lora_request=lora,
            )[0]
            assert list(result.prompt_token_ids) == prefix_ids
            output = result.outputs[0]
            final = tokenizer.decode(output.token_ids,
                                     skip_special_tokens=False)
            write(out / path.name, {
                "id": source["id"], "source_id": source["source_id"],
                "fresh4_instance": source["fresh4_instance"],
                "model": source["model"], "revision": source["revision"],
                "adapter": args.adapter, "seed": source["seed"],
                "original_trace_file": str(path.resolve()),
                "original_trace_sha256": digest(path),
                "forced_ids": forced_ids,
                "prefix_ids_sha256": digest_bytes(
                    json.dumps(prefix_ids, separators=(",", ":")).encode()),
                "raw_final_text": final,
                "completion_ids": list(output.token_ids),
                "finish_reason": output.finish_reason,
            })
            print(json.dumps({"id": source["id"],
                              "tokens": len(output.token_ids),
                              "finish_reason": output.finish_reason}),
                  flush=True)
        receipt["status"] = "complete"
    except BaseException as error:
        receipt.update(status="failed", error=repr(error))
        raise
    finally:
        receipt.update(end_unix=time.time(),
                       elapsed_seconds=time.monotonic() - tick)
        write(out / "receipt.json", receipt)


if __name__ == "__main__":
    main()
