"""Single-device token-normalized clipped policy objective, with no hidden scaling.

The denominator is shared by *all* microbatches in one optimizer update,
after truncation masking. Backward sums these losses; never divide by the
number of microbatches. This is the DAPO token objective, not full DAPO.
"""

from __future__ import annotations

import math

import torch


def token_policy_loss(
    logps, old_logps, advantages, mask, denominator, epsilon=0.2, importance_weights=None
):
    ratio = (logps - old_logps).exp()
    adv = advantages.reshape(-1, 1)
    objective = torch.minimum(ratio * adv, ratio.clamp(1 - epsilon, 1 + epsilon) * adv)
    if importance_weights is not None:
        objective = objective * importance_weights.detach()
    return -(objective * mask).sum() / torch.as_tensor(denominator, device=logps.device).clamp_min(
        1
    )


def sampling_correction(learner_logps, sampling_logps, cap=2.0):
    """Token-level truncated IS, using processed (temperature/top-k/p) actor logps.

    This is a bounded token surrogate, not exact trajectory-level off-policy RL.
    """
    difference = learner_logps.detach() - sampling_logps
    if not torch.isfinite(difference).all():
        raise ValueError("Nonfinite sampling/learner logprobs")
    weights = difference.clamp(max=math.log(cap)).exp()
    raw_clipped = (difference > math.log(cap)).float().mean().item()
    ess = (weights.sum().square() / (weights.square().sum() * weights.numel())).item()
    metrics = {
        "mean_weight": weights.mean().item(),
        "min_weight": weights.min().item(),
        "max_weight": weights.max().item(),
        "clipped_fraction": raw_clipped,
        "relative_ess": ess,
        "mean_logprob_difference": difference.mean().item(),
    }
    return weights, metrics


def liger_policy_loss(
    hidden,
    weight,
    targets,
    old_logps,
    advantages,
    mask,
    denominator,
    temperature=0.6,
    chunk_size=128,
):
    """Flatten token positions into Liger's chunked batch axis to bound logits RAM."""
    from liger_kernel.chunked_loss.grpo_loss import LigerFusedLinearGRPOLoss

    batch, length, width = hidden.shape
    fn = LigerFusedLinearGRPOLoss(
        beta=0,
        compiled=False,
        use_ref_model=False,
        chunk_size=chunk_size,
        temperature=temperature,
        loss_type="dapo",
    )
    return fn(
        hidden.reshape(batch * length, 1, width),
        weight,
        targets.reshape(-1, 1),
        mask.reshape(-1, 1),
        advantages.repeat_interleave(length),
        old_per_token_logps=old_logps.reshape(-1, 1),
        num_items_in_batch=denominator,
    )[0]


class _FrozenHeadLogps(torch.autograd.Function):
    """Exact chunked vocabulary softmax with a frozen LM head.

    Saves hidden states instead of N×vocabulary logits. Recomputes one token
    chunk during backward; does not allocate a useless frozen-head gradient.
    """

    @staticmethod
    def forward(ctx, hidden, weight, targets, temperature, chunk_size):
        if weight.requires_grad:
            raise ValueError("The memory-bounded path requires a frozen LM head")
        ctx.save_for_backward(hidden, weight, targets)
        ctx.temperature = temperature
        ctx.chunk_size = chunk_size
        flat = hidden.reshape(-1, hidden.shape[-1])
        target = targets.reshape(-1)
        output = torch.empty(target.shape, dtype=torch.float32, device=hidden.device)
        for start in range(0, len(target), chunk_size):
            end = start + chunk_size
            logits = torch.nn.functional.linear(flat[start:end], weight).float() / temperature
            output[start:end] = logits.gather(1, target[start:end, None]).squeeze(
                1
            ) - logits.logsumexp(1)
        return output.reshape(targets.shape)

    @staticmethod
    def backward(ctx, grad_output):
        hidden, weight, targets = ctx.saved_tensors
        flat = hidden.reshape(-1, hidden.shape[-1])
        target = targets.reshape(-1)
        grad_output = grad_output.reshape(-1)
        result = torch.empty_like(flat)
        for start in range(0, len(target), ctx.chunk_size):
            end = min(start + ctx.chunk_size, len(target))
            logits = torch.nn.functional.linear(flat[start:end], weight).float() / ctx.temperature
            grad_logits = -logits.softmax(-1)
            grad_logits[torch.arange(end - start, device=hidden.device), target[start:end]] += 1
            grad_logits *= grad_output[start:end, None] / ctx.temperature
            result[start:end] = grad_logits.to(weight.dtype) @ weight
        return result.reshape(hidden.shape), None, None, None, None


def frozen_head_logps(hidden, weight, targets, temperature=0.6, chunk_size=128):
    return _FrozenHeadLogps.apply(hidden, weight, targets, temperature, chunk_size)
