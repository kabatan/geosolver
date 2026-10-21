"""Full-vocabulary forward KL without sequence-by-vocabulary stored tensors.

The LM head must be frozen. Both projection and its backward are streamed over
completion positions, preserving the complete causal backbone graph. There is
no vocabulary sampling, top-k approximation, context windowing, or detached KV.
"""

import contextlib
from pathlib import Path

import torch
import torch.nn.functional as F


class StreamedHiddenKL(torch.autograd.Function):
    @staticmethod
    def forward(ctx, student_hidden, teacher_hidden_cpu, head_weight, chunk_tokens):
        if (student_hidden.ndim != 2 or student_hidden.shape[0] == 0 or
                teacher_hidden_cpu.shape != student_hidden.shape or
                teacher_hidden_cpu.device.type != "cpu" or
                teacher_hidden_cpu.requires_grad or head_weight.requires_grad or
                head_weight.ndim != 2 or head_weight.shape[1] != student_hidden.shape[1] or
                head_weight.device != student_hidden.device or
                head_weight.dtype != student_hidden.dtype or
                teacher_hidden_cpu.dtype != student_hidden.dtype or
                type(chunk_tokens) is not int or chunk_tokens < 1):
            raise ValueError("Invalid hidden/head shape, dtype, device, or frozen-teacher/head contract")
        ctx.save_for_backward(student_hidden, teacher_hidden_cpu, head_weight)
        ctx.chunk_tokens = chunk_tokens
        ctx.set_materialize_grads(False)
        n = student_hidden.shape[0]
        total = torch.zeros((), device=student_hidden.device, dtype=torch.float32)
        segments = torch.zeros(4, device=student_hidden.device, dtype=torch.float32)
        counts = [n * (q + 1) // 4 - n * q // 4 for q in range(4)]
        for start in range(0, n, chunk_tokens):
            end = min(start + chunk_tokens, n)
            logp = F.linear(student_hidden[start:end], head_weight).float().log_softmax(-1)
            teacher_chunk = teacher_hidden_cpu[start:end].to(student_hidden.device)
            logq = F.linear(teacher_chunk, head_weight).float().log_softmax(-1)
            per_token = (logq.exp() * (logq - logp)).sum(-1)
            total.add_(per_token.sum())
            for q in range(4):
                left, right = max(start, n * q // 4), min(end, n * (q + 1) // 4)
                if left < right:
                    segments[q].add_(per_token[left-start:right-start].sum())
            del logp, logq, teacher_chunk, per_token
        means = torch.stack([segments[q] / counts[q] if counts[q] else
                             segments.new_tensor(float("nan")) for q in range(4)])
        ctx.mark_non_differentiable(means)
        return total / n, means

    @staticmethod
    def backward(ctx, grad_loss, grad_segments):
        if grad_loss is None:
            return None, None, None, None
        student_hidden, teacher_hidden_cpu, head_weight = ctx.saved_tensors
        n = student_hidden.shape[0]
        # O(n*hidden_size), not O(n*vocab_size).
        hidden_grad = torch.empty_like(student_hidden)
        for start in range(0, n, ctx.chunk_tokens):
            end = min(start + ctx.chunk_tokens, n)
            p = F.linear(student_hidden[start:end], head_weight).float().softmax(-1)
            teacher_chunk = teacher_hidden_cpu[start:end].to(student_hidden.device)
            q = F.linear(teacher_chunk, head_weight).float().softmax(-1)
            # Cast before the linear backward, matching autograd through BF16
            # LM-head output -> FP32 normalization -> BF16 projection backward.
            logits_grad = ((p - q) * grad_loss / n).to(student_hidden.dtype)
            hidden_grad[start:end] = logits_grad @ head_weight
            del p, q, teacher_chunk, logits_grad
        return hidden_grad, None, None, None


def completion_hidden(backbone_output, completion_tokens):
    """Same positions as logits_to_keep=n+1 followed by logits[0, :-1]."""
    hidden = backbone_output.last_hidden_state
    if (hidden.ndim != 3 or hidden.shape[0] != 1 or completion_tokens < 1 or
            hidden.shape[1] <= completion_tokens):
        raise ValueError("One nonempty prompt and completion are required")
    return hidden[0, -completion_tokens-1:-1]


class _OffloadedTensor:
    def __init__(self, device, value, tracker):
        self.device, self.value, self.tracker = device, value, tracker
        self.nbytes = value.numel() * value.element_size()
        tracker.live_bytes += self.nbytes
        tracker.total_bytes += self.nbytes
        tracker.tensor_count += 1
        tracker.peak_live_bytes = max(tracker.peak_live_bytes, tracker.live_bytes)

    def __del__(self):
        self.tracker.live_bytes -= self.nbytes


class ActivationOffload:
    """Offload saved activations/checkpoint inputs, retaining model weights.

    Parameter storage IDs cover views such as transposed Linear weights. Hooks
    run only during the student backbone forward. The KL's head weight and
    hidden are saved outside this context. CPU copies are blocking/unpinned;
    this avoids requiring pinned host RAM proportional to the whole sequence.
    Nested PyTorch checkpoint hooks may own recomputation intermediates.
    """
    def __init__(self, parameters, enabled, max_cpu_bytes=12*2**30, reserve_host_bytes=4*2**30):
        self.enabled = enabled
        self.max_cpu_bytes, self.reserve_host_bytes = max_cpu_bytes, reserve_host_bytes
        self.parameter_storages = {(p.device, p.untyped_storage().data_ptr()) for p in parameters}
        self.live_bytes = self.total_bytes = self.peak_live_bytes = self.tensor_count = 0

    @staticmethod
    def available_host_bytes():
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1])*1024
        raise RuntimeError("MemAvailable is required for bounded host activation offload")

    def check_budget(self, nbytes, available=None):
        if self.live_bytes + nbytes > self.max_cpu_bytes:
            raise RuntimeError("CPU activation offload exceeds its explicit retained-byte limit")
        available = self.available_host_bytes() if available is None else available
        if available - nbytes < self.reserve_host_bytes:
            raise RuntimeError("Insufficient MemAvailable for activation offload plus host reserve")

    def pack(self, tensor):
        if (tensor.device.type != "cuda" or tensor.numel() == 0 or
                (tensor.device, tensor.untyped_storage().data_ptr()) in self.parameter_storages):
            return tensor.detach()
        self.check_budget(tensor.numel()*tensor.element_size())
        return _OffloadedTensor(tensor.device, tensor.detach().cpu(), self)

    @staticmethod
    def unpack(packed):
        return packed.value.to(packed.device) if isinstance(packed, _OffloadedTensor) else packed

    def context(self):
        return (torch.autograd.graph.saved_tensors_hooks(self.pack, self.unpack)
                if self.enabled else contextlib.nullcontext())

    def stats(self):
        return dict(offloaded_tensors=self.tensor_count, cumulative_offloaded_bytes=self.total_bytes,
                    peak_live_offloaded_bytes=self.peak_live_bytes,
                    remaining_offloaded_bytes=self.live_bytes, max_cpu_bytes=self.max_cpu_bytes,
                    reserve_host_bytes=self.reserve_host_bytes)
