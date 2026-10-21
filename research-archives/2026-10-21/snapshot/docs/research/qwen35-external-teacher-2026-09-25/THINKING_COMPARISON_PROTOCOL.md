# Fresh4 Thinking-mode comparison (fixed before generation)

## Purpose

Compare Qwen3.5-9B with and without the tokenizer's `enable_thinking` option
on the completed fresh4 stage-localization probes. This is a paired inference
comparison, not a new SFT run or a test of autonomous geometric discovery.

## Matched generation

Run the existing `generate.py` with `--thinking` on exactly the four frozen
job files used for the previous non-Thinking study:

1. `heldout-near-transfer/followup-fresh4/eval_jobs.json` on both untouched
   base and the existing all-37 low-dose adapter: six jobs each.
2. `heldout-near-transfer/followup-relation-given-fresh4/eval_jobs.json` on
   untouched base: six jobs.
3. `heldout-near-transfer/proof-gap-diagnostic-fresh4/condition_c_claim_jobs.json`
   on untouched base: three jobs.
4. `heldout-near-transfer/proof-gap-diagnostic-fresh4/condition_d_proof_jobs.json`
   on untouched base: three jobs.

Only the chat-template `enable_thinking` flag changes. Preserve each job's
English wording, seed and ID, model revision, adapter, sample count 1, cap
32768, context 45056, temperature 1.0, top-p 0.95, top-k 20, and presence
penalty 1.5. Use the same output driver and separate output directories; do
not overwrite earlier receipts. Run only one GPU generation process at a
time. Verify receipts, finish reason, token count, and the actual rendered
prompt suffix. No training is authorized by this comparison.

## Mode-aware answer extraction and grading

The non-Thinking template ends in an *empty* `<think>...</think>` block in the
prompt. Therefore every generated token is in the visible assistant answer.
The previous driver nevertheless split `raw_text` at any generated
`</think>`; seven of 24 prior outputs spontaneously emitted such a token, so
the saved `final_text` is only the suffix in those cases. For a fair primary
baseline, assess the entire generated `raw_text` as the non-Thinking answer;
report separately whether this changes any conclusion relative to the prior
`final_text` grades. A stray control token and contradictory material remain
quality defects, not valid hidden reasoning.

The Thinking template ends with an *open* `<think>` in the prompt. For each
Thinking generation, the reasoning segment is generated text up to its first
`</think>`; only the generated suffix after that marker is the visible final
answer. Require a closing marker and a substantive final answer. If the
completion reaches the token cap before a closing marker, report truncation
and no final answer rather than treating the trace as final. If extra markers
appear after the first closure, report them and inspect explicitly. Preserve
the raw trace for mechanism analysis, but grade the final answer for valid
relation, self-contained proof, selected branch, exact value, and use using
the frozen `STAGE_LOCALIZATION_GRADING.md` rubric. A correct thought that is
absent from the final answer does not earn proof credit.

For unhinted A/E, compare each paired numeric instance under base and adapter.
Blind the mode/condition labels during detailed math grading where practical;
open the mapping only after grades are frozen. For B/C/D, retain the original
distinction between supplied generic lemma, supplied unproved target claim,
and supplied construction proof. Score conditional execution separately from
independent proof. Report all per-item results and the count of incomplete or
length-stopped outputs. The two numeric variants per ID and one C/D instance
remain small exploratory probes, so no probability or causal improvement
claim follows from a few changes.
