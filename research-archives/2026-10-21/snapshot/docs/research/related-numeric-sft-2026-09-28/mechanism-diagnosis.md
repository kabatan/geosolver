# Numeric SFT mechanism diagnosis

This is a posthoc interpretation of the completed base and SFT-A digit probes and the existing greedy-fit summary. No model was run or trained for this diagnosis.

## What the digit-loss change says

The probe teacher-forces the correct answer prefix and scores the next target token. Its cross entropy (CE) therefore measures how predictable the correct tokens are when all previous answer tokens are supplied. It does not measure a free-running answer.

I decomposed the all-target CE change using each category's token share:

\[
\text{contribution}_g=\frac{n_g}{N}(CE_{base,g}-CE_{SFT-A,g}),\qquad
\text{share}_g=\frac{\text{contribution}_g}{CE_{base,all}-CE_{SFT-A,all}}.
\]

Base and SFT-A have the same category token counts within each split, so these contributions sum to the observed all-target CE decrease. Positive values improve CE; negative values are regressions.

| Split | All-target CE, base → SFT-A | Decrease | Leading 6 digits | Remaining digits | Format tokens | EOS |
|---|---:|---:|---:|---:|---:|---:|
| Train, 80 examples | 2.5232 → 2.0291 | 0.4941 | 0.0791 (16.00%) | 0.3965 (80.25%) | 0.0230 (4.66%) | −0.0045 (−0.91%) |
| New shape, 10 examples | 2.5112 → 2.0641 | 0.4471 | 0.0824 (18.44%) | 0.3566 (79.75%) | 0.0249 (5.57%) | −0.0168 (−3.75%) |

These are weighted contributions to the all-target decrease, not the unweighted CE change within each category. The remaining-digit category has the largest contribution because it contains the most tokens and its CE fell by 0.689 on train and 0.621 on new-shape. Leading-six-digit CE fell by 0.250 and 0.258 respectively. Format-token CE fell sharply but those tokens account for few targets. EOS CE worsened in both splits and slightly offsets the gains.

Token top-1 accuracy also rose: all-target accuracy increased from 15.82% to 23.34% on train (+7.51 percentage points), and from 17.02% to 22.87% on new-shape (+5.85 points). On the new-shape set, leading-digit top-1 rose by 15 points, while remaining-digit top-1 rose by only 1.85 points. These are still teacher-forced next-token measurements.

## What the greedy outputs add

The completed posthoc greedy-fit summary is a separate measurement of generated numeric answers. For SFT-A, median relative error fell from 0.864 to 0.170 on the 80 trained examples and from 0.922 to 0.250 on the 10 new-shape examples. The summary's `correct` count is 0 for base and SFT-A on both splits. SFT-A had 5/80 train and 2/10 new-shape outputs within 1%; within 5%, 19/80 and 3/10; within 10%, 29/80 and 3/10.

So the evidence supports improved conditional prediction of gold answer tokens and closer generated numbers on these samples. It does not show exact numerical mastery or establish a reusable arithmetic procedure. The gold-prefix probe and free-running generation answer different questions. The 10-item new-shape set and this exploratory greedy metric do not tell us whether the gains come from following numeric inputs, learning common answer patterns, or both.

The result concerns this dataset, SFT-A checkpoint, recipe, and 128-update run. It should not be generalized into a rejection of SFT as a method; other data, objectives, models, and budgets remain untested here.

## One small, unexecuted auxiliary experiment

To distinguish input-conditioned mapping from movement toward familiar answer values, use a matched input-perturbation evaluation on the existing base and SFT-A checkpoints. This is an auxiliary suggestion, separate from the root agent's next-training proposal; it is not run as part of this diagnosis and requires no new training.

Use 10 construction families and two unseen parameterizations per family: **10 matched pairs, 20 prompts**. Within a pair, preserve the wording and construction, vary one free parameter of the original construction, then regenerate all dependent givens and recompute the exact answer from the original construction. Do not arbitrarily change a dependent condition, since that could violate existence or branch assumptions. Choose each pair so its correct answers differ by at least 10%, and use the exact numeric-only target at full precision for each member.

Run the same greedy decoding settings on both checkpoints. Record exact-correct rate, median relative error, and whether each prediction changes in the target's direction and tracks the gold answer delta. Teacher-forced digit CE on the same correct targets can be logged separately. This tests input sensitivity while preserving the intended prompt-to-correct-number supervision; do not shuffle targets or use model-generated labels. A positive result would be stronger evidence of input-conditioned numeric mapping, not proof of broad construction transfer.

The numerical decomposition and greedy summary are also stored in [mechanism-diagnosis.json](mechanism-diagnosis.json). The review used the two digit-probe summaries and the status/scope/summary block of `greedy-fit-scores.json`. An initial unfiltered display was clipped and incidentally showed some row excerpts; those excerpts were not analyzed or used. Training prompts and inputs were not inspected.
