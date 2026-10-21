"""Half-precision base with native, unmerged LoRA; no base-weight round trips."""

from pathlib import Path

from .models import locked_models


def engine(seed=20260922, max_seqs=4, precision="float16"):
    import os

    os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from vllm import LLM

    return LLM(
        model=locked_models()["qwen3_4b"]["snapshot_path"],
        dtype=precision,
        kv_cache_dtype="auto",
        enable_lora=True,
        max_lora_rank=32,
        lora_dtype=precision,
        max_loras=1,
        max_model_len=32768,
        max_num_seqs=max_seqs,
        max_num_batched_tokens=1024,
        gpu_memory_utilization=0.85,
        enforce_eager=True,
        enable_prefix_caching=False,
        logprobs_mode="processed_logprobs",
        seed=seed,
    )


def request(adapter):
    if not adapter:
        return None
    from vllm.lora.request import LoRARequest

    return LoRARequest("policy", 1, str(Path(adapter).resolve()))
