"""CPU-only actual Qwen/LoRA nested-checkpoint and saved-storage checks."""

import copy
import hashlib
import json
from importlib import metadata
from pathlib import Path

import torch

from capacity_mlp_chunk import MLPChunkPatch
from streamed_kl import ActivationOffload, StreamedHiddenKL, completion_hidden


def make_model(dtype):
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import Qwen3_5ForCausalLM, Qwen3_5TextConfig
    torch.manual_seed(512)
    config = Qwen3_5TextConfig(vocab_size=41, hidden_size=32, intermediate_size=96,
        num_hidden_layers=2, layer_types=["linear_attention", "full_attention"],
        num_attention_heads=2, num_key_value_heads=1, head_dim=16,
        linear_num_key_heads=1, linear_num_value_heads=2,
        linear_key_head_dim=8, linear_value_head_dim=8,
        rope_parameters={"rope_type":"default", "rope_theta":10000.0,
                         "partial_rotary_factor":0.5,"mrope_section":[1,1,2],"mrope_interleaved":True},
        attention_dropout=0, use_cache=False, tie_word_embeddings=False)
    config._attn_implementation = "eager"
    model = get_peft_model(Qwen3_5ForCausalLM(config).to(dtype), LoraConfig(
        r=2, lora_alpha=4, lora_dropout=0, bias="none", task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj","k_proj","v_proj","o_proj","in_proj_qkv","in_proj_z",
                        "out_proj","gate_proj","up_proj","down_proj"]))
    with torch.no_grad():
        for name, p in model.named_parameters():
            if "lora_B" in name:
                p.normal_(std=0.01)
    model.enable_input_require_grads()
    return model


def gradient_case(dtype, outer_checkpoint):
    model = make_model(dtype)
    if outer_checkpoint:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant":False})
    base = model.get_base_model()
    completion = list(range(8,25))
    student = torch.tensor([[1,2,3]+completion])
    teacher = torch.tensor([[1,2,3,4,5]+completion])
    model.eval()
    with torch.no_grad(), model.disable_adapter():
        teacher_hidden = completion_hidden(base.model(input_ids=teacher,use_cache=False),len(completion)).detach()
    state = {k:v.detach().clone() for k,v in model.state_dict().items()}
    results = []
    for patched in (False, True):
        model.zero_grad(set_to_none=True); model.train()
        handle = MLPChunkPatch(model,chunk_tokens=6,inner_checkpoint=True) if patched else None
        try:
            offload = ActivationOffload(model.parameters(), enabled=True)
            with offload.context():
                h = completion_hidden(base.model(input_ids=student,use_cache=False),len(completion))
                h.retain_grad()
            loss, _ = StreamedHiddenKL.apply(h,teacher_hidden,base.lm_head.weight,5)
            (loss/4).backward()
            results.append(dict(loss=loss.detach().clone(),hidden=h.detach().clone(),hidden_grad=h.grad.clone(),
                grads={name:p.grad.clone() for name,p in model.named_parameters() if p.requires_grad}))
        finally:
            if handle:
                handle.restore()
    # Chunked GEMM/parameter-gradient reduction has BF16 rounding differences.
    atol,rtol = (2e-7,3e-4) if dtype==torch.float32 else (4e-6,4e-2)
    torch.testing.assert_close(results[0]["hidden"],results[1]["hidden"],atol=atol,rtol=rtol)
    torch.testing.assert_close(results[0]["loss"],results[1]["loss"],atol=2e-7,rtol=3e-5)
    torch.testing.assert_close(results[0]["hidden_grad"],results[1]["hidden_grad"],atol=atol,rtol=rtol)
    expected,actual = results[0]["grads"],results[1]["grads"]
    assert expected.keys()==actual.keys()
    maximum = 0
    err2 = ref2 = 0
    for name in expected:
        torch.testing.assert_close(expected[name],actual[name],atol=atol,rtol=rtol)
        diff=actual[name].float()-expected[name].float()
        maximum=max(maximum,float(diff.abs().max()))
        err2+=float(diff.square().sum());ref2+=float(expected[name].float().square().sum())
    assert {k:v.dtype for k,v in model.state_dict().items()}=={k:v.dtype for k,v in state.items()}
    assert all(torch.equal(v,model.state_dict()[k]) for k,v in state.items())
    return dict(dtype=str(dtype),outer_checkpoint=outer_checkpoint,inner_checkpoint=True,
        lora_tensors=len(actual),full_context_tokens=student.shape[1],
        unpatched_kl=float(results[0]["loss"]),patched_kl=float(results[1]["loss"]),
        max_hidden_abs_diff=float((results[0]["hidden"].float()-results[1]["hidden"].float()).abs().max()),
        max_lora_gradient_abs_diff=maximum,lora_gradient_relative_l2=(err2/ref2)**0.5,
        state_dict_values_and_keys_unchanged=True)


def saved_storage_case():
    model=make_model(torch.float32);base=model.get_base_model();module=base.model.layers[0].mlp
    x=torch.randn(1,257,32,requires_grad=True)
    parameter_storages={(p.device,p.untyped_storage().data_ptr()) for p in model.parameters()}
    rows=[]
    for mode in ("unchunked","naive_chunk","inner_checkpoint_chunk"):
        model.zero_grad(set_to_none=True);x.grad=None
        handle=MLPChunkPatch(model,16,mode=="inner_checkpoint_chunk") if mode!="unchunked" else None
        logical=[];unique={}
        def pack(t):
            key=(t.device,t.untyped_storage().data_ptr())
            if key not in parameter_storages and t.numel():
                logical.append(t.numel()*t.element_size())
                unique[key]=t.untyped_storage().nbytes()
            return t.detach()
        try:
            with torch.autograd.graph.saved_tensors_hooks(pack,lambda t:t):
                output=module(x)
            row=dict(mode=mode,logical_saved_activation_bytes=sum(logical),
                     unique_saved_activation_storage_bytes=sum(unique.values()),saved_tensors=len(logical))
            output.square().mean().backward()
            assert x.grad.norm()>0
            rows.append(row)
        finally:
            if handle:handle.restore()
    checkpointed=rows[2]["unique_saved_activation_storage_bytes"]
    assert checkpointed<rows[0]["unique_saved_activation_storage_bytes"]
    assert checkpointed<rows[1]["unique_saved_activation_storage_bytes"]
    # Naive chunking retains activations across all chunks, despite reducing
    # individual allocation sizes. It does not make this saved graph O(chunk).
    assert rows[1]["logical_saved_activation_bytes"]>=0.9*rows[0]["logical_saved_activation_bytes"]
    return rows


def run():
    old_threads=torch.get_num_threads();torch.set_num_threads(2)
    try:
        rows=[gradient_case(dtype,outer) for dtype in (torch.float32,torch.bfloat16) for outer in (False,True)]
        memory=saved_storage_case()
        assert not torch.cuda.is_initialized()
        import transformers.models.qwen3_5.modeling_qwen3_5 as source
        paths=[Path(__file__),Path(__file__).with_name("capacity_mlp_chunk.py"),Path(source.__file__)]
        return dict(status="pass",cuda_executed=False,not_installed_in_live_engine=True,
                    gradients=rows,saved_activation_storage=memory,
                    source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                    versions={name:metadata.version(name) for name in ("torch","transformers","peft")})
    finally:
        torch.set_num_threads(old_threads)


if __name__=="__main__":
    print(json.dumps(run(),indent=2))
