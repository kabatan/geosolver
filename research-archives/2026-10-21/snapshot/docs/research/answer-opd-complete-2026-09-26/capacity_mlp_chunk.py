"""Optional Qwen3.5 MLP capacity prototype; not installed by the live trainer.

Qwen3_5MLP is token-independent SwiGLU: down(silu(gate(x))*up(x)). This
prototype chunks only that MLP's sequence axis. Attention and the loss remain
full-context. Inner nonreentrant checkpoints prevent all chunks' intermediate
MLP autograd tensors from accumulating in the backward graph.
"""

import types

import torch
from torch.utils.checkpoint import checkpoint


class MLPChunkPatch:
    """Reversible instance patch, retaining original modules and state-dict keys.

    The root must explicitly authorize installation after an actual OOM. This
    file is not imported by train_worker.py, and creates no CUDA experiments.
    """
    def __init__(self, model, chunk_tokens=512, inner_checkpoint=True):
        from transformers.models.qwen3_5.modeling_qwen3_5 import Qwen3_5MLP
        if type(chunk_tokens) is not int or chunk_tokens < 1:
            raise ValueError("chunk_tokens must be a positive integer")
        base = model.get_base_model() if hasattr(model, "get_base_model") else model
        self.originals = []
        self.chunk_tokens, self.inner_checkpoint = chunk_tokens, inner_checkpoint
        for layer in base.model.layers:
            mlp = layer.mlp
            if not isinstance(mlp, Qwen3_5MLP):
                raise TypeError("Only the source-verified Qwen3_5MLP is supported")
            if any(isinstance(child, torch.nn.Dropout) and child.p != 0 for child in mlp.modules()):
                raise ValueError("Nonzero dropout changes per-chunk RNG semantics")
            if hasattr(mlp, "_capacity_original_forward"):
                raise ValueError("MLP is already patched")
        # Validate every layer before mutating any layer.
        for layer in base.model.layers:
            mlp = layer.mlp
            original = mlp.forward
            self.originals.append((mlp, original))
            mlp._capacity_original_forward = original
            mlp._capacity_chunk_tokens = chunk_tokens
            mlp._capacity_inner_checkpoint = inner_checkpoint
            mlp.forward = types.MethodType(_chunked_forward, mlp)

    def restore(self):
        for module, original in self.originals:
            module.forward = original
            del module._capacity_original_forward
            del module._capacity_chunk_tokens
            del module._capacity_inner_checkpoint
        self.originals.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.restore()


def _chunked_forward(module, x):
    if x.ndim < 2:
        raise ValueError("MLP input requires a token and hidden dimension")
    original = module._capacity_original_forward
    size = module._capacity_chunk_tokens
    if x.shape[-2] <= size:
        return original(x)
    outputs = []
    for start in range(0, x.shape[-2], size):
        one = x[..., start:start+size, :]
        if module._capacity_inner_checkpoint and torch.is_grad_enabled():
            out = checkpoint(original, one, use_reentrant=False, preserve_rng_state=True)
        else:
            out = original(one)
        outputs.append(out)
    return torch.cat(outputs, dim=-2)
