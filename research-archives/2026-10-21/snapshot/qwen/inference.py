"""GPU runtime for the pinned Qwen3-4B snapshot."""

from __future__ import annotations

import importlib.metadata
import os
import platform
import sys
import time

from .common import digest, require


def versions():
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in (
                "torch",
                "transformers",
                "huggingface-hub",
                "tokenizers",
                "safetensors",
                "numpy",
            )
        },
    }


def load_model(entry):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.set_num_threads(4)
    require(torch.cuda.is_available(), "CUDA is not available")
    require(torch.cuda.is_bf16_supported(), "BF16 is not supported")
    tokenizer = AutoTokenizer.from_pretrained(
        entry["snapshot_path"], local_files_only=True, trust_remote_code=False
    )
    model = AutoModelForCausalLM.from_pretrained(
        entry["snapshot_path"],
        local_files_only=True,
        trust_remote_code=False,
        use_safetensors=True,
        torch_dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    model.to("cuda").eval()
    require(next(model.parameters()).dtype == torch.bfloat16, "Wrong model dtype")
    return torch, tokenizer, model


def rendered(tokenizer, case):
    return tokenizer.apply_chat_template(
        [
            {"role": "system", "content": case["system"]},
            {"role": "user", "content": case["prompt"]},
        ],
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=True,
    )


def generate(
    torch,
    tokenizer,
    model,
    case,
    seed,
    max_new_tokens,
    context_limit,
    deadline,
    temperature=0.6,
    top_p=0.95,
    top_k=20,
):
    from transformers import StoppingCriteria, StoppingCriteriaList, set_seed

    class Deadline(StoppingCriteria):
        def __call__(self, input_ids, scores, **kwargs):
            return time.monotonic() >= deadline

    prompt = rendered(tokenizer, case)
    inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
    n_input = inputs.input_ids.shape[1]
    require(
        n_input + max_new_tokens <= context_limit, "Output allocation exceeds total context limit"
    )
    set_seed(seed)
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    with torch.inference_mode():
        output = model.generate(
            **inputs,
            do_sample=True,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_new_tokens=max_new_tokens,
            use_cache=True,
            pad_token_id=tokenizer.eos_token_id,
            stopping_criteria=StoppingCriteriaList([Deadline()]),
        )
    torch.cuda.synchronize()
    ids = output[0, n_input:].tolist()
    eos_ids = model.generation_config.eos_token_id
    eos_ids = [eos_ids] if isinstance(eos_ids, int) else eos_ids
    reason = (
        "eos"
        if ids and ids[-1] in eos_ids
        else "max_tokens"
        if len(ids) == max_new_tokens
        else "time_limit"
    )
    visible_ids = ids[:-1] if reason == "eos" else ids
    text = tokenizer.decode(visible_ids, skip_special_tokens=False)
    return {
        "raw_token_ids": ids,
        "raw_text": text,
        "finish_reason": reason,
        "input_tokens": n_input,
        "output_tokens": len(ids),
        "max_new_tokens": max_new_tokens,
        "context_limit": context_limit,
        "prompt_open_thinking": prompt.rstrip().endswith("<think>"),
        "rendered_prompt_sha256": digest(prompt),
        "input_ids_sha256": digest(inputs.input_ids.tolist()),
        "elapsed_seconds": time.monotonic() - started,
        "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
    }


def infer(request):
    """Run one chat inference unrelated to any benchmark case."""
    from .models import locked_models

    entry = locked_models()[request["model_key"]]
    torch, tokenizer, model = load_model(entry)
    deadline = time.monotonic() + request["wall_seconds"]
    case = {"system": request["system"], "prompt": request["prompt"]}
    result = generate(
        torch,
        tokenizer,
        model,
        case,
        seed=request["seed"],
        max_new_tokens=request["max_new_tokens"],
        context_limit=request["context_limit"],
        deadline=deadline,
        temperature=request["temperature"],
        top_p=request["top_p"],
        top_k=request["top_k"],
    )
    return {
        "model_key": request["model_key"],
        "model_id": entry["model_id"],
        "revision": entry["revision"],
        "system": request["system"],
        "prompt": request["prompt"],
        "seed": request["seed"],
        "generation": {
            "temperature": request["temperature"],
            "top_p": request["top_p"],
            "top_k": request["top_k"],
            "max_new_tokens": request["max_new_tokens"],
        },
        **result,
    }
