# Projection-bridge candidate protocol

## Rotation and row design

Each leave-one-out rotation starts with the identical frozen 32-row base and
adds six rows per arm: three rows for each of the two permitted sources. The
omitted target is audit metadata only and must not occur in the training rows.

For each permitted source, treatment rows 1 and 2 focus on the construction
relation and its proof. Treatment row 3 is a separate, unhinted full-task
sample with the exact standard problem prompt and a complete integrated
solution. Control has three complete integrated solutions: one with that same
standard prompt and two distinct whole-task paraphrases. No answer may depend
on companion rows from the same source being sampled in the same training
example.

## Token-count acceptance

Count assistant answer text with the frozen tokenizer plus one EOS token per
row; prompts and chat wrappers are excluded. The common 32-row base contributes
19,936 tokens per arm. For this explicitly exploratory comparison, accept a
maximum 2% relative difference between merged 38-row totals, calculated as
`abs(treatment - control) / max(treatment, control)`. This is an approximate
full-dataset tolerance, not strict token matching.

Report addition-only counts and their relative mismatch separately. Matching
the merged totals does not mean the six added rows have equal token budgets or
equal supervision dose. Do not add unrelated text or padding to force a match;
interpret any result as exploratory and disclose the added-row mismatch.

| Rotation | Added treatment/control | Added mismatch | Merged treatment/control | Merged mismatch |
|---|---:|---:|---:|---:|
| rotation-1 | 1,424 / 1,623 | 199 (12.26%) | 21,360 / 21,559 | 199 (0.923%) |
| rotation-2 | 1,867 / 2,040 | 173 (8.48%) | 21,803 / 21,976 | 173 (0.787%) |
| rotation-3 | 1,467 / 1,389 | 78 (5.32%) | 21,403 / 21,325 | 78 (0.364%) |

## Scope

The candidate is untrained. This protocol authorizes no GPU run and makes no
claim of causal or confirmatory evidence. The projection lemma appears in
permitted-source treatment material by design, so omitted-source evaluation
is a transfer positive control.
