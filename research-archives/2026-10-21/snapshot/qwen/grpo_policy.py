"""Explicit FP32 LoRA learner shared by calibration and staged GRPO runs."""

from __future__ import annotations

from contextlib import contextmanager

import torch

from .grpo_loss import frozen_head_logps
from .models import locked_models

TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def fp32_attention(module, query, key, value, attention_mask, dropout=0.0, scaling=None, **kwargs):
    """Explicit KV expansion avoids SDPA GQA's quadratic FP32 math fallback."""
    from torch.nn.attention import SDPBackend, sdpa_kernel

    if kwargs.get("sliding_window") is not None:
        raise ValueError("This learner only supports full causal Qwen3 attention")
    groups = query.shape[1] // key.shape[1]
    key = key.repeat_interleave(groups, dim=1)
    value = value.repeat_interleave(groups, dim=1)
    causal = query.shape[2] > 1 and attention_mask is None and kwargs.get("is_causal", True)
    with sdpa_kernel(SDPBackend.EFFICIENT_ATTENTION):
        output = torch.nn.functional.scaled_dot_product_attention(
            query,
            key,
            value,
            attn_mask=attention_mask,
            dropout_p=dropout,
            is_causal=causal,
            scale=scaling,
        )
    return output.transpose(1, 2).contiguous(), None


def load_policy(adapter=None, seed=20260922, train=True, precision="float32"):
    from peft import LoraConfig, PeftModel, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed

    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    set_seed(seed)
    snapshot = locked_models()["qwen3_4b"]["snapshot_path"]
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True)
    if precision not in ("float32", "bfloat16", "float16"):
        raise ValueError("Unsupported learner precision")
    model = AutoModelForCausalLM.from_pretrained(
        snapshot,
        dtype=getattr(torch, precision),
        attn_implementation="sdpa",
        local_files_only=True,
    )
    from transformers.masking_utils import ALL_MASK_ATTENTION_FUNCTIONS
    from transformers.modeling_utils import ALL_ATTENTION_FUNCTIONS

    ALL_ATTENTION_FUNCTIONS.register("solver_fp32", fp32_attention)
    ALL_MASK_ATTENTION_FUNCTIONS.register("solver_fp32", ALL_MASK_ATTENTION_FUNCTIONS["sdpa"])
    if precision == "float32":
        model.config._attn_implementation = "solver_fp32"
    if adapter:
        model = PeftModel.from_pretrained(model, adapter, is_trainable=train)
    else:
        model = get_peft_model(
            model,
            LoraConfig(
                r=32,
                lora_alpha=64,
                lora_dropout=0,
                target_modules=TARGET_MODULES,
                task_type="CAUSAL_LM",
            ),
        )
    model.to("cuda")
    model.config.use_cache = False
    if train:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
        model.train()
    else:
        model.eval()
    return model, tokenizer


@contextmanager
def activation_offload(enabled):
    # Keep leaf parameters on GPU. Only saved intermediate activations travel
    # to CPU; unlike save_on_cpu this does not duplicate every frozen weight.
    def pack(t):
        if t.device.type == "cuda" and not t.is_leaf and t.numel() > 4096:
            return (t.device, t.detach().to("cpu"))
        return t

    def unpack(value):
        return value[1].to(value[0]) if isinstance(value, tuple) else value

    with torch.autograd.graph.saved_tensors_hooks(pack if enabled else lambda x: x, unpack):
        yield


def completion_hidden(model, row, offload=False):
    p, c = row["prompt_ids"], row["completion_ids"]
    if not p or not c or len(p) + len(c) > 32768:
        raise ValueError("Empty input or context limit exceeded")
    ids = torch.tensor([p + c], device="cuda")
    with activation_offload(offload):
        hidden = model.get_base_model().model(input_ids=ids, use_cache=False).last_hidden_state
    return hidden[:, len(p) - 1 : len(p) + len(c) - 1], torch.tensor([c], device="cuda")


def completion_logps(model, row, offload=False):
    hidden, targets = completion_hidden(model, row, offload)
    return frozen_head_logps(hidden, model.get_base_model().lm_head.weight, targets)


def trainable(model):
    return [p for p in model.parameters() if p.requires_grad]


def flat_gradient(model):
    return torch.cat(
        [
            p.grad.detach().float().cpu().flatten()
            if p.grad is not None
            else torch.zeros(p.numel())
            for p in trainable(model)
        ]
    )
