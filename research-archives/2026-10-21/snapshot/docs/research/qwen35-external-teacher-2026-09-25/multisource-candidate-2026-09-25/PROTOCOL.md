# Six-source numeric-variant candidate

**Status:** prepared and audited on CPU only. No model training or evaluation has been run with these files.

## Diagnostic question

After the frozen 38-row comparison, this candidate can test whether three new numeric instances for each of six already-trained theorem sources improve held-out proof transfer more than spending the same three extra row slots on exact repetitions of the source's v0 answer. The common 32-row training base and all five held-out source families remain fixed.

This is a narrow diagnostic of numeric-instance variation versus repetition. It does not compare different proof styles or establish that one teacher style is generally best.

## Matched arms

| Arm | Dataset | Rows | Construction |
|---|---|---:|---|
| Numeric variants | `train-50-six-source-v1-v3.json` | 50 | The frozen 32-row base plus v1, v2, and v3 for each of H01, H02, H07, DA02, DB02, and DB06. |
| Exact-v0 repetition control | `train-50-six-source-v0-repeat-control.json` | 50 | The same frozen 32-row base plus three exact prompt-and-answer copies of each of those six v0 rows. |

Both arms have 32 distinct source IDs and four rows for each selected source. Their 18 additional rows occupy the same source slots. The held-out configuration families H03, H04, H08, H14, and H15 are absent from both arms.

## Teacher proof checks

The six v0 sources were accepted in `docs/research/qwen35-external-teacher-2026-09-24/audits.json`. New answers use the corresponding proved relation and apply the variant's exact givens. H01 and H02 include exact acute/scalene or circle-intersection branch checks; H07 includes an exact acute/scalene coordinate witness for all three variants. DA02 and DB02 are positive homotheties of their audited v0 constructions. DB06 scales every squared length by the same positive factor, preserving the audited convex cyclic branch and side-product condition.

For every added row, the builder checks the prompt's numerical givens against the benchmark's structured `givens`, parses and compares the derived final value to `answer_exact`, and checks branch conditions recorded in the audit. H07 numeric prompts explicitly state that the first circle is tangent at A and the second at B, matching the prior H07 variant audit; the repeat control remains an exact v0 copy. The new prompts and answers are English; no CJK characters occur. Each new answer is under 1,200 whitespace-delimited words.

## Token and integrity audit

Token counts use the local Qwen3.5 tokenizer revision recorded in `token-audit.json`, with the exact chat-template path and assistant-through-EOS span used by `docs/research/qwen35-external-teacher-2026-09-25/train_no_eos.py`. Both arms have 50 rows. Assistant targets including EOS total 29,973 tokens in the numeric arm and 30,520 in the repeat control (numeric arm −1.7923%). Prompt-plus-assistant sequences total 42,987 and 43,416 tokens respectively (−0.9881%). The longest full sequence is 1,238 tokens, well below the existing 8,192-token training cap.

`variant-audit.json` records exact-answer, branch, source-audit, and input-file checks. `token-audit.json` gives per-row counts. `hashes.json` freezes the two datasets and audit files. Rerun `build_candidate.py` with `qwen/.runtime/vllm-venv/bin/python` to recreate the candidate and refresh those hashes.

## Run boundary

These files are candidates only. If selected for a later comparison, use the same frozen model, evaluation jobs, optimizer settings, seed, and update/exposure schedule for both arms. Keep the five held-out configuration families out of any training or teacher construction. This preparation task did not start that run.

After independent CPU review accepted all 18 added proofs and the separately frozen fresh3 answer key, `train-protocol-six-source-variants.json` and `train-protocol-six-source-repeat.json` were written before any second-seed, leave-one-out, or fresh2 answers were graded. Both point to the same nine fresh3 jobs and use 50 base-start updates at `1e-5`. The second-seed and 38-row comparisons remain earlier in the execution queue. H07's added prompt clarification and the 1.79% assistant-token difference remain documented interpretation limits.
