# Answer-conditioned on-policy distillation worker

`train_worker.py` performs one bounded training round on already generated student rollouts. It does not generate examples or evaluate the adapter. Run it with the existing vLLM environment after the rollout batch and GPU schedule are ready:

```bash
qwen/.runtime/vllm-venv/bin/python docs/research/answer-opd-pilot-2026-09-26/train_worker.py --cpu-check
qwen/.runtime/vllm-venv/bin/python docs/research/answer-opd-pilot-2026-09-26/train_worker.py --config CONFIG.json --batch BATCH.json --out NEW_OUTPUT_DIR
```

`CONFIG.json` fields:

```json
{
  "model_metadata": "docs/research/qwen35-self-materials-2026-09-23/model.json",
  "seed": 20260926,
  "max_completion_tokens": 1024,
  "max_sequence_tokens": 8192,
  "learning_rate": 0.000005,
  "grad_accumulation": 4,
  "grad_clip": 1.0,
  "kl_chunk_tokens": 64,
  "lora_rank": 8,
  "lora_alpha": 16,
  "lora_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "in_proj_qkv", "in_proj_z", "out_proj", "gate_proj", "up_proj", "down_proj"],
  "prior_checkpoint": null
}
```

For rounds after the first, set `prior_checkpoint` to the preceding output directory. The worker requires identical training parameters and model revision across rounds and restores `optimizer.pt`. `max_completion_tokens` accepts 1024–4096, and `max_sequence_tokens` is bounded at 8192 for this pilot.

`BATCH.json` fields:

```json
{
  "round": 1,
  "policy_adapter_sha256": null,
  "examples": [
    {
      "id": "example-01",
      "reference": "4",
      "student_prompt_ids": [1, 2],
      "teacher_prompt_ids": [1, 3],
      "completion_ids": [4, 5],
      "finish_reason": "length",
      "student_thinking": false,
      "teacher_thinking": false
    }
  ]
}
```

The token arrays above only illustrate the JSON shape; actual IDs must come from the local Qwen tokenizer and the same student generation. Include at most 32 examples with unique IDs. Both prompts must already include their assistant generation prefix, and `completion_ids` must exclude the prompt. The teacher prompt should differ only by the numeric-answer hint and must use the same thinking setting intended in the protocol. For later rounds, `policy_adapter_sha256` must equal the previous output's `vllm_adapter_sha256` in `receipt.json`, because `adapter-vllm/` is the actual rollout policy. The worker independently verifies the previous canonical PEFT adapter hash before resuming. The reference is recorded for provenance but does not enter the loss. Proof targets or teacher continuations are rejected.

If a completion exceeds the cap, training uses its first `max_completion_tokens` tokens. The event records both lengths and `prefix_is_complete_answer=false`; a length-limited rollout is also treated as a prefix even when its full supplied sequence is under the cap. An empty completion or identical student/teacher prompt is rejected.

For each example, the worker evaluates the frozen base teacher with its adapter disabled, keeps teacher logits on CPU, and evaluates the student on its own sampled tokens. `logits_to_keep=n+1` and dropping the final logit align the two distributions at each completion token. A custom autograd function computes exact full-vocabulary forward KL in 64-token chunks and recomputes the softmax during backward. One pass over the batch uses four-example gradient accumulation (a shorter final group is averaged by its actual size), AdamW with zero weight decay, and a constant 5e-6 learning rate.

Every new output directory contains `examples.jsonl`, `receipt.json`, canonical `adapter/adapter_model.safetensors`, mapped `adapter-vllm/adapter_model.safetensors`, and `optimizer.pt`. Use the canonical adapter to resume training with PEFT and the mapped adapter for vLLM rollout/evaluation. The mapping inserts `model.language_model.` into the layer keys, following the [prior Qwen3.5 mapping audit](../qwen35-sft-pilot-2026-09-24/ADAPTER_MAPPING_AUDIT.md); the worker verifies all 400 mapped tensor values on CPU. The receipt records input and output hashes, actual optimizer updates, changed LoRA tensors, peak memory, and saved adapter tensors verified by loading the safetensors files on CPU. Each event records total mean KL, KL mean in each consecutive completion quartile, the isolated example gradient norm before accumulation, token lengths, finish reason, thinking flags, completion hash, and whether the trained prefix is a completed answer. A failed run leaves a failed receipt and does not mark a checkpoint complete.

`rollout_worker.py` reads a pool of rows `{id, source_id, variant, reference, student_messages, teacher_messages}` and generates exactly eight new non-thinking student completions per round. It writes `batch.json` for the trainer, `raw_rollouts.json` with full decoded text and token IDs, and a hashed receipt. Its config reads the same training fields plus:

```json
"rollout": {
  "batch_size": 8,
  "max_num_seqs": 8,
  "generation_max_tokens": 2048,
  "max_model_len": 8192,
  "gpu_memory_utilization": 0.8,
  "temperature": 1.0,
  "top_p": 0.95,
  "top_k": 20,
  "presence_penalty": 1.5,
  "seed_base": 20260926
}
```

`run_study.py --config CONFIG.json --pool TRAIN_POOL.json --eval-jobs FROZEN_EVAL_JOBS.json --out NEW_STUDY_DIR --start-round 1 --end-round 16` runs 16 rounds, selecting the next eight ordered pool rows each time. Each round uses a fresh vLLM subprocess, followed by a fresh trainer subprocess after generation exits. This gives 128 sampled rollouts and 32 actual optimizer updates; evaluation remains a separate operation. To continue in a new study directory, pass `--start-round 17 --end-round ... --prior-checkpoint PREVIOUS_ROUND_TRAIN_DIR`. The runner records the frozen evaluation jobs hash for provenance, passes through subprocess failures, and writes per-round logs. The rollout receipt also reports generation-only tokens per second; `rollout.max_num_seqs` accepts 2, 4, or 8, with eight used for the main run. Use `rollout_worker.py --preflight ...` or `run_study.py --preflight ...` for CPU-only validation before GPU scheduling.

CPU-only checks performed before GPU scheduling: exact chunked KL value and gradient agree with dense KL; quartile KL means reconstruct the overall KL; identical distributions give zero KL and gradient; schema rejects same-point conditioning; a tiny CPU LoRA adapter saves and reloads with matching safetensors; 400 existing Qwen3.5 tensors export with equal values to vLLM layer names; the local Qwen config exposes its vocabulary under `text_config.vocab_size`; synthetic eight-row pool preflight passes.
