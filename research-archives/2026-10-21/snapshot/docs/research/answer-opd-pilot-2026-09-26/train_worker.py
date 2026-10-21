"""One bounded round of privileged numeric-answer, on-policy self-distillation.

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


class ChunkedForwardKL(torch.autograd.Function):
    """Exact full-vocabulary KL(teacher||student), FP32, temperature one.

    Keep frozen teacher logits on CPU and recompute token-chunk probabilities
    in backward. The student model's logits still own their normal LM graph.
    """

    @staticmethod
    def forward(ctx, student, teacher_cpu, chunk_size):
        if (student.ndim != 2 or teacher_cpu.shape != student.shape or
                teacher_cpu.device.type != "cpu" or teacher_cpu.requires_grad or
                student.shape[0] == 0 or chunk_size < 1):
            raise ValueError("Invalid shapes, devices, or chunk size for KL")
        ctx.save_for_backward(student, teacher_cpu)
        ctx.chunk_size = chunk_size
        total = torch.zeros((), device=student.device, dtype=torch.float32)
        for start in range(0, student.shape[0], chunk_size):
            end = min(start + chunk_size, student.shape[0])
            logp = student[start:end].float().log_softmax(-1)
            logq = teacher_cpu[start:end].to(student.device).float().log_softmax(-1)
            total += (logq.exp() * (logq - logp)).sum()
        return total / student.shape[0]

    @staticmethod
    def backward(ctx, grad_output):
        student, teacher_cpu = ctx.saved_tensors
        grad = torch.empty_like(student)
        for start in range(0, student.shape[0], ctx.chunk_size):
            end = min(start + ctx.chunk_size, student.shape[0])
            p = student[start:end].float().softmax(-1)
            q = teacher_cpu[start:end].to(student.device).float().softmax(-1)
            grad[start:end] = ((p - q) * grad_output / student.shape[0]).to(student.dtype)
        return grad, None, None


@torch.no_grad()
def kl_quartiles(student, teacher_cpu, chunk_size):
    """Four position-segment KL means without retaining a softmax graph."""
    n = student.shape[0]
    means = []
    for quarter in range(4):
        begin, end = n * quarter // 4, n * (quarter + 1) // 4
        if begin == end:
            means.append(None)
            continue
        total = torch.zeros((), device=student.device, dtype=torch.float32)
        for start in range(begin, end, chunk_size):
            stop = min(start + chunk_size, end)
            logp = student[start:stop].float().log_softmax(-1)
            logq = teacher_cpu[start:stop].to(student.device).float().log_softmax(-1)
            total += (logq.exp() * (logq - logp)).sum()
        means.append(float(total / (end - begin)))
    return means


def cpu_check():
    torch.manual_seed(20260926)
    student = torch.randn(7, 19, dtype=torch.float32, requires_grad=True)
    teacher = torch.randn(7, 19, dtype=torch.float32)
    logq = teacher.log_softmax(-1)
    dense = (logq.exp() * (logq - student.log_softmax(-1))).sum() / 7
    dense_grad, = torch.autograd.grad(dense, student)
    other = student.detach().clone().requires_grad_(True)
    chunked = ChunkedForwardKL.apply(other, teacher, 3)
    chunked_grad, = torch.autograd.grad(chunked, other)
    assert torch.allclose(dense, chunked, atol=1e-6, rtol=1e-6)
    assert torch.allclose(dense_grad, chunked_grad, atol=1e-7, rtol=1e-6)
    quarters = kl_quartiles(other, teacher, 3)
    counts = [7 * (quarter+1)//4 - 7*quarter//4 for quarter in range(4)]
    assert abs(sum(value * count for value, count in zip(quarters, counts)) / 7 - float(dense.detach())) < 1e-6
    same = student.detach().clone().requires_grad_(True)
    zero = ChunkedForwardKL.apply(same, same.detach().clone(), 3)
    zero_grad, = torch.autograd.grad(zero, same)
    assert abs(float(zero.detach())) < 1e-6 and float(zero_grad.abs().max()) < 1e-7
    return dict(status="pass", dense_kl=float(dense.detach()), chunked_kl=float(chunked.detach()),
                max_abs_gradient_difference=float((dense_grad-chunked_grad).abs().max()),
                identical_distribution_kl=float(zero.detach()), quartile_kl=quarters)


def parameters(spec):
    expected = ("seed", "max_completion_tokens", "max_sequence_tokens", "learning_rate",
                "grad_accumulation", "grad_clip", "kl_chunk_tokens", "lora_rank",
                "lora_alpha", "lora_modules")
    missing = [key for key in expected if key not in spec]
    if missing:
        raise ValueError(f"Missing config keys: {missing}")
    bounded = {key: spec[key] for key in expected}
    if (not isinstance(bounded["seed"], int) or isinstance(bounded["seed"], bool) or
            not isinstance(bounded["max_completion_tokens"], int) or
            not 1024 <= bounded["max_completion_tokens"] <= 4096 or
            not isinstance(bounded["max_sequence_tokens"], int) or
            not 1 <= bounded["max_sequence_tokens"] <= 8192 or
            bounded["learning_rate"] != 5e-6 or bounded["grad_accumulation"] != 4 or
            not 0 < bounded["grad_clip"] <= 10 or
            not isinstance(bounded["kl_chunk_tokens"], int) or
            not 1 <= bounded["kl_chunk_tokens"] <= 256 or
            bounded["lora_rank"] != 8 or bounded["lora_alpha"] != 16 or
            not isinstance(bounded["lora_modules"], list) or not bounded["lora_modules"]):
        raise ValueError("Config exceeds pilot bounds or changes fixed optimizer/LoRA settings")
    return bounded


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
        completion = full[:spec["max_completion_tokens"]]
        if max(len(student), len(teacher)) + len(completion) > spec["max_sequence_tokens"]:
            raise ValueError(f"{row_id}: exceeds max sequence tokens")
        reason = raw["finish_reason"]
        if not isinstance(reason, str) or not reason:
            raise ValueError(f"{row_id}: missing finish reason")
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
                prior_receipt.get("training_parameters") != fixed or
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
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    receipt = dict(status="running", round=batch["round"], start_unix=time.time(),
                   driver_sha256=digest(__file__), config_sha256=digest(config_path),
                   batch_sha256=digest(batch_path), model_metadata_sha256=digest(meta_path),
                   model_revision=meta["revision"], prior_checkpoint=str(prior) if prior else None,
                   prior_adapter_sha256=prior_hash, prior_vllm_adapter_sha256=prior_vllm_hash,
                   prior_optimizer_sha256=prior_optimizer_hash,
                   training_parameters=fixed,
                   n_examples=len(rows), updates=0, cpu_check=cpu_check(),
                   objective="full-vocabulary forward KL(teacher||student), FP32 normalization, T=1",
                   teacher="same frozen base; adapter disabled; numeric-answer prompt",
                   gradient_accumulation="one pass, four examples per optimizer step",
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
        named_trainable = [(name, param) for name, param in model.named_parameters() if param.requires_grad]
        if not named_trainable or any("lora_" not in name for name, _ in named_trainable):
            raise AssertionError("Only LoRA parameters may be trained")
        trainable = [param for _, param in named_trainable]
        before = {name: param.detach().float().cpu().clone() for name, param in named_trainable}
        optimizer = torch.optim.AdamW(trainable, lr=fixed["learning_rate"], weight_decay=0)
        if prior:
            optimizer.load_state_dict(torch.load(prior / "optimizer.pt", map_location="cpu", weights_only=True))
        receipt["optimizer_state_loaded"] = bool(prior)
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
                teacher_output = model(input_ids=teacher_input, use_cache=False, logits_to_keep=n+1)
                teacher_cpu = teacher_output.logits[0, :-1].detach().cpu()
            del teacher_output, teacher_input
            gc.collect()
            torch.cuda.empty_cache()
            student_input = torch.tensor([row["student_prompt_ids"] + row["completion_ids"]],
                                         dtype=torch.long, device="cuda")
            model.train()
            student_output = model(input_ids=student_input, use_cache=False, logits_to_keep=n+1)
            student_logits = student_output.logits[0, :-1]
            if teacher_cpu.shape != student_logits.shape or student_logits.shape[0] != n:
                raise AssertionError("Teacher/student completion-token alignment failed")
            kl = ChunkedForwardKL.apply(student_logits, teacher_cpu, fixed["kl_chunk_tokens"])
            if not torch.isfinite(kl):
                raise AssertionError(f"Nonfinite KL on {row['id']}")
            quarters = kl_quartiles(student_logits, teacher_cpu, fixed["kl_chunk_tokens"])
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
                         peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,
                         peak_reserved_gib=torch.cuda.max_memory_reserved()/2**30,
                         seconds=time.monotonic()-tick)
            max_allocated = max(max_allocated, event["peak_allocated_gib"])
            max_reserved = max(max_reserved, event["peak_reserved_gib"])
            del prior_grads, student_input, student_output, student_logits, teacher_cpu, kl
            gc.collect()
            torch.cuda.empty_cache()
            if (idx + 1) % fixed["grad_accumulation"] == 0 or idx + 1 == len(rows):
                norm = torch.nn.utils.clip_grad_norm_(trainable, fixed["grad_clip"])
                if not torch.isfinite(norm):
                    raise AssertionError("Nonfinite accumulated gradient norm")
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
                receipt["updates"] += 1
                event["optimizer_update"] = receipt["updates"]
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
        if len(reloaded_optimizer["state"]) != len(optimizer.state_dict()["state"]):
            raise AssertionError("Optimizer state reload failed")
        receipt.update(status="complete", changed_lora_tensors=changed,
                       total_lora_tensors=len(before), saved_adapter_tensors_verified=saved_tensors,
                       optimizer_state_entries=len(reloaded_optimizer["state"]),
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
    parser.add_argument("--config")
    parser.add_argument("--batch")
    parser.add_argument("--out")
    options = parser.parse_args()
    if options.cpu_check:
        print(json.dumps(cpu_check()), flush=True)
    elif options.config and options.batch and options.out:
        run(options)
    else:
        parser.error("Use --cpu-check or provide --config, --batch, and --out")
