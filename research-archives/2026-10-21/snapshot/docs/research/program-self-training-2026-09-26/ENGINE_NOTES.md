# Execution and SFT interfaces

No GPU jobs have been launched by these engines during preparation. The study
protocol, case generation, candidate collection/repair/selection and dataset
freeze are owned by the root orchestrator. Execution does not repair programs.

## Isolated candidate execution

Run/import `execution_harness.py` with **system `/usr/bin/python3`**. The actual
isolation boundary is installed bubblewrap: fresh user/PID/network/mount
namespaces, no further user namespaces, no capabilities, minimal read-only
system Python3.14/std-library/shared-library mounts, fresh `/tmp` and `/dev`.
There is no `/home`, repository, model, answer data, host environment or inherited
open file descriptor. `/proc` belongs to the PID namespace. Seccomp blocks
fork/clone, tracing, mounting and namespace changes; numerical algorithms and
ordinary control flow have no target-specific grammar restrictions.

Default per-input bounds are2s wall,1s CPU,256MiB address space,16KiB combined
stdout/stderr,16MiB temporary filesystem,32 open descriptors, no core dumps.
The parent kills only its own child process group on wall/output violations.
There is no unsafe fallback when OS isolation cannot start. The import and
reflection policy is additional hardening, not the claimed security boundary.

`extract_program(answer, finish_reason)` accepts only a naturally completed
(`stop`) generation. Strip exactly one terminal literal `<|im_end|>` plus
whitespace, recording the fact and retaining the original answer hash. Choose
the last parse-valid closed python/py/unlabelled fence that satisfies the
module/solve/reflection policy; later rejected fences are explicitly recorded.
Preserve its whole program. Repeated solve definitions use the last definition
by ordinary Python semantics. `normalize_program(code)` removes comments and
module/function/class docstrings using AST unparse; semantic dunder/reflection
use is rejected. Never take an earlier closed block from a length-capped
generation as a completed candidate.

Allowed candidate modules: math,cmath,statistics,fractions,decimal,itertools,
functools. The function must be synchronous `solve(givens)` with exactly one
positional parameter. Return one finite scalar real value; booleans, strings,
lists, complex values, NaN and infinities fail. Fraction and Decimal results are
accepted and converted to float. Only code plus one givens object goes to the
child. Expected answers stay in the host process.

Python API:

```python
candidate = extract_program(final_text, finish_reason)
normalized = candidate['normalized_code']
one = execute_program(normalized, givens)
receipt = evaluate_candidate(normalized, cases)
```

Each case is `{case_id, source_id, split, givens, answer}`. `evaluate_candidate`
records every output/error/time, input hashes and numerical tolerance
`abs1e-7 + rel1e-6*abs(answer)`. It does not stop at the first failure. Run raw and
normalized candidates on the same cases and compare results before acceptance;
the orchestrator must not treat normalization as an externally repaired answer.

CLI:

```
python3 execution_harness.py extract --input rollout.json --out candidate.json
python3 execution_harness.py check --candidate candidate.json --cases cases.jsonl --out checks.json --normalize
```

Extraction input accepts existing generator `final_text` (or `answer`) and
`finish_reason`. Case files can be JSON arrays or JSONL. Outputs must be new.

## Fixed-update SFT

Use the existing `qwen/.runtime/vllm-venv/bin/python` runtime. The dataset is a
JSON array with rows:

```json
{"id":"unique", "source_id":"H01", "kind":"numeric", "messages":[{"role":"user","content":"Numeric task"}], "target":"3.141592653589793"}
```

Code rows use `kind:"code"` and `target` **exactly one python fence around the
normalized program**, including its final body newline before the closing
fence. This keeps the training format consistent with generation/extraction.
The code prompt excludes concrete I/O examples. One target kind per dataset.
Messages contain user/system context, no assistant solutions.

Config required fields are `dataset`, `dataset_sha256`, `model_metadata`,
`model_metadata_sha256`, `model_revision`, `updates` (16or32). Default fixed
training parameters: seed2026092701, LR5e-6, gradacc4, clip1, r8alpha16,
dropout0, weight_decay0, nonthinking, ce_chunk_tokens64,
max_target_tokens4096, max_sequence_tokens8192. The working attention,
linear-attention and MLP module list is validated. Optional `save_checkpoints`
contains16; optional `prior_checkpoint` is a complete engine checkpoint.

```
qwen/.runtime/vllm-venv/bin/python train_sft.py --config arm.json --out new-preflight --preflight
qwen/.runtime/vllm-venv/bin/python train_sft.py --config arm.json --out new-training
```

Preflight loads the local tokenizer only, verifies exact prompt/assistant
boundary, target EOS, complete target lengths, input hashes and deterministic
shuffled repetition. There is no greater-than20-token minimum: short numeric
targets are valid. Oversize targets fail; they are never silently truncated.
Training averages4 per-example token-mean losses per update. Exact full-vocab
CE uses token chunks with FP32 normalization and a custom backward that
recomputes probabilities; a full-sequence FP32 softmax graph is not retained.

The engine records planned/actual teacher-token counts, order/hash provenance,
per-example loss, gradient norm, memory and actual updates. It saves optional
`checkpoint-016/` and final **`final/adapter`, `final/adapter-vllm`,
`final/optimizer.pt`**. Live/saved adapter tensors and reloaded optimizer tensors
are checked exactly, including global AdamW step counts. The proven Qwen3.5
vLLM mapping inserts `.language_model.`; the helper file hash is recorded.
Resume verifies prior weights/optimizer hashes and processed-example order;
16→32 extends the same deterministic order, never resets the optimizer.

## Explicit GPU-job wrapper

`gpu_job.py` executes one caller-supplied command under a nonblocking study
lock, verifies that no GPU compute process is present, prepends the authorized
process-local compatible driver library directory, and records command/input
hashes, stdout log, exit status and elapsed time. It never chooses an arm,
retries, changes system libraries or kills other GPU jobs. Root decides when
to invoke it. It is not a global scheduler for unrelated applications.

## CPU checks

```
python3 test_execution_harness.py
qwen/.runtime/vllm-venv/bin/python test_train_sft.py
```

Harness checks use actual bubblewrap against a host-only sentinel and a host
listening socket, plus read-only mounts, fork denial, CPU/wall/memory/output
limits and malformed/truncated/EOS-marked extraction. Trainer checks verify CE
values and gradients including a one-token target and BF16, real local Qwen
chat-template masks for short numeric/code targets, deterministic resume order,
and all400 mapped tensor values. These do not load model weights or run GPU.
