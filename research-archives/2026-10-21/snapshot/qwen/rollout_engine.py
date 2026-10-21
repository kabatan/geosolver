"""FP32 rollout engine; synchronize from immutable base without BF16 round trips."""

from __future__ import annotations

from functools import partial


def _replace_policy(model, snapshot, adapter):
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM

    torch.set_num_threads(4)
    # This temporary model lives on CPU. Never merge/unmerge the learner or
    # incrementally add deltas to the previous rollout policy.
    source = AutoModelForCausalLM.from_pretrained(
        snapshot, dtype=torch.float32, local_files_only=True
    )
    if adapter:
        source = PeftModel.from_pretrained(source, adapter).merge_and_unload(safe_merge=True)
    assert all(p.dtype == torch.float32 for p in source.parameters())
    model.load_weights(source.named_parameters())
    return {"parameters": sum(p.numel() for p in source.parameters()), "dtype": "float32"}


def set_adapter(llm, adapter):
    from pathlib import Path

    from .models import locked_models

    result = llm.apply_model(
        partial(
            _replace_policy,
            snapshot=locked_models()["qwen3_4b"]["snapshot_path"],
            adapter=str(Path(adapter).resolve()) if adapter else None,
        )
    )
    llm.reset_prefix_cache()
    return result


def engine(kv="auto", seed=20260922, max_seqs=4):
    import os

    # Only our local parent/worker IPC uses this to serialize the repo-owned
    # apply_model callback. No network server or external pickle is accepted.
    os.environ["VLLM_ALLOW_INSECURE_SERIALIZATION"] = "1"
    os.environ["VLLM_FLOAT32_MATMUL_PRECISION"] = "highest"
    os.environ["TRITON_F32_DEFAULT"] = "ieee"
    from vllm import LLM

    from .models import locked_models

    return LLM(
        model=locked_models()["qwen3_4b"]["snapshot_path"],
        dtype="float32",
        kv_cache_dtype=kv,
        attention_backend="TRITON_ATTN",
        enforce_eager=True,
        max_model_len=32768,
        max_num_seqs=max_seqs,
        max_num_batched_tokens=1024,
        gpu_memory_utilization=0.85,
        enable_prefix_caching=False,
        seed=seed,
    )
