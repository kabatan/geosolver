"""One technical distillation update; never an efficacy/transfer experiment.

Run --cpu-check before --run. No new rollouts, no second base model, and no
trained adapter is saved. A prefix of an existing rollout is deliberately used
only to test numerical alignment, memory, and gradient flow.
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
import re
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
RUNTIME = ROOT / "qwen/.runtime/learning_options_20260926"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


class ChunkedForwardKL(torch.autograd.Function):
    """Exact full-vocabulary KL(teacher||student), recomputed in backward.

    Teacher logits reside on CPU. Only a token chunk of probabilities/logits
    is materialized on the student's device. The LM's student logits remain
    attached to its graph, but full-vocabulary softmax graphs are not retained.
    All normalizations use FP32 and temperature 1.
    """

    @staticmethod
    def forward(ctx, student, teacher_cpu, chunk_size):
        assert student.ndim == teacher_cpu.ndim == 2
        assert student.shape == teacher_cpu.shape
        assert teacher_cpu.device.type == "cpu" and not teacher_cpu.requires_grad
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


def cpu_check():
    torch.manual_seed(20260926)
    x = torch.randn(7, 19, dtype=torch.float32, requires_grad=True)
    qlogits = torch.randn(7, 19, dtype=torch.float32)
    logq = qlogits.log_softmax(-1)
    dense = (logq.exp() * (logq - x.log_softmax(-1))).sum() / len(x)
    dense_grad, = torch.autograd.grad(dense, x)
    y = x.detach().clone().requires_grad_(True)
    chunked = ChunkedForwardKL.apply(y, qlogits, 3)
    chunked_grad, = torch.autograd.grad(chunked, y)
    assert torch.allclose(dense, chunked, atol=1e-6, rtol=1e-6)
    assert torch.allclose(dense_grad, chunked_grad, atol=1e-7, rtol=1e-6)
    z = x.detach().clone().requires_grad_(True)
    zero = ChunkedForwardKL.apply(z, z.detach().clone(), 3)
    zero_grad, = torch.autograd.grad(zero, z)
    assert abs(float(zero.detach())) < 1e-6 and float(zero_grad.abs().max()) < 1e-7
    return dict(status="pass", dense_kl=float(dense.detach()), chunked_kl=float(chunked.detach()),
                max_abs_gradient_difference=float((dense_grad-chunked_grad).abs().max()),
                identical_distribution_kl=float(zero.detach()))


def run(args):
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    source = RUNTIME / "hint_probe" / f"{args.source}-no_hint.json"
    jobs_path = HERE / "hint-probe-jobs.json"
    meta_path = ROOT / "docs/research/qwen35-self-materials-2026-09-23/model.json"
    spec_path = ROOT / "docs/research/qwen35-external-teacher-2026-09-24/train-protocol-low-dose.json"
    assert re.fullmatch(r"[a-z][a-z0-9_]*", args.output_name)
    out = RUNTIME / args.output_name
    out.mkdir(parents=True, exist_ok=False)
    receipt = dict(status="running", scope="mechanical single-update feasibility only",
                   efficacy_claim=False, generated_new_tokens=0, saved_adapter=False,
                   target_prefix_tokens=args.tokens, source=str(source), source_sha256=digest(source),
                   driver_sha256=digest(__file__), jobs_sha256=digest(jobs_path),
                   source_training_protocol_sha256=digest(spec_path), cpu_check=cpu_check(),
                   versions={name: importlib.metadata.version(name)
                             for name in ("torch", "transformers", "peft")}, start_unix=time.time())
    write(out / "receipt.json", receipt)
    start = time.monotonic()
    try:
        row = json.loads(source.read_text())
        jobs = {j["id"]: j for j in json.loads(jobs_path.read_text())}
        student_prompt = jobs[f"{args.source}-no_hint"]["prompt"]
        teacher_prompt = jobs[f"{args.source}-numeric_hint"]["prompt"]
        meta = json.loads(meta_path.read_text())
        spec = json.loads(spec_path.read_text())
        assert row["model_revision"] == meta["revision"] == spec["model_revision"]
        tok = AutoTokenizer.from_pretrained(meta["snapshot"], local_files_only=True)

        def prompt_ids(prompt):
            text = tok.apply_chat_template([dict(role="user", content=prompt)], tokenize=False,
                                           add_generation_prompt=True, enable_thinking=False)
            return tok.encode(text, add_special_tokens=False)

        student_ids, teacher_ids = prompt_ids(student_prompt), prompt_ids(teacher_prompt)
        assert student_ids == row["prompt_ids"]
        completion = row["completion_ids"][:args.tokens]
        assert len(completion) >= 128
        n = len(completion)
        assert max(len(student_ids), len(teacher_ids)) + n <= 8192
        receipt.update(model_revision=meta["revision"], source_configuration=args.source,
                       numerical_answer=jobs[f"{args.source}-numeric_hint"]["reference"],
                       student_prompt_tokens=len(student_ids), teacher_prompt_tokens=len(teacher_ids),
                       completion_tokens=n, source_completion_tokens=len(row["completion_ids"]),
                       source_finish_reason=row["finish_reason"],
                       completion_sha256=hashlib.sha256(json.dumps(completion).encode()).hexdigest(),
                       prefix_is_complete_answer=n == len(row["completion_ids"]),
                       alignment="Both inputs end with identical completion ids; logits_to_keep=n+1, omit last logit.",
                       student_thinking=False, teacher_thinking=False, teacher="frozen base with LoRA disabled",
                       objective="full vocabulary forward KL(teacher||student), float32 normalization, temperature 1",
                       lora_rank=spec["lora_rank"], lora_alpha=spec["lora_alpha"],
                       lora_modules=spec["modules"], learning_rate=spec["lr"])
        torch.manual_seed(20260926)
        torch.cuda.manual_seed_all(20260926)
        torch.cuda.reset_peak_memory_stats()
        model = AutoModelForCausalLM.from_pretrained(
            meta["snapshot"], dtype=torch.bfloat16, device_map="cuda",
            attn_implementation="sdpa", local_files_only=True)
        model = get_peft_model(model, LoraConfig(
            r=spec["lora_rank"], lora_alpha=spec["lora_alpha"], lora_dropout=0.0,
            target_modules=spec["modules"], bias="none", task_type=TaskType.CAUSAL_LM))
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
        trainable = [p for p in model.parameters() if p.requires_grad]
        assert trainable and all("lora_" in name for name, p in model.named_parameters() if p.requires_grad)
        before = {name: p.detach().float().cpu().clone()
                  for name, p in model.named_parameters() if p.requires_grad}
        optimizer = torch.optim.AdamW(trainable, lr=spec["lr"], weight_decay=0)
        teacher_input = torch.tensor([teacher_ids + completion], dtype=torch.long, device="cuda")
        t0 = time.monotonic()
        model.eval()
        with torch.no_grad(), model.disable_adapter():
            teacher_output = model(input_ids=teacher_input, use_cache=False, logits_to_keep=n+1)
            teacher_cpu = teacher_output.logits[0, :-1].detach().cpu()
        assert teacher_cpu.shape[0] == n
        del teacher_output, teacher_input
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        receipt["teacher_forward_seconds"] = time.monotonic()-t0
        receipt["teacher_logits_cpu_gib"] = teacher_cpu.numel()*teacher_cpu.element_size()/2**30
        receipt["teacher_peak_allocated_gib"] = torch.cuda.max_memory_allocated()/2**30
        write(out / "receipt.json", receipt)

        model.train()
        optimizer.zero_grad(set_to_none=True)
        student_input = torch.tensor([student_ids + completion], dtype=torch.long, device="cuda")
        t0 = time.monotonic()
        student_output = model(input_ids=student_input, use_cache=False, logits_to_keep=n+1)
        student_logits = student_output.logits[0, :-1]
        assert student_logits.shape == teacher_cpu.shape
        # Inspect the same target tokens under the two differently conditioned
        # models. This is a numerical difference, not a correctness judgement.
        ratios = []
        with torch.no_grad():
            for begin in range(0, n, 64):
                end = min(begin+64, n)
                targets = torch.tensor(completion[begin:end], device="cuda").unsqueeze(1)
                plog = student_logits[begin:end].float().log_softmax(-1).gather(1, targets).squeeze(1)
                qlog = teacher_cpu[begin:end].to("cuda").float().log_softmax(-1).gather(1, targets).squeeze(1)
                ratios.extend((qlog-plog).cpu().tolist())
        loss = ChunkedForwardKL.apply(student_logits, teacher_cpu, 64)
        assert torch.isfinite(loss)
        loss.backward()
        grad_finite = all(p.grad is None or torch.isfinite(p.grad).all().item() for p in trainable)
        assert grad_finite
        grad_norm = torch.nn.utils.clip_grad_norm_(trainable, spec["grad_clip"])
        assert torch.isfinite(grad_norm)
        optimizer.step()
        torch.cuda.synchronize()
        changed = sum(not torch.equal(before[name], p.detach().float().cpu())
                      for name, p in model.named_parameters() if name in before)
        assert changed > 0
        ratio_tensor = torch.tensor(ratios)
        receipt.update(status="complete", updates=1, loss=float(loss.detach()),
                       finite_gradients=grad_finite, gradient_norm_before_clipping=float(grad_norm),
                       changed_lora_tensors=changed, total_lora_tensors=len(before),
                       student_update_seconds=time.monotonic()-t0,
                       peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,
                       peak_reserved_gib=torch.cuda.max_memory_reserved()/2**30,
                       sampled_token_logratio_mean=float(ratio_tensor.mean()),
                       sampled_token_logratio_abs_mean=float(ratio_tensor.abs().mean()),
                       sampled_token_logratio_max_abs=float(ratio_tensor.abs().max()),
                       token_logratios_sha256=hashlib.sha256(json.dumps(ratios).encode()).hexdigest())
        write(out / "token_logratios.json", dict(description="teacher-minus-student log-probabilities on identical sampled tokens; not correctness labels",
                                                completion_token_ids=completion, logratios=ratios))
    except BaseException as exc:
        receipt.update(status="failed", error=repr(exc))
        raise
    finally:
        receipt.update(end_unix=time.time(), total_seconds=time.monotonic()-start)
        write(out / "receipt.json", receipt)
        print(json.dumps(receipt, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cpu-check", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--source", default="H04", choices=["H04", "H07", "DA05", "H14"])
    parser.add_argument("--tokens", type=int, default=1024)
    parser.add_argument("--output-name", default="distillation_probe")
    args = parser.parse_args()
    if args.cpu_check:
        result = cpu_check()
        write(HERE / "distillation-probe-cpu-check.json", result)
        print(json.dumps(result))
    elif args.run:
        run(args)
    else:
        parser.error("Choose --cpu-check or --run explicitly")
