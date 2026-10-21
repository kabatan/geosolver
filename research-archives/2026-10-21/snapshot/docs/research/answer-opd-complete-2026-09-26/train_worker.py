"""One complete-trajectory round of privileged numeric-answer self-distillation.

The supplied completion is sampled from the current student policy. The teacher
is the same frozen Qwen3.5-9B base with the adapter disabled, conditioned on a
numeric-answer hint. Neither reference values nor proof labels enter the loss.
"""

import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

import argparse
import gc
import hashlib
import importlib.metadata
import json
import math
import resource
import subprocess
import sys
import time
from pathlib import Path

import torch


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


from streamed_kl import ActivationOffload, StreamedHiddenKL, completion_hidden


def cpu_check():
    # Keep CPU validation isolated even when transformer/optimizer imports in
    # a GPU-visible parent have initialized the CUDA runtime incidentally.
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="")
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("test_engine_cpu.py")), "--core"],
                            env=env, capture_output=True, text=True, check=True, timeout=60)
    return json.loads(result.stdout)


def parameters(spec):
    expected = ("seed", "max_completion_tokens", "max_sequence_tokens", "learning_rate",
                "grad_accumulation", "grad_clip", "kl_chunk_tokens", "lora_rank",
                "lora_alpha", "lora_modules")
    missing = [key for key in expected if key not in spec]
    if missing:
        raise ValueError(f"Missing config keys: {missing}")
    bounded = {key: spec[key] for key in expected}
    bounded["activation_offload"] = spec.get("activation_offload", "cpu")
    bounded["cpu_offload_max_gib"] = spec.get("cpu_offload_max_gib", 12)
    bounded["cpu_offload_reserve_gib"] = spec.get("cpu_offload_reserve_gib", 4)
    bounded["engine"] = "streamed_hidden_full_vocab_kl_v1"
    if (not isinstance(bounded["seed"], int) or isinstance(bounded["seed"], bool) or
            not isinstance(bounded["max_completion_tokens"], int) or
            not 1024 <= bounded["max_completion_tokens"] <= 81920 or
            not isinstance(bounded["max_sequence_tokens"], int) or
            not 1 <= bounded["max_sequence_tokens"] <= 98304 or
            bounded["learning_rate"] != 5e-6 or bounded["grad_accumulation"] != 4 or
            not 0 < bounded["grad_clip"] <= 10 or
            not isinstance(bounded["kl_chunk_tokens"], int) or
            not 1 <= bounded["kl_chunk_tokens"] <= 256 or
            bounded["activation_offload"] not in ("cpu", "none") or
            not isinstance(bounded["cpu_offload_max_gib"], (int, float)) or
            not 0 < bounded["cpu_offload_max_gib"] <= 64 or
            not isinstance(bounded["cpu_offload_reserve_gib"], (int, float)) or
            not 1 <= bounded["cpu_offload_reserve_gib"] <= 32 or
            bounded["lora_rank"] != 8 or bounded["lora_alpha"] != 16 or
            not isinstance(bounded["lora_modules"], list) or not bounded["lora_modules"]):
        raise ValueError("Config exceeds pilot bounds or changes fixed optimizer/LoRA settings")
    return bounded


def parameter_changes(old, new):
    if not isinstance(old, dict):
        return {"missing_prior_parameters": True}
    return {k: {"old": old.get(k), "new": new.get(k)}
            for k in sorted(old.keys() | new.keys()) if old.get(k) != new.get(k)}


def compatible_prior_parameters(old, new, spec):
    changes = parameter_changes(old, new)
    if not changes:
        return True
    revision = spec.get("prior_parameter_revision", {})
    capacity_keys = {"max_completion_tokens", "max_sequence_tokens", "kl_chunk_tokens",
                     "activation_offload", "engine", "cpu_offload_max_gib", "cpu_offload_reserve_gib"}
    old_hash = hashlib.sha256(json.dumps(old, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return (isinstance(revision, dict) and revision.get("prior_parameters_sha256") == old_hash and
            isinstance(revision.get("reason"), str) and bool(revision["reason"].strip()) and
            set(changes).issubset(capacity_keys) and
            set(changes) == set(revision.get("allowed_changes", [])))


def _ids(value, name, vocab_size):
    if (not isinstance(value, list) or not value or
            any(type(token) is not int or token < 0 or token >= vocab_size for token in value)):
        raise ValueError(f"{name} must be a nonempty in-vocabulary integer token list")
    return value


def prepare_batch(batch, spec, vocab_size, prior_hash):
    if type(batch.get("round")) is not int or batch["round"] < 1:
        raise ValueError("Batch round must be a positive integer")
    if "policy_adapter_sha256" not in batch or batch["policy_adapter_sha256"] != prior_hash:
        raise ValueError("Rollout policy adapter hash does not match training entry checkpoint")
    examples = batch.get("examples")
    if not isinstance(examples, list) or not 1 <= len(examples) <= 32:
        raise ValueError("Pilot batch requires 1–32 examples")
    seen = set()
    prepared = []
    for raw in examples:
        required = ("id", "reference", "student_prompt_ids", "teacher_prompt_ids",
                    "completion_ids", "finish_reason", "student_thinking", "teacher_thinking")
        if not isinstance(raw, dict) or any(key not in raw for key in required):
            raise ValueError("Incomplete rollout row")
        if any(key in raw for key in ("proof", "proof_label", "target_proof", "teacher_completion_ids")):
            raise ValueError("Proof targets and external teacher continuations are forbidden")
        row_id = raw["id"]
        if not isinstance(row_id, str) or not row_id or row_id in seen:
            raise ValueError("Rollout IDs must be unique nonempty strings")
        seen.add(row_id)
        if not isinstance(raw["reference"], (str, int, float)) or isinstance(raw["reference"], bool):
            raise ValueError(f"{row_id}: reference must be a numeric answer scalar")
        if type(raw["student_thinking"]) is not bool or type(raw["teacher_thinking"]) is not bool:
            raise ValueError(f"{row_id}: thinking flags must be boolean")
        student = _ids(raw["student_prompt_ids"], "student_prompt_ids", vocab_size)
        teacher = _ids(raw["teacher_prompt_ids"], "teacher_prompt_ids", vocab_size)
        full = _ids(raw["completion_ids"], "completion_ids", vocab_size)
        if student == teacher:
            raise ValueError(f"{row_id}: identical student/teacher prompts give a degenerate teacher")
        if len(full) > spec["max_completion_tokens"]:
            raise ValueError(f"{row_id}: refusing to truncate the supplied completion")
        completion = full
        if max(len(student), len(teacher)) + len(completion) > spec["max_sequence_tokens"]:
            raise ValueError(f"{row_id}: exceeds max sequence tokens")
        reason = raw["finish_reason"]
        if reason not in ("stop", "eos", "end_of_sequence"):
            raise ValueError(f"{row_id}: incomplete/capped trajectory is not a complete-trajectory training example")
        prepared.append(dict(id=row_id, reference=raw["reference"], student_prompt_ids=student,
                             teacher_prompt_ids=teacher, completion_ids=completion,
                             source_completion_tokens=len(full), finish_reason=reason,
                             prefix_is_complete_answer=(len(completion) == len(full) and
                                                        reason in ("stop", "eos", "end_of_sequence")),
                             student_thinking=raw["student_thinking"],
                             teacher_thinking=raw["teacher_thinking"]))
    return prepared


def grad_norm_for_example(trainable, prior_grads, multiplier):
    squared = 0.0
    for param, before in zip(trainable, prior_grads):
        after = param.grad
        if after is None:
            continue
        delta = after.detach().float().cpu()
        if before is not None:
            delta -= before
        squared += float(delta.square().sum())
    return math.sqrt(squared) * multiplier


def verify_optimizer_state(expected, actual):
    if isinstance(expected, torch.Tensor):
        if (not isinstance(actual, torch.Tensor) or expected.dtype != actual.dtype or
                not torch.equal(expected.detach().cpu(), actual.detach().cpu())):
            raise AssertionError("Optimizer tensor changed during save/reload")
    elif isinstance(expected, dict):
        if not isinstance(actual, dict) or expected.keys() != actual.keys():
            raise AssertionError("Optimizer state keys changed during save/reload")
        for key in expected:
            verify_optimizer_state(expected[key], actual[key])
    elif isinstance(expected, (list, tuple)):
        if type(expected) is not type(actual) or len(expected) != len(actual):
            raise AssertionError("Optimizer state sequence changed during save/reload")
        for one, two in zip(expected, actual):
            verify_optimizer_state(one, two)
    elif expected != actual:
        raise AssertionError("Optimizer scalar changed during save/reload")


def optimizer_step_values(optimizer):
    return sorted({int(value["step"]) for value in optimizer.state_dict()["state"].values()})


def verify_saved_adapter(model, adapter_path):
    from peft import get_peft_model_state_dict
    from safetensors.torch import load_file

    expected = {name: value.detach().cpu().contiguous()
                for name, value in get_peft_model_state_dict(model).items()}
    actual = load_file(str(adapter_path / "adapter_model.safetensors"), device="cpu")
    if expected.keys() != actual.keys():
        raise AssertionError("Saved adapter tensor keys differ from live adapter")
    differences = {name: float((expected[name].float() - actual[name].float()).abs().max())
                   for name in expected if not torch.equal(expected[name], actual[name])}
    if differences:
        raise AssertionError(f"Saved adapter differs from live weights: {differences}")
    return len(expected)


def export_vllm_adapter(source, target):
    """Translate text-only PEFT layer names to vLLM's Qwen3.5 wrapper."""
    from safetensors import safe_open
    from safetensors.torch import load_file, save_file

    old_prefix = "base_model.model.model.layers."
    new_prefix = "base_model.model.model.language_model.layers."
    source_file = source / "adapter_model.safetensors"
    target.mkdir(parents=True, exist_ok=False)
    mapped = {}
    with safe_open(source_file, framework="pt", device="cpu") as handle:
        metadata = handle.metadata()
        for key in handle.keys():
            if not key.startswith(old_prefix):
                raise AssertionError(f"Unexpected Qwen3.5 PEFT tensor key: {key}")
            translated = new_prefix + key[len(old_prefix):]
            if translated in mapped:
                raise AssertionError(f"Duplicate mapped tensor key: {translated}")
            mapped[translated] = handle.get_tensor(key)
    if len(mapped) != 400:
        raise AssertionError(f"Expected 400 mapped Qwen3.5 LoRA tensors, got {len(mapped)}")
    target_file = target / "adapter_model.safetensors"
    save_file(mapped, str(target_file), metadata=metadata)
    (target / "adapter_config.json").write_bytes((source / "adapter_config.json").read_bytes())
    loaded = load_file(str(target_file), device="cpu")
    if mapped.keys() != loaded.keys() or any(not torch.equal(mapped[key], loaded[key]) for key in mapped):
        raise AssertionError("vLLM adapter export changed tensor values")
    mapping = dict(source_adapter_sha256=digest(source_file),
                   vllm_adapter_sha256=digest(target_file), n_tensors=len(mapped),
                   old_prefix=old_prefix, new_prefix=new_prefix,
                   verified_equal_tensor_values=True)
    write_json(target / "mapping-receipt.json", mapping)
    return mapping


def run(args):
    from peft import LoraConfig, PeftModel, TaskType, get_peft_model
    from transformers import AutoModelForCausalLM

    config_path, batch_path = Path(args.config).resolve(), Path(args.batch).resolve()
    spec = json.loads(config_path.read_text())
    fixed = parameters(spec)
    meta_path = Path(spec["model_metadata"]).resolve()
    meta = json.loads(meta_path.read_text())
    if meta["model_id"] != "Qwen/Qwen3.5-9B" or not Path(meta["snapshot"]).is_dir():
        raise ValueError("Expected local Qwen3.5-9B snapshot")
    prior = Path(spec["prior_checkpoint"]).resolve() if spec.get("prior_checkpoint") else None
    prior_hash = digest(prior / "adapter/adapter_model.safetensors") if prior else None
    prior_vllm_hash = digest(prior / "adapter-vllm/adapter_model.safetensors") if prior else None
    prior_optimizer_hash = digest(prior / "optimizer.pt") if prior else None
    if prior:
        prior_receipt = json.loads((prior / "receipt.json").read_text())
        if (prior_receipt.get("status") != "complete" or
                prior_receipt.get("adapter_sha256") != prior_hash or
                prior_receipt.get("vllm_adapter_sha256") != prior_vllm_hash or
                prior_receipt.get("optimizer_sha256") != prior_optimizer_hash or
                not compatible_prior_parameters(prior_receipt.get("training_parameters"), fixed, spec) or
                prior_receipt.get("model_revision") != meta["revision"]):
            raise ValueError("Prior checkpoint is incomplete or incompatible")
    batch = json.loads(batch_path.read_text())
    # The local model config supplies the vocabulary bound without loading weights.
    from transformers import AutoConfig
    model_config = AutoConfig.from_pretrained(meta["snapshot"], local_files_only=True)
    rows = prepare_batch(batch, fixed, model_config.text_config.vocab_size, prior_vllm_hash)
    if prior and batch["round"] != prior_receipt["round"] + 1:
        raise ValueError("Round does not immediately follow prior checkpoint")
    if not prior and batch["round"] != 1:
        raise ValueError("First round must start from base policy")
    if args.preflight:
        result = dict(status="preflight_pass", round=batch["round"], n_examples=len(rows),
                      training_parameters=fixed,
                      prior_parameter_revision=parameter_changes(prior_receipt["training_parameters"], fixed) if prior else None,
                      batch_sha256=digest(batch_path),
                      config_sha256=digest(config_path), engine_sha256=digest(Path(__file__).with_name("streamed_kl.py")),
                      student_sequence_tokens=[len(r["student_prompt_ids"])+len(r["completion_ids"]) for r in rows],
                      teacher_sequence_tokens=[len(r["teacher_prompt_ids"])+len(r["completion_ids"]) for r in rows],
                      completion_tokens=[len(r["completion_ids"]) for r in rows],
                      no_completion_truncation=True, cuda_executed=False)
        print(json.dumps(result), flush=True)
        return
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    receipt = dict(status="running", round=batch["round"], start_unix=time.time(),
                   driver_sha256=digest(__file__), engine_sha256=digest(Path(__file__).with_name("streamed_kl.py")),
                   config_sha256=digest(config_path),
                   batch_sha256=digest(batch_path), model_metadata_sha256=digest(meta_path),
                   model_revision=meta["revision"], prior_checkpoint=str(prior) if prior else None,
                   prior_adapter_sha256=prior_hash, prior_vllm_adapter_sha256=prior_vllm_hash,
                   prior_optimizer_sha256=prior_optimizer_hash,
                   training_parameters=fixed,
                   prior_parameter_revision=parameter_changes(prior_receipt["training_parameters"], fixed) if prior else None,
                   authorized_prior_parameter_revision=spec.get("prior_parameter_revision"),
                   n_examples=len(rows), updates=0, cpu_check=cpu_check(),
                   objective="full-vocabulary forward KL(teacher||student), FP32 normalization, T=1",
                   teacher="same frozen base; adapter disabled; numeric-answer prompt",
                   gradient_accumulation="one pass, four examples per optimizer step; final partial group averages its actual examples",
                   token_alignment="backbone.last_hidden_state[0, -n-1:-1], equivalent to logits_to_keep=n+1 then [0,:-1]",
                   no_completion_truncation=True,
                   capacity_note="32k/81k GPU backbone+offload memory and runtime unmeasured until authorized full-length run",
                   versions={name: importlib.metadata.version(name)
                             for name in ("torch", "transformers", "peft", "safetensors")})
    write_json(out / "receipt.json", receipt)
    started = time.monotonic()
    try:
        torch.manual_seed(fixed["seed"])
        torch.cuda.manual_seed_all(fixed["seed"])
        torch.cuda.reset_peak_memory_stats()
        model = AutoModelForCausalLM.from_pretrained(
            meta["snapshot"], dtype=torch.bfloat16, device_map="cuda",
            attn_implementation="sdpa", local_files_only=True)
        if prior:
            model = PeftModel.from_pretrained(model, prior / "adapter", is_trainable=True)
        else:
            model = get_peft_model(model, LoraConfig(
                r=fixed["lora_rank"], lora_alpha=fixed["lora_alpha"], lora_dropout=0.0,
                target_modules=fixed["lora_modules"], bias="none", task_type=TaskType.CAUSAL_LM))
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
        base = model.get_base_model()
        backbone, head = base.model, base.lm_head
        if not isinstance(head, torch.nn.Linear) or head.weight.requires_grad or head.bias is not None:
            raise AssertionError("Streamed KL requires the unchanged frozen bias-free LM head")
        if getattr(base.config, "attention_dropout", 0) != 0:
            raise AssertionError("Nonzero backbone dropout changes the fixed objective")
        named_trainable = [(name, param) for name, param in model.named_parameters() if param.requires_grad]
        if not named_trainable or any("lora_" not in name for name, _ in named_trainable):
            raise AssertionError("Only LoRA parameters may be trained")
        trainable = [param for _, param in named_trainable]
        before = {name: param.detach().float().cpu().clone() for name, param in named_trainable}
        optimizer = torch.optim.AdamW(trainable, lr=fixed["learning_rate"], weight_decay=0)
        if prior:
            optimizer.load_state_dict(torch.load(prior / "optimizer.pt", map_location="cpu", weights_only=True))
        receipt["optimizer_state_loaded"] = bool(prior)
        receipt["optimizer_step_values_before"] = optimizer_step_values(optimizer)
        prior_steps = receipt["optimizer_step_values_before"]
        if prior:
            if len(prior_steps) != 1:
                raise AssertionError("Prior optimizer must have one common cumulative step value")
            prior_updates = prior_receipt.get("global_updates", prior_steps[0])
            if prior_steps != [prior_updates]:
                raise AssertionError("Prior receipt cumulative updates disagree with optimizer steps")
        else:
            prior_updates = 0
            if prior_steps:
                raise AssertionError("Fresh optimizer unexpectedly contains steps")
        receipt["prior_global_updates"] = prior_updates
        receipt["global_updates"] = prior_updates
        receipt["trainable_parameters"] = sum(param.numel() for param in trainable)
        optimizer.zero_grad(set_to_none=True)
        max_allocated, max_reserved = 0, 0
        for idx, row in enumerate(rows):
            tick = time.monotonic()
            n = len(row["completion_ids"])
            group_size = min(fixed["grad_accumulation"], len(rows) -
                             (idx // fixed["grad_accumulation"]) * fixed["grad_accumulation"])
            prior_grads = [param.grad.detach().float().cpu().clone() if param.grad is not None else None
                           for param in trainable]
            torch.cuda.reset_peak_memory_stats()
            teacher_input = torch.tensor([row["teacher_prompt_ids"] + row["completion_ids"]],
                                         dtype=torch.long, device="cuda")
            model.eval()
            with torch.no_grad(), model.disable_adapter():
                teacher_output = backbone(input_ids=teacher_input, use_cache=False, return_dict=True)
                teacher_cpu = completion_hidden(teacher_output, n).detach().cpu().contiguous()
            del teacher_output, teacher_input
            gc.collect()
            torch.cuda.empty_cache()
            student_input = torch.tensor([row["student_prompt_ids"] + row["completion_ids"]],
                                         dtype=torch.long, device="cuda")
            model.train()
            offload = ActivationOffload(model.parameters(), fixed["activation_offload"] == "cpu",
                                       int(fixed["cpu_offload_max_gib"]*2**30),
                                       int(fixed["cpu_offload_reserve_gib"]*2**30))
            with offload.context():
                student_output = backbone(input_ids=student_input, use_cache=False, return_dict=True)
                student_hidden = completion_hidden(student_output, n)
            kl, quartile_values = StreamedHiddenKL.apply(student_hidden, teacher_cpu,
                                                        head.weight, fixed["kl_chunk_tokens"])
            if not torch.isfinite(kl):
                raise AssertionError(f"Nonfinite KL on {row['id']}")
            quarters = [float(v) if torch.isfinite(v) else None for v in quartile_values]
            (kl / group_size).backward()
            per_example_grad_norm = grad_norm_for_example(trainable, prior_grads, group_size)
            if not math.isfinite(per_example_grad_norm):
                raise AssertionError(f"Nonfinite gradient on {row['id']}")
            torch.cuda.synchronize()
            event = dict(id=row["id"], round=batch["round"], example_index=idx,
                         kl=float(kl.detach()), kl_by_completion_quartile=quarters,
                         grad_norm_before_accumulation=per_example_grad_norm,
                         student_prompt_tokens=len(row["student_prompt_ids"]),
                         teacher_prompt_tokens=len(row["teacher_prompt_ids"]),
                         trained_completion_tokens=n,
                         source_completion_tokens=row["source_completion_tokens"],
                         finish_reason=row["finish_reason"],
                         prefix_is_complete_answer=row["prefix_is_complete_answer"],
                         student_thinking=row["student_thinking"],
                         teacher_thinking=row["teacher_thinking"],
                         completion_sha256=hashlib.sha256(json.dumps(row["completion_ids"]).encode()).hexdigest(),
                         activation_offload=offload.stats(),
                         teacher_hidden_cpu_bytes=teacher_cpu.numel()*teacher_cpu.element_size(),
                         host_peak_rss_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024/2**30,
                         peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,
                         peak_reserved_gib=torch.cuda.max_memory_reserved()/2**30,
                         seconds=time.monotonic()-tick)
            max_allocated = max(max_allocated, event["peak_allocated_gib"])
            max_reserved = max(max_reserved, event["peak_reserved_gib"])
            del prior_grads, student_input, student_output, student_hidden, teacher_cpu, kl, quartile_values, offload
            gc.collect()
            torch.cuda.empty_cache()
            if (idx + 1) % fixed["grad_accumulation"] == 0 or idx + 1 == len(rows):
                norm = torch.nn.utils.clip_grad_norm_(trainable, fixed["grad_clip"])
                if not torch.isfinite(norm):
                    raise AssertionError("Nonfinite accumulated gradient norm")
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
                receipt["updates"] += 1
                receipt["global_updates"] = prior_updates + receipt["updates"]
                steps = optimizer_step_values(optimizer)
                if steps != [receipt["global_updates"]]:
                    raise AssertionError("Optimizer step values disagree with actual cumulative updates")
                receipt["optimizer_step_min"], receipt["optimizer_step_max"] = min(steps), max(steps)
                event["optimizer_update"] = receipt["updates"]
                event["global_optimizer_update"] = receipt["global_updates"]
                event["accumulated_grad_norm_before_clipping"] = float(norm)
            with (out / "examples.jsonl").open("a") as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            print(json.dumps(event, ensure_ascii=False), flush=True)
            receipt["examples_processed"] = idx + 1
            write_json(out / "receipt.json", receipt)
        changed = sum(not torch.equal(before[name], param.detach().float().cpu())
                      for name, param in named_trainable)
        if changed == 0:
            raise AssertionError("No LoRA weights changed; inspect same-point degeneracy")
        adapter_path = out / "adapter"
        model.save_pretrained(adapter_path, safe_serialization=True)
        saved_tensors = verify_saved_adapter(model, adapter_path)
        mapping = export_vllm_adapter(adapter_path, out / "adapter-vllm")
        torch.save(optimizer.state_dict(), out / "optimizer.pt")
        reloaded_optimizer = torch.load(out / "optimizer.pt", map_location="cpu", weights_only=True)
        verify_optimizer_state(optimizer.state_dict(), reloaded_optimizer)
        saved_steps = sorted({int(s["step"]) for s in reloaded_optimizer["state"].values()})
        if saved_steps != [prior_updates + receipt["updates"]]:
            raise AssertionError("Saved optimizer steps disagree with the expected global update count")
        if len(reloaded_optimizer["state"]) != len(trainable):
            raise AssertionError("Not every trainable LoRA tensor has a saved optimizer state")
        receipt.update(status="complete", changed_lora_tensors=changed,
                       total_lora_tensors=len(before), saved_adapter_tensors_verified=saved_tensors,
                       optimizer_state_entries=len(reloaded_optimizer["state"]),
                       optimizer_state_save_reload_equal=True,
                       optimizer_step_values_after=optimizer_step_values(optimizer),
                       adapter_sha256=digest(adapter_path / "adapter_model.safetensors"),
                       vllm_adapter_sha256=mapping["vllm_adapter_sha256"],
                       vllm_adapter_tensors_verified=mapping["n_tensors"],
                       optimizer_sha256=digest(out / "optimizer.pt"),
                       peak_allocated_gib=max_allocated, peak_reserved_gib=max_reserved,
                       trained_completion_tokens=sum(len(row["completion_ids"]) for row in rows),
                       truncated_prefixes=sum(not row["prefix_is_complete_answer"] for row in rows))
    except BaseException as exc:
        receipt.update(status="failed", error=repr(exc))
        raise
    finally:
        receipt.update(end_unix=time.time(), elapsed_seconds=time.monotonic()-started)
        write_json(out / "receipt.json", receipt)
        print(json.dumps(receipt, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpu-check", action="store_true")
    parser.add_argument("--preflight", action="store_true", help="Validate config/batch/token lengths without CUDA")
    parser.add_argument("--config")
    parser.add_argument("--batch")
    parser.add_argument("--out")
    options = parser.parse_args()
    if options.cpu_check:
        print(json.dumps(cpu_check()), flush=True)
    elif options.config and options.batch and (options.out or options.preflight):
        run(options)
    else:
        parser.error("Use --cpu-check or provide --config, --batch, and --out")
