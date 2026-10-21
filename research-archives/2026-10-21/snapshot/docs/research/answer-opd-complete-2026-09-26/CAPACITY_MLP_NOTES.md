# Inactive MLP workspace fallback

This prototype is **not imported or installed by the running trainer**. The
live `train_worker.py` and `streamed_kl.py` hashes remain respectively
`98394a951cda057a546166f2cbfeda153e817fec1f26be639adb821cf583d801`
and `b23d1aaf62758397aea44cd037ce579ed3e581e01e8e15f9588f464b6e17a554`.
No CUDA experiment was performed for this prototype. Installation is reserved
for a root-authorized capacity amendment after an actual formal-run OOM.

The installed Transformers source defines `Qwen3_5MLP.forward` as
`down_proj(silu(gate_proj(x)) * up_proj(x))`. These operations do not mix token
positions. The actual decoder separately computes its full/linear attention,
adds the residual, applies post-attention RMSNorm, then calls the MLP. Patching
only that MLP therefore preserves the complete attention context and existing
KL objective. `MLPChunkPatch` reversibly patches instances and retains all
module/adapter names, parameter storages, optimizer objects and state-dict keys.
It rejects nonzero MLP/LoRA dropout rather than claiming equivalent RNG behavior.

Each chunk uses `checkpoint(original_forward, chunk, use_reentrant=False)`
during gradient-enabled execution. Its inputs and the concatenated hidden
output remain O(n*hidden); intermediate gate/up/activation/LoRA expansions are
recomputed chunk by chunk in backward. Simple splitting without this inner
checkpoint retains all chunks' intermediates and does not bound the saved
autograd graph. Outer decoder checkpointing remains enabled; nested checkpoint
compatibility is tested against actual Qwen/PEFT modules.

## CPU evidence

`test_capacity_mlp_cpu.py` uses a tiny random actual Qwen3.5 with one linear-
attention and one full-attention layer, all corresponding attention/MLP LoRA
targets, nonzero A/B adapter weights, frozen base/head, and the streamed KL.
It compares patched/unpatched FP32 and BF16 with outer checkpoint both on and
off, including 26 adapter gradients, hidden output/gradient, loss and unchanged
state-dict values/keys. CPU saved-tensor hooks are used; CUDA transfer behavior
and full-size CUDA peaks are not established by this check.

All four combinations pass. Worst FP32 adapter gradient absolute error is
3.64e-11 (relative L2 7.32e-7); BF16 error is 2.73e-12 (relative L2 3.81e-8).
FP32 hidden maximum difference is 2.38e-7; BF16 hidden/loss are identical in
this small test. CUDA GEMM shape changes and accumulation order may produce
different BF16 rounding; mathematical equivalence is not bitwise equivalence.

An isolated 257-token actual Qwen MLP with LoRA retains 433,816 bytes of unique
saved activation storage unchunked, and exactly the same amount with naive
16-token splitting. Inner checkpoint splitting retains 32,896 bytes. This is
saved activation storage, **not** a measured process/GPU peak or a statement
that the full model's memory falls by that factor. Parameters and temporary
workspaces are excluded from the saved-storage count.

Run the inactive CPU check with:

```bash
CUDA_VISIBLE_DEVICES='' qwen/.runtime/vllm-venv/bin/python \
  docs/research/answer-opd-complete-2026-09-26/test_capacity_mlp_cpu.py
```

The detailed results and source hashes are in `capacity-mlp-cpu-check.json`.
No existing engine/test/protocol/config file was changed for this prototype.

## Remaining capacity risks

Actual hidden/intermediate widths are 4096/12288. At 32,768 tokens one dense
BF16 MLP intermediate is 0.75 GiB, and one FP32 LoRA up/gate output is 1.5 GiB;
at 81,920 they are 1.875/3.75 GiB. With 512-token MLP chunks these individual
arrays are 12/24 MiB. Output concatenation and checkpoint inputs still retain
O(n*hidden) storage. LoRA parameter-gradient reductions are chunked, which
changes floating-point accumulation order, not the target derivative.

The installed linear-attention fallback is a separate risk: it converts full
query/key/value streams to FP32, creates pairwise-decay/UT/intra-chunk tensors
for all 64-token attention blocks, solves for new values and keys, then scans
recurrent states without detaching the gradient. A single full FP32 stream
with 32 value heads of width 128 costs 0.5 GiB at 32k or 1.25 GiB at 81k. One
collection of 32x128x128 FP32 states per 64-token block can occupy approximately
1/2.5 GiB at these lengths. Multiple live streams/intermediates may coexist;
these component calculations are not a measured peak. Outer checkpoint's
backward recomputation can still need this full layer workspace on GPU.

Full-attention backend/masks, recurrent-state backward, FP32 attention LoRA
expansions, residual/norm outputs, and available CPU RAM may still dominate.
MLP splitting alone does not guarantee 32k or 81k training. Do not detach
attention states, independently window the context, or omit the tail to make
the method fit while claiming the unchanged full-trajectory objective.

If a formal-run OOM establishes the need, first stop/preserve the failed
receipt and rollout, record an explicit capacity/source amendment, and install
the patch after LoRA setup and decoder checkpoint enabling. A candidate call
is `handle = MLPChunkPatch(model, chunk_tokens=512, inner_checkpoint=True)`;
hold the handle until shutdown. An authorized real-model comparison and
retry must use the same completed trajectory and incoming optimizer, with no
double count of failed zero-update work. The root decides that scheduling;
this note does not launch or authorize a GPU retry.
