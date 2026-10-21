"""Environment diagnostics: pinned model, CUDA/BF16, KV stress, unrelated smoke."""

from __future__ import annotations

import gc
import time

from .common import digest, now, require
from .inference import generate, load_model, versions
from .models import locked_models

SMOKE = {"system": "You are a helpful assistant.", "prompt": "What is 2 + 3? Answer briefly."}


def run(kv_tokens=32768, smoke_max_new_tokens=512):
    receipts = {}
    models = locked_models(verify_weights=True)
    for key, entry in models.items():
        started = time.monotonic()
        torch, tokenizer, model = load_model(entry)
        token = tokenizer.encode(" hello", add_special_tokens=False)[0]
        torch.cuda.reset_peak_memory_stats()
        cache = None
        # Incrementally fill KV without generating benchmark-related content.
        with torch.inference_mode():
            for _consumed in range(0, kv_tokens, 256):
                ids = torch.full((1, 256), token, dtype=torch.long, device="cuda")
                result = model(
                    input_ids=ids, past_key_values=cache, use_cache=True, logits_to_keep=1
                )
                cache = result.past_key_values
                require(bool(torch.isfinite(result.logits).all()), "Non-finite dummy logits")
            require(cache.get_seq_length() == kv_tokens, "Incomplete KV stress test")
        torch.cuda.synchronize()
        stress = {
            "tokens": kv_tokens,
            "chunk_tokens": 256,
            "finite_logits": True,
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
        }
        del cache, result, ids
        gc.collect()
        torch.cuda.empty_cache()
        smoke = generate(
            torch,
            tokenizer,
            model,
            SMOKE,
            seed=1709,
            max_new_tokens=smoke_max_new_tokens,
            context_limit=kv_tokens,
            deadline=time.monotonic() + 90,
        )
        require(smoke["finish_reason"] == "eos", "Unrelated smoke did not reach EOS")
        receipts[key] = {
            "model_id": entry["model_id"],
            "revision": entry["revision"],
            "chat_template_sha256": digest(tokenizer.chat_template),
            "generation_config": model.generation_config.to_dict(),
            "device": torch.cuda.get_device_name(0),
            "capability": torch.cuda.get_device_capability(0),
            "cuda_runtime": torch.version.cuda,
            "torch_arch_list": torch.cuda.get_arch_list(),
            "total_memory": torch.cuda.get_device_properties(0).total_memory,
            "kv_stress": stress,
            "unrelated_smoke": smoke,
            "gpu_wall_seconds": time.monotonic() - started,
            "passed": True,
        }
        del model, tokenizer
        gc.collect()
        torch.cuda.empty_cache()
        print(f"Doctor PASS: {key}", flush=True)
    return {"utc": now(), "versions": versions(), "models": receipts, "passed": True}
