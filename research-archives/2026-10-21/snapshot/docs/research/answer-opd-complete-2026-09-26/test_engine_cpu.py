"""CPU equivalence, causal alignment, LoRA gradient, and input-boundary checks.

Run with CUDA_VISIBLE_DEVICES= to enforce the CPU-only pre-GPU test phase.
No pretrained weights are loaded; the Qwen/PEFT test uses a tiny random model.
"""

import copy
import argparse
import hashlib
import json
import importlib.util
from importlib import metadata
from pathlib import Path
import tempfile
from types import SimpleNamespace

import torch
import torch.nn.functional as F

from streamed_kl import ActivationOffload, StreamedHiddenKL, completion_hidden


def dense_loss(hidden, teacher, weight):
    logp = F.linear(hidden, weight).float().log_softmax(-1)
    logq = F.linear(teacher, weight).float().log_softmax(-1)
    return (logq.exp() * (logq - logp)).sum() / hidden.shape[0]


def legacy_kl():
    path = Path(__file__).resolve().parents[1] / "answer-opd-pilot-2026-09-26/train_worker.py"
    spec = importlib.util.spec_from_file_location("frozen_opd_worker", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ChunkedForwardKL


def compare_projection(dtype, chunk, n=17):
    torch.manual_seed(2026092601)
    weight = (torch.randn(31, 11) / 4).to(dtype)
    teacher = torch.randn(n, 11).to(dtype)
    first = torch.randn(n, 11).to(dtype).requires_grad_()
    dense = dense_loss(first, teacher, weight) / 4
    expected, = torch.autograd.grad(dense, first)
    second = first.detach().clone().requires_grad_()
    streamed, quarters = StreamedHiddenKL.apply(second, teacher, weight, chunk)
    actual, = torch.autograd.grad(streamed / 4, second)
    # BF16 quantization can differ by one ULP for a softmax-backward versus the
    # closed-form p-q gradient. FP32 is checked much more strictly.
    atol, rtol = (2e-6, 3e-5) if dtype == torch.float32 else (5e-4, 1e-2)
    torch.testing.assert_close(streamed / 4, dense, atol=2e-6, rtol=2e-6)
    torch.testing.assert_close(actual, expected, atol=atol, rtol=rtol)
    count = [n*(q+1)//4 - n*q//4 for q in range(4)]
    assert abs(sum(float(quarters[q])*count[q] for q in range(4) if count[q]) / n - float(streamed.detach())) < 2e-6
    assert teacher.grad is None and weight.grad is None
    return dict(dtype=str(dtype), chunk=chunk, n=n, loss=float(streamed.detach()),
                max_hidden_grad_abs_diff=float((actual.float()-expected.float()).abs().max()),
                hidden_grad_relative_l2=float((actual.float()-expected.float()).norm()/expected.float().norm()))


def low_rank_check():
    torch.manual_seed(16)
    x, frozen, a, b = torch.randn(19, 7), torch.randn(11, 7)/4, torch.randn(3, 7)/5, torch.randn(11, 3)/5
    teacher, head = torch.randn(19, 11), torch.randn(37, 11)/4
    results = []
    for mode in ("dense", "legacy", "streamed"):
        aa, bb = a.clone().requires_grad_(), b.clone().requires_grad_()
        hidden = F.linear(x, frozen) + 2 * F.linear(F.linear(x, aa), bb)
        if mode == "streamed":
            loss = StreamedHiddenKL.apply(hidden, teacher, head, 4)[0]
        elif mode == "legacy":
            loss = legacy_kl().apply(F.linear(hidden, head), F.linear(teacher, head), 4)
        else:
            loss = dense_loss(hidden, teacher, head)
        grads = torch.autograd.grad(loss, (aa, bb))
        results.append((loss.detach(), grads))
    diffs = []
    for loss, grads in results[1:]:
        torch.testing.assert_close(results[0][0], loss, atol=2e-6, rtol=2e-6)
        for expected, actual in zip(results[0][1], grads):
            torch.testing.assert_close(expected, actual, atol=2e-6, rtol=3e-5)
            assert actual.norm() > 0
            diffs.append(float((expected-actual).abs().max()))
    return dict(max_lora_grad_abs_diff=max(diffs), compared=["dense", "legacy_full_logits", "streamed_hidden"])


def optimizer_resume_check():
    from train_worker import verify_optimizer_state, optimizer_step_values
    torch.manual_seed(24)
    initial = [torch.randn(3,7)/5, torch.randn(11,3)/5]
    frozen, head = torch.randn(11,7)/4, torch.randn(37,11)/4
    cases = [(torch.randn(n,7), torch.randn(n,11)) for n in (3,5,7,11)]
    def advance(params, optimizer, streamed):
        optimizer.zero_grad(set_to_none=True)
        for x, teacher in cases:
            h = F.linear(x, frozen) + 2*F.linear(F.linear(x, params[0]), params[1])
            loss = StreamedHiddenKL.apply(h, teacher, head, 4)[0] if streamed else dense_loss(h, teacher, head)
            (loss/4).backward()
        torch.nn.utils.clip_grad_norm_(params, 1)
        optimizer.step()
    pairs = []
    for streamed in (False, True):
        params = [torch.nn.Parameter(p.clone()) for p in initial]
        optimizer = torch.optim.AdamW(params, lr=5e-6, weight_decay=0)
        advance(params, optimizer, streamed)
        pairs.append((params, optimizer))
    for expected, actual in zip(pairs[0][0], pairs[1][0]):
        torch.testing.assert_close(actual, expected, atol=1e-7, rtol=1e-6)
    params, optimizer = pairs[1]
    assert optimizer_step_values(optimizer) == [1]
    with tempfile.TemporaryDirectory(prefix=".cpu-optimizer-", dir=Path(__file__).parent) as temp:
        path = Path(temp)/"optimizer.pt"
        torch.save(optimizer.state_dict(), path)
        restored_state = torch.load(path, map_location="cpu", weights_only=True)
        verify_optimizer_state(optimizer.state_dict(), restored_state)
        resumed = [torch.nn.Parameter(p.detach().clone()) for p in params]
        resumed_optimizer = torch.optim.AdamW(resumed, lr=5e-6, weight_decay=0)
        resumed_optimizer.load_state_dict(restored_state)
        advance(params, optimizer, True)
        advance(resumed, resumed_optimizer, True)
        assert all(torch.equal(one, two) for one, two in zip(params, resumed))
        verify_optimizer_state(optimizer.state_dict(), resumed_optimizer.state_dict())
        assert optimizer_step_values(resumed_optimizer) == [2]
        corrupted = copy.deepcopy(restored_state)
        next(iter(corrupted["state"].values()))["exp_avg"].add_(1)
        try:
            verify_optimizer_state(restored_state, corrupted)
        except AssertionError:
            pass
        else:
            raise AssertionError("Optimizer corruption was not detected")
    return dict(grad_accumulation=4, before_steps=[1], after_steps=[2],
                dense_vs_streamed_update_equal_within_tolerance=True,
                resumed_vs_uninterrupted_parameters_and_state_bit_equal=True,
                saved_state_corruption_detected=True)


def boundary_checks():
    from train_worker import parameters, prepare_batch, compatible_prior_parameters, parameter_changes
    spec = dict(seed=1, max_completion_tokens=32768, max_sequence_tokens=40960,
                learning_rate=5e-6, grad_accumulation=4, grad_clip=1, kl_chunk_tokens=64,
                lora_rank=8, lora_alpha=16, lora_modules=["q_proj"])
    fixed = parameters(spec)
    raw = dict(id="one", reference="3/2", student_prompt_ids=[1], teacher_prompt_ids=[1,2],
               completion_ids=[3,4], finish_reason="stop", student_thinking=False, teacher_thinking=False)
    batch = dict(round=1, policy_adapter_sha256=None, examples=[raw])
    assert prepare_batch(batch, fixed, 10, None)[0]["completion_ids"] == [3,4]
    failures = []
    for change in [dict(finish_reason="length"), dict(completion_ids=[]),
                   dict(completion_ids=[3]*32769), dict(student_prompt_ids=[1,2]), dict(target_proof="forbidden")]:
        bad = copy.deepcopy(batch); bad["examples"][0].update(change)
        try:
            prepare_batch(bad, fixed, 10, None)
        except ValueError:
            failures.append(next(iter(change)))
        else:
            raise AssertionError(f"Invalid batch was accepted: {change.keys()}")
    older = {k:v for k,v in fixed.items() if k not in ("engine", "activation_offload")}
    older["max_completion_tokens"], older["max_sequence_tokens"] = 4096, 8192
    assert not compatible_prior_parameters(older, fixed, spec)
    changed = parameter_changes(older, fixed)
    revised = dict(spec, prior_parameter_revision=dict(
        prior_parameters_sha256=hashlib.sha256(json.dumps(older, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        allowed_changes=list(changed), reason="explicit capacity/engine revision"))
    assert compatible_prior_parameters(older, fixed, revised)
    forbidden = dict(fixed, learning_rate=1e-4)
    assert not compatible_prior_parameters(older, forbidden, revised)
    long_spec = dict(spec, max_completion_tokens=81920, max_sequence_tokens=98304)
    assert parameters(long_spec)["max_completion_tokens"] == 81920
    try:
        parameters(dict(spec, max_completion_tokens=81921))
    except ValueError:
        pass
    else:
        raise AssertionError("Completion cap bound not enforced")
    return dict(rejected_boundaries=failures, authorized_capacity_revision_only=True)


def tail_and_storage_check():
    torch.manual_seed(4)
    weight = torch.randn(37, 11)/4
    teacher = torch.randn(513, 11)
    student = teacher.clone()
    student[-1] += 1
    student.requires_grad_()
    shapes = []
    def pack(t):
        shapes.append(tuple(t.shape)); return t
    with torch.autograd.graph.saved_tensors_hooks(pack, lambda t:t):
        loss, _ = StreamedHiddenKL.apply(student, teacher, weight, 7)
    loss.backward()
    assert shapes == [(513,11), (513,11), (37,11)]
    assert float(student.grad[:-1].abs().max()) < 1e-8
    assert student.grad[-1].norm() > 0
    same = teacher.clone().requires_grad_()
    zero, _ = StreamedHiddenKL.apply(same, teacher, weight, 9)
    zero.backward()
    assert abs(float(zero.detach())) < 1e-7 and float(same.grad.abs().max()) < 1e-8
    # CPU hook paths do not allocate or probe a CUDA device.
    offload = ActivationOffload([weight], True)
    x = torch.randn(4, 11, requires_grad=True)
    with offload.context():
        y = F.linear(x, weight).square().sum()
    y.backward()
    assert offload.stats()["offloaded_tensors"] == 0
    budget = ActivationOffload([], True, max_cpu_bytes=1024, reserve_host_bytes=1024)
    budget.check_budget(512, available=2048)
    for nbytes, available in [(2048, 4096), (512, 1024)]:
        try:
            budget.check_budget(nbytes, available=available)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Host offload budget guard failed")
    return dict(saved_shapes=shapes, final_token_gradient_norm=float(student.grad[-1].norm()),
                identical_distribution_kl=float(zero.detach()), offload_budget_guard=True)


def tiny_qwen_check(dtype):
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import Qwen3_5ForCausalLM, Qwen3_5TextConfig
    torch.manual_seed(32)
    config = Qwen3_5TextConfig(vocab_size=41, hidden_size=32, intermediate_size=64,
        num_hidden_layers=2, layer_types=["linear_attention", "full_attention"],
        num_attention_heads=2, num_key_value_heads=1, head_dim=16,
        linear_num_key_heads=1, linear_num_value_heads=2,
        linear_key_head_dim=8, linear_value_head_dim=8,
        rope_parameters={"rope_type":"default", "rope_theta":10000.0,
                         "partial_rotary_factor":0.5, "mrope_section":[1,1,2], "mrope_interleaved":True},
        attention_dropout=0.0, use_cache=False, tie_word_embeddings=False)
    config._attn_implementation = "eager"
    model = get_peft_model(Qwen3_5ForCausalLM(config).to(dtype), LoraConfig(r=2, lora_alpha=4,
        lora_dropout=0, target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "in_proj_qkv",
                                      "in_proj_z", "out_proj", "gate_proj", "up_proj", "down_proj"],
        bias="none", task_type=TaskType.CAUSAL_LM))
    # Exercise both A and B gradients, not just B at the zero-init point.
    with torch.no_grad():
        for name, p in model.named_parameters():
            if "lora_B" in name:
                p.normal_(std=0.01)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant":False})
    model.enable_input_require_grads()
    base = model.get_base_model()
    assert not base.lm_head.weight.requires_grad
    completion = [8,9,10,11,12,13,14]
    si, ti = torch.tensor([[1,2,3]+completion]), torch.tensor([[1,2,3,4,5]+completion])
    model.eval()
    with torch.no_grad(), model.disable_adapter():
        th = completion_hidden(base.model(input_ids=ti, use_cache=False), len(completion)).detach()
        tl = model(input_ids=ti, use_cache=False, logits_to_keep=len(completion)+1).logits[0,:-1]
        torch.testing.assert_close(F.linear(th, base.lm_head.weight), tl, atol=1e-7, rtol=1e-6)
    results = []
    for mode in ("dense", "legacy", "streamed"):
        model.zero_grad(set_to_none=True); model.train()
        offload = ActivationOffload(model.parameters(), mode == "streamed")
        with offload.context():
            h = completion_hidden(base.model(input_ids=si, use_cache=False), len(completion))
            h.retain_grad()
        if mode == "streamed":
            loss = StreamedHiddenKL.apply(h, th, base.lm_head.weight, 3)[0]
        elif mode == "legacy":
            loss = legacy_kl().apply(F.linear(h, base.lm_head.weight), tl, 3)
        else:
            loss = dense_loss(h, th, base.lm_head.weight)
        (loss/4).backward()
        results.append((loss.detach().clone(), h.grad.clone(),
                        {name:p.grad.clone() for name,p in model.named_parameters() if p.requires_grad}))
    diffs = []
    hidden_diffs = []
    atol, rtol = (1e-7, 2e-4) if dtype == torch.float32 else (2e-6, 2e-2)
    for loss, hidden_grad, grads in results[1:]:
        torch.testing.assert_close(results[0][0], loss, atol=1e-7, rtol=1e-5)
        torch.testing.assert_close(results[0][1], hidden_grad, atol=atol, rtol=rtol)
        hidden_diffs.append(float((results[0][1].float()-hidden_grad.float()).abs().max()))
        assert results[0][2].keys() == grads.keys()
        for name, expected in results[0][2].items():
            actual = grads[name]
            torch.testing.assert_close(actual, expected, atol=atol, rtol=rtol)
            diffs.append(float((actual.float()-expected.float()).abs().max()))
        assert max(float(g.norm()) for g in grads.values()) > 0
    assert all(p.grad is None for p in model.parameters() if not p.requires_grad)
    return dict(model="tiny random Qwen3_5ForCausalLM + PEFT", dtype=str(dtype),
                layer_types=config.layer_types, lora_tensors=len(results[0][2]),
                dense_kl=float(results[0][0]), legacy_kl=float(results[1][0]), streamed_kl=float(results[2][0]),
                max_hidden_grad_abs_diff=max(hidden_diffs),
                max_lora_grad_abs_diff=max(diffs), cpu_only=True)


def run_checks(include_qwen=True):
    old_threads = torch.get_num_threads()
    torch.set_num_threads(2)
    try:
        projection = [compare_projection(dtype, chunk, n)
                      for dtype in (torch.float32, torch.bfloat16)
                      for n in (1,17) for chunk in (1,3,64)]
        result = dict(status="pass", projection=projection, lora=low_rank_check(), optimizer=optimizer_resume_check(),
                      boundaries=boundary_checks(), storage_and_tail=tail_and_storage_check(),
                      cuda_executed=False)
        if include_qwen:
            result["qwen_peft"] = [tiny_qwen_check(dtype) for dtype in (torch.float32, torch.bfloat16)]
        assert not torch.cuda.is_initialized()
        files = [Path(__file__), Path(__file__).with_name("streamed_kl.py"),
                 Path(__file__).with_name("train_worker.py"),
                 Path(__file__).resolve().parents[1]/"answer-opd-pilot-2026-09-26/train_worker.py"]
        result["source_sha256"] = {str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        result["versions"] = {name:metadata.version(name) for name in ("torch", "transformers", "peft")}
        return result
    finally:
        torch.set_num_threads(old_threads)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", action="store_true", help="Run core checks without the tiny Qwen model")
    args = parser.parse_args()
    print(json.dumps(run_checks(include_qwen=not args.core), indent=2))
