# Matched near-transfer data audit

This CPU-only authoring pass creates a first-step 36-row comparison. It does not train or evaluate a model and makes no transfer claim. Arm A adds four audited H01/H07 numeric counterfactual examples. Arm B adds four exact prompt-and-answer copies of the corresponding v0 teachers. Both arms share the same ordered 32-row base; H01 and H07 each appear three times, and each of the other 30 sources appears once.

## Integrity and math checks

- Each arm has 36 rows, 36 unique `id` values, and 32 unique `source` values. H03/H04/H08/H14/H15 are absent.
- Base rows are the original v0 rows. Arm A additions are candidate-H01-v1/v2 and candidate-H07-v1/v2. Arm B retains source H01/H07 and exactly duplicates the corresponding v0 prompt and answer.
- Candidate proof prefixes match the audited v0 teachers. Exact rational arithmetic verifies H01 AP=48/13 and 40/11 with positive acute-angle checks (48 and 40). H07 checks verify ON²=2401/148 and 256/13 (see manifest for reduced values), λ=37/49 and 13/16, and areas 36/7 and 9/2.
- No v3/d1 row was added. No evaluation output was opened. `eval_jobs.json` was only hashed as a protocol input.
- Both protocols use seed 2026092431, lr=1e-5, one epoch / 36 updates, assistant-only targets including EOS, the same non-thinking template, AdamW (zero weight decay), and identical LoRA settings. The row-index shuffle matches the training driver.

## Token counts

Tokenizer revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`; CPU tokenization mirrors `train.py` rendering.

| Arm | Prompt tokens | Assistant tokens incl. EOS | Assistant tokens excl. EOS | Total sequence tokens | Max sequence |
| --- | ---: | ---: | ---: | ---: | ---: |
| A | 9341 | 21854 | 21818 | 31195 | 1238 |
| B | 9337 | 21742 | 21706 | 31079 | 1238 |

Assistant-target delta A−B including EOS: **112 tokens**. Per-row counts and four matched added-slot deltas are recorded in `multi-token-audit.json`; hashes and the exact epoch-0 update permutation are in `multi-comparison-manifest.json`.
