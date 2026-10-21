# Thinking comparison: longer output budget (user correction)

The user observed that a 32,768-token Thinking completion without a final
answer cannot show whether proof ability improved and directed us to raise the
limit. The earlier 32k Thinking base run was interrupted after three completed
outputs (H03 twice at the length cap with no `</think>`, H04 once naturally
stopped). Preserve it as a pilot, not the primary Thinking comparison.

## Revised primary condition

Run the same frozen English fresh4 jobs on the untouched base and existing
all-37 low-dose adapter, six numeric instances per model. Change only the
inference template to `enable_thinking=True` and the shared Thinking output
budget to 81,920 new tokens with context 90,112. Keep one sample, the same
per-job seeds, temperature 1.0, top-p 0.95, top-k 20, presence penalty 1.5,
model revision, and adapter. Use separate output directories and run one GPU
process at a time. Record completion time, `finish_reason`, token count,
`</think>` presence, reasoning and final segment lengths. The non-Thinking
comparison remains the already completed 32k condition; output budgets thus
differ as explicitly requested, and time/compute cannot be attributed solely
to the template flag. The comparison of final-answer quality is still useful,
but a clean flag-only experiment would require equal larger caps for both
modes.

Do not treat a length-stopped unclosed trace as a final answer. Grade only the
segment after the first generated `</think>` using the frozen stage-localization
rubric, and report the trace separately. For the non-Thinking side, use the
mode-aware raw-text audit and its sensitivity comparison to prior final-text
grades. Blind A/E mode and adapter labels during detailed math grading where
practical. If the higher cap remains insufficient, report that directly and
consider a separately labeled reasoning-budget intervention rather than
silently altering this condition.

The longer cap is within the pinned model's 262,144-token configured context.
The 32k pilot's vLLM log reported a GPU KV cache of 297,167 tokens at the
same `gpu_memory_utilization=0.85`; this suggests the longer context can fit,
but actual initialization and run receipts must verify it. The official
Qwen3.5-9B model card recommends up to 81,920 output tokens for difficult
mathematics. This is a diagnostic budget, not a promise of completion.

After the unhinted base/adapter comparison, decide whether B/C/D cue probes
need a matching long-cap Thinking rerun to explain any changed outcomes.
No SFT training is part of this request.
