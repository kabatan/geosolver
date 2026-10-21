# Complete-trajectory KL engine

`train_worker.py` consumes the original batch interface, saves PEFT/vLLM
adapters and AdamW state in a new output directory, and never changes the
frozen prior study. GPU execution belongs to the root operator.

The objective remains full-vocabulary FP32 forward KL(teacher || student),
temperature one, averaged over **every supplied completion position** and
then over each accumulation group. Teacher: same frozen base, numeric-answer
prompt, adapters disabled. Student: current adapter, original prompt, exactly
the same completion IDs. It is teacher-forced distribution distillation,
not a separately generated corrected answer or answer-label CE.

The Qwen backbone returns its final normalized hidden states. The positions
`[0, -n-1:-1]` exactly match the old `logits_to_keep=n+1; logits[0,:-1]`
causal shift. A frozen bias-free LM head is applied in token chunks in both
KL forward and backward. The persistent KL tensors have shapes `(n,H)`,
`(n,H)` on CPU for the teacher, and frozen `(V,H)` head weights already in
the model. There is no persistent `(n,V)` logits/gradient tensor. Backward
returns a full `(n,H)` hidden gradient into the complete backbone graph.
No detached KV cache, independent windows, sampled vocabulary, or tail loss
omission is used. BF16 projection/gradient rounding follows the old engine;
chunked reduction is mathematically equivalent, not promised bit-identical.

## Input and validation

Config retains `model_metadata`, `seed`, `max_completion_tokens`,
`max_sequence_tokens`, `learning_rate=5e-6`, `grad_accumulation=4`,
`grad_clip=1`, `kl_chunk_tokens`, `lora_rank=8`, `lora_alpha=16`,
`lora_modules`, and optional `prior_checkpoint`. New capacity fields:

- `activation_offload`: `none` or `cpu` (default `cpu`). The root should set
  `none` explicitly for the first checkpoint+chunk memory measurement.
- `cpu_offload_max_gib`: retained saved-activation limit, default 12 GiB.
- `cpu_offload_reserve_gib`: required system MemAvailable after a proposed
  CPU copy, default 4 GiB. Neither budget guard guarantees protection against
  concurrent external allocations; failure stops rather than changing loss.

Completion capacity is bounded at 81,920; sequence capacity at 98,304.
The worker refuses an oversized completion instead of slicing it, and rejects
`length` or other non-natural finish reasons. It appends no artificial EOS.
Natural termination is a serialization gate, not proof of mathematical
correctness or coherent completion; the protocol's completion audit remains
the root's responsibility. Mathematical errors alone do not trigger rejection.

Batch JSON: `{round, policy_adapter_sha256, examples}`. Each example requires
`id`, `reference` (numeric scalar/string), `student_prompt_ids`,
`teacher_prompt_ids`, `completion_ids`, `finish_reason`, `student_thinking`,
and `teacher_thinking`. The incoming policy hash must match the prior mapped
adapter (null for fresh base). Proof targets and teacher-generated completion
targets are forbidden. Empty/invalid token lists and identical prompts fail.
The small final accumulation group averages its actual size; a one-example
technical smoke test therefore makes one update and is **not** a formal
four-example update. Main eight-example batches make two updates.

PEFT LoRA keys, vLLM language_model key mapping, and AdamW format remain
compatible with the old worker. Normal resumes require matching training
parameters, revision, hashes, and adjacent round numbers. Loading a legacy
checkpoint across an engine/capacity revision requires an explicit config
`prior_parameter_revision` object with `prior_parameters_sha256` (canonical
sorted compact JSON hash), `reason`, and an exact `allowed_changes` list.
Only capacity/engine/offload keys can be changed this way. Optimizer/model
hyperparameters cannot silently change. The formal new experiment starts
fresh; this compatibility path does not authorize resuming the old arm.

## CPU verification and operator commands

Run from the repository root, using the existing runtime:

```bash
CUDA_VISIBLE_DEVICES='' qwen/.runtime/vllm-venv/bin/python \
  docs/research/answer-opd-complete-2026-09-26/test_engine_cpu.py
```

The test compares dense autograd, the frozen old `ChunkedForwardKL`, and the
new hidden-streamed objective. It checks FP32/BF16 projections, hidden and
low-rank parameter gradients, a tiny random Qwen with both linear/full
attention plus PEFT and nonreentrant checkpointing, causal alignment, frozen
teacher/head gradients, same-point zero KL, final-token supervision, absence
of saved `(n,V)` tensors, and input/offload/resume boundaries. No pretrained
weights or CUDA device are used. `cpu-check.json` records the full result.

Validate the operator-supplied complete batch without CUDA:

```bash
CUDA_VISIBLE_DEVICES='' qwen/.runtime/vllm-venv/bin/python \
  docs/research/answer-opd-complete-2026-09-26/train_worker.py \
  --preflight --config CONFIG.json --batch COMPLETE-BATCH.json
```

Only after the root releases the GPU, a single completed trajectory may be
passed in a fresh round-one batch with null policy hash for a technical
update. Its checkpoint must be kept separate from the fresh formal run:

```bash
LD_LIBRARY_PATH=/home/kabatan/work/solver/qwen/.runtime/answer_opd_pilot_20260926/recovery-nvml59584/extracted/usr/lib/x86_64-linux-gnu \
  qwen/.runtime/vllm-venv/bin/python \
  docs/research/answer-opd-complete-2026-09-26/train_worker.py \
  --config CONFIG.json --batch COMPLETE-BATCH.json --out NEW-TRAIN-DIR
```

These GPU commands require the root's scheduling authorization. Actual runs
are recorded under the study runtime's `gpu-jobs/` receipts. The root owns
rollout collection, completion audits, data/protocol freeze, schedule, and eval.

## Capacity boundary and measurements

The removed dense BF16 logits tensor would cost 15.16 GiB at 32,768 tokens,
37.89 GiB at 81,920, **per tensor**. Teacher hidden storage instead costs
0.25/0.625 GiB. A 32-token head chunk needs about 15.16 MiB per BF16
`(chunk,V)` array, plus FP32 normalization/probability buffers. This removes
the head's sequence-length multiplication, not the backbone's memory cost.

The 32-layer backbone's checkpoint inputs alone can be of order 8 GiB at
32k or 20 GiB at 81k (BF16 `(n,4096)` per layer); prompt tokens, rotary
states, layer recomputation workspaces and attention masks add memory.
CPU hooks offload saved activations/checkpoint inputs while retaining model
parameter storages, including parameter views. PyTorch checkpoint's own
nested hooks may retain/recompute intermediates; CPU equivalence does not
establish a full-size GPU peak. The fallback linear-attention kernels in the
installed runtime are also a potential long-sequence runtime cost.

32k/81k CUDA capacity, speed, head GEMM rounding, and the CUDA transfer branch
of offload remain **unmeasured** pending the authorized real trajectory smoke
test. None of these improvements proves that long OPD will improve transfer.
Receipts log per-example KL/quartiles, every completion length, gradient norm,
GPU allocated/reserved peaks, host process peak RSS, teacher CPU bytes,
offloaded byte counts/budgets, elapsed time, adapter integrity and exact
optimizer save/reload equality/step values. Host RSS does not measure other
users' memory, and MemAvailable is only a current snapshot.

Every optimizer update and the saved/reloaded state must have one common step
equal to `prior_global_updates + updates`. The receipt records `global_updates`
and `optimizer_step_min/max`; a standard round r is 2r, and the separate
single-example technical update is 1. CPU tests also compare a four-example
dense/streamed AdamW update and verify that resumed versus uninterrupted
parameters and optimizer state are bit-equal after the next update.
