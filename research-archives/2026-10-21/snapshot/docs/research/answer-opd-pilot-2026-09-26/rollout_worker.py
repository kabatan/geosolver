"""Generate one eight-example on-policy batch for answer-conditioned distillation."""

import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

import argparse
import hashlib
import json
import time
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def read_pool(path):
    value = json.loads(Path(path).read_text())
    rows = value["examples"] if isinstance(value, dict) and "examples" in value else value
    if not isinstance(rows, list) or not rows:
        raise ValueError("Training pool must be a nonempty list or object with examples")
    seen = set()
    for row in rows:
        required = ("id", "source_id", "variant", "reference", "student_messages", "teacher_messages")
        if not isinstance(row, dict) or any(key not in row for key in required):
            raise ValueError("Incomplete training pool row")
        if any(key in row for key in ("proof", "proof_label", "target_proof", "teacher_completion_ids")):
            raise ValueError("Training pool must not contain proof targets or teacher completions")
        if not isinstance(row["id"], str) or not row["id"] or row["id"] in seen:
            raise ValueError("Training pool IDs must be unique nonempty strings")
        seen.add(row["id"])
        if not isinstance(row["reference"], (str, int, float)) or isinstance(row["reference"], bool):
            raise ValueError(f"{row['id']}: reference must be a numeric-answer scalar")
        if row["student_messages"] == row["teacher_messages"]:
            raise ValueError(f"{row['id']}: identical student and teacher messages")
        for name in ("student_messages", "teacher_messages"):
            messages = row[name]
            if (not isinstance(messages, list) or not messages or
                    any(not isinstance(msg, dict) or msg.get("role") not in ("system", "user") or
                        not isinstance(msg.get("content"), str) for msg in messages)):
                raise ValueError(f"{row['id']}: malformed {name}")
    return rows


def rollout_settings(config):
    settings = dict(config.get("rollout", {}))
    settings.setdefault("max_num_seqs", 8)
    required = ("batch_size", "generation_max_tokens", "max_model_len",
                "gpu_memory_utilization", "temperature", "top_p", "top_k",
                "presence_penalty", "seed_base")
    if any(key not in settings for key in required):
        raise ValueError(f"Missing rollout settings: {[k for k in required if k not in settings]}")
    if (settings["batch_size"] != 8 or settings["max_num_seqs"] not in (2, 4, 8) or
            not 1 <= settings["generation_max_tokens"] <= 8192 or
            not 1 <= settings["max_model_len"] <= 16384 or
            not 0.7 <= settings["gpu_memory_utilization"] <= 0.85 or
            not 0 < settings["temperature"] <= 2 or
            not 0 < settings["top_p"] <= 1 or
            not isinstance(settings["top_k"], int) or settings["top_k"] < 0 or
            not 0 <= settings["presence_penalty"] <= 2 or
            not isinstance(settings["seed_base"], int)):
        raise ValueError("Rollout settings outside bounded pilot values")
    return settings


def prepare(args):
    from transformers import AutoTokenizer

    config_path, pool_path = Path(args.config).resolve(), Path(args.pool).resolve()
    config = json.loads(config_path.read_text())
    settings = rollout_settings(config)
    meta_path = Path(config["model_metadata"]).resolve()
    meta = json.loads(meta_path.read_text())
    if meta["model_id"] != "Qwen/Qwen3.5-9B" or not Path(meta["snapshot"]).is_dir():
        raise ValueError("Expected local Qwen3.5-9B snapshot")
    pool = read_pool(pool_path)
    if args.round < 1 or args.start_index < 0 or args.start_index + 8 > len(pool):
        raise ValueError("Round/start-index selects outside training pool")
    checkpoint = Path(args.checkpoint).resolve() if args.checkpoint else None
    policy_hash = digest(checkpoint / "adapter-vllm/adapter_model.safetensors") if checkpoint else None
    if checkpoint:
        prior = json.loads((checkpoint / "receipt.json").read_text())
        if (prior.get("status") != "complete" or prior.get("round") != args.round - 1 or
                prior.get("vllm_adapter_sha256") != policy_hash or
                prior.get("model_revision") != meta["revision"]):
            raise ValueError("Rollout checkpoint is incomplete or mismatched")
    elif args.round != 1:
        raise ValueError("Round after one requires a prior checkpoint")
    tokenizer = AutoTokenizer.from_pretrained(meta["snapshot"], local_files_only=True)
    jobs = []
    for offset, row in enumerate(pool[args.start_index:args.start_index + 8]):
        student_text = tokenizer.apply_chat_template(
            row["student_messages"], tokenize=False, add_generation_prompt=True,
            enable_thinking=False)
        teacher_text = tokenizer.apply_chat_template(
            row["teacher_messages"], tokenize=False, add_generation_prompt=True,
            enable_thinking=False)
        student_ids = tokenizer.encode(student_text, add_special_tokens=False)
        teacher_ids = tokenizer.encode(teacher_text, add_special_tokens=False)
        if student_ids == teacher_ids or not student_ids or not teacher_ids:
            raise ValueError(f"{row['id']}: degenerate or empty tokenized prompts")
        if max(len(student_ids), len(teacher_ids)) + settings["generation_max_tokens"] > settings["max_model_len"]:
            raise ValueError(f"{row['id']}: prompt plus generation exceeds rollout context")
        jobs.append(dict(id=row["id"], source_id=row["source_id"], variant=row["variant"],
                         reference=row["reference"], student_prompt_ids=student_ids,
                         teacher_prompt_ids=teacher_ids,
                         seed=settings["seed_base"] + args.start_index + offset))
    return dict(config=config, settings=settings, config_path=config_path, pool_path=pool_path,
                meta_path=meta_path, meta=meta, policy_hash=policy_hash,
                checkpoint=checkpoint, tokenizer=tokenizer, jobs=jobs)


def run(args):
    prepared = prepare(args)
    if args.preflight:
        print(json.dumps(dict(status="preflight_pass", round=args.round,
                              ids=[job["id"] for job in prepared["jobs"]],
                              student_prompt_tokens=[len(job["student_prompt_ids"]) for job in prepared["jobs"]],
                              teacher_prompt_tokens=[len(job["teacher_prompt_ids"]) for job in prepared["jobs"]])), flush=True)
        return
    from vllm import LLM, SamplingParams
    from vllm.lora.request import LoRARequest

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    settings, meta, jobs = prepared["settings"], prepared["meta"], prepared["jobs"]
    receipt = dict(status="running", start_unix=time.time(), round=args.round,
                   start_index=args.start_index, n_examples=len(jobs),
                   ids=[job["id"] for job in jobs],
                   driver_sha256=digest(__file__),
                   config_sha256=digest(prepared["config_path"]),
                   pool_sha256=digest(prepared["pool_path"]),
                   model_metadata_sha256=digest(prepared["meta_path"]),
                   model_revision=meta["revision"],
                   checkpoint=str(prepared["checkpoint"]) if prepared["checkpoint"] else None,
                   policy_adapter_sha256=prepared["policy_hash"], settings=settings)
    write_json(out / "receipt.json", receipt)
    started = time.monotonic()
    try:
        engine_options = dict(model=meta["snapshot"], dtype="bfloat16", kv_cache_dtype="auto",
                              max_model_len=settings["max_model_len"],
                              max_num_seqs=settings["max_num_seqs"],
                              max_num_batched_tokens=1024,
                              gpu_memory_utilization=settings["gpu_memory_utilization"],
                              enforce_eager=True, enable_prefix_caching=False,
                              language_model_only=True, seed=settings["seed_base"])
        if prepared["checkpoint"]:
            engine_options.update(enable_lora=True, max_lora_rank=8)
        engine = LLM(**engine_options)
        adapter = (LoRARequest("opd_policy", 1, str(prepared["checkpoint"] / "adapter-vllm"))
                   if prepared["checkpoint"] else None)
        prompts = [{"prompt_token_ids": job["student_prompt_ids"]} for job in jobs]
        params = [SamplingParams(n=1, seed=job["seed"],
                                 max_tokens=settings["generation_max_tokens"],
                                 temperature=settings["temperature"], top_p=settings["top_p"],
                                 top_k=settings["top_k"],
                                 presence_penalty=settings["presence_penalty"])
                  for job in jobs]
        generation_started = time.monotonic()
        generated = engine.generate(prompts, params, lora_request=adapter)
        generation_seconds = time.monotonic() - generation_started
        if len(generated) != len(jobs):
            raise AssertionError("vLLM returned wrong number of rollout results")
        examples, raw = [], []
        for job, result in zip(jobs, generated, strict=True):
            if list(result.prompt_token_ids) != job["student_prompt_ids"] or len(result.outputs) != 1:
                raise AssertionError(f"{job['id']}: vLLM prompt or sample count mismatch")
            output = result.outputs[0]
            completion = list(output.token_ids)
            if not completion:
                raise AssertionError(f"{job['id']}: empty rollout")
            raw_text = prepared["tokenizer"].decode(completion, skip_special_tokens=False)
            examples.append(dict(id=job["id"], reference=job["reference"],
                                 student_prompt_ids=job["student_prompt_ids"],
                                 teacher_prompt_ids=job["teacher_prompt_ids"],
                                 completion_ids=completion, finish_reason=output.finish_reason,
                                 student_thinking=False, teacher_thinking=False))
            raw.append(dict(id=job["id"], source_id=job["source_id"], variant=job["variant"],
                            seed=job["seed"], raw_text=raw_text, completion_ids=completion,
                            completion_sha256=hashlib.sha256(json.dumps(completion).encode()).hexdigest(),
                            finish_reason=output.finish_reason, tokens=len(completion)))
        batch = dict(round=args.round, policy_adapter_sha256=prepared["policy_hash"], examples=examples)
        write_json(out / "batch.json", batch)
        write_json(out / "raw_rollouts.json", raw)
        generated_tokens = sum(len(row["completion_ids"]) for row in examples)
        receipt.update(status="complete", batch_sha256=digest(out / "batch.json"),
                       raw_rollouts_sha256=digest(out / "raw_rollouts.json"),
                       generated_completion_tokens=generated_tokens,
                       generation_seconds=generation_seconds,
                       generated_tokens_per_second=generated_tokens/generation_seconds,
                       finish_reasons=[row["finish_reason"] for row in examples])
    except BaseException as exc:
        receipt.update(status="failed", error=repr(exc))
        raise
    finally:
        receipt.update(end_unix=time.time(), elapsed_seconds=time.monotonic()-started)
        write_json(out / "receipt.json", receipt)
        print(json.dumps(receipt, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--pool", required=True)
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--start-index", type=int, required=True)
    parser.add_argument("--checkpoint")
    parser.add_argument("--out")
    parser.add_argument("--preflight", action="store_true")
    options = parser.parse_args()
    if not options.preflight and not options.out:
        parser.error("--out is required except for --preflight")
    run(options)
