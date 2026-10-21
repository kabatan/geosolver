# Numeric SFT: successful 56-row versus 80-row recipe comparison

This is a read-only CPU audit of the frozen training datasets, configs, trainer receipts, tokenization receipts, and already-saved digit-probe summaries. It did not run a model or inspect held-out answer keys. The differences below are observed confounds; this audit alone does not identify a single causal factor.

## What stayed fixed

Both recipes use **Qwen/Qwen3.5-9B** at revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`, the same `train_sft.py` driver hash and harness hash, LoRA rank/alpha/modules, AdamW (`weight_decay=0`), learning rate `5e-6`, gradient accumulation 4, clip 1.0, target/sequence caps 4096/8192, CE chunk 64, and `enable_thinking=false`. At 128 cumulative updates, both have 512 example presentations. The matched primary seed is `2026092701`.

The exact English instruction prefix is byte-identical across every row: `Solve the following numerical geometry problem. Give only the requested numerical value, with at least 10 significant digits when appropriate. Do not give a proof or explanation.` Its SHA-256 is `06852637dd33549b484432bb75567b81c0e8dd39f6418a79c3b56cdb5d871796`. Both datasets enforce one user prompt and a numeric-only assistant target; target strings pass the Python `.17g` round-trip check (56/56 old, 80/80 new). The trainer masks loss to the assistant target including EOS. The body after the prefix is different geometry content and different numeric instances.

The dose-control `train-correct.json` is byte-identical to the 80-row related-SFT `train.json`; it is the same training data, not a third dataset. Its longer 512-update run changes the training dose, not the 80 prompt/target pairs.

## What changed in the 128-update comparison

The old dataset has **56 rows / 7 normalized shape templates** (DA01, DA05, H01, H04, H07, H13, H15); the new dataset has **80 rows / 10 templates** (DA01, DA02, DA03, DA04, DA06, DA07, DA08, DA11, DB02, DB12). Each source family has 8 numeric parameterizations. Only the family label `DA01` is shared; row IDs do not overlap. Same label does not establish identical prompts: this audit compares rendered bodies, not labels alone.
At 128 updates, both chains process 512 examples and nearly the same number of assistant target tokens: **9,656 old vs 9,711 new** (including the EOS tokens counted in tokenization). Per-example repeat exposure nevertheless falls from 512/56 = **9.14** to 512/80 = **6.40** presentations per row on average. This is the clearest recipe-level dose difference at fixed updates: equal total presentations, broader set, fewer repeats per item. The dataset cardinality also changes the deterministic order, even with the same seed.
Prompt/token counts: the old prompt is 164.0 tokens median and the new prompt 176.0; target is 19.0 vs 19.0 tokens median (target-token counts include EOS). The output lengths are close; the new tasks are not simply longer numeric labels.
Target-value distribution changes materially: old range **1.60363–1451.27** (median 9.39476; 0 below 1), new range **0.23744–70.5177** (median 6.55441; 4 below 1). The old set includes a much larger upper tail; the new set adds sub-unit values. Lexical significant-digit counts are [15, 17.0, 17] old vs [15, 17.0, 17] new; both are rounded through the same `.17g` formatting rule.

Shape breadth also changes. The old families include orthocenter/midpoint-foot constructions (H01/H04), a two-circle configuration (H07), tangent/circle geometry (H13/H15, DA01/DA05); the 80-row set mixes ten distinct bodies including tangent-circle, Fermat-point/circumcenter, chord-interior tangency, midpoint, and cevian constructions. Source IDs are construction labels, not proof that all prompts within the set have equal mathematical complexity. The per-family shape previews, input-literal counts, prompt lengths, and output ranges are preserved in the JSON for inspection.

### old56 source families

| Source | N | Decimal givens, median | Prompt tokens, median | Target range | Normalized construction preview |
|---|---:|---:|---:|---:|---|
| DA01 | 8 | 3 | 157 | 2.5684–12.914 | Triangle ABC has AB=<N>, BC=<N>, and CA=<N>. One circle passes through A and B and is tangent at A to lin |
| DA05 | 8 | 2 | 164 | 1.6366–12.506 | Let ABC be an acute scalene triangle with BC=<N>. Let ω<N> be a circle through A tangent at B to line BC, |
| H01 | 8 | 2 | 128 | 2.6122–13.875 | Let H be the orthocenter and M the midpoint of BC in an acute scalene triangle ABC. Let P be the foot of  |
| H04 | 8 | 2 | 151 | 11.105–88.326 | In an acute scalene triangle ABC, let H be the orthocenter, M the midpoint of BC, and P the foot from H t |
| H07 | 8 | 3 | 219.5 | 1.6036–48.305 | Two circles tangent to line AB at A and B intersect at M and N on the same side of AB, with M closer to A |
| H13 | 8 | 3 | 185 | 20.446–1451.3 | In an acute scalene triangle ABC, BC=<N> and cos(angle ACB)=<N>. Let M be the midpoint of AC. The tangent |
| H15 | 8 | 3 | 211 | 1.9215–10.41 | Let ABC be a scalene triangle with angle BAC=<N> degrees, and let Ω be its circumcircle. The tangents to  |

### new80 source families

| Source | N | Decimal givens, median | Prompt tokens, median | Target range | Normalized construction preview |
|---|---:|---:|---:|---:|---|
| DA01 | 8 | 3 | 160 | 7.8577–11.658 | Triangle ABC has AB=<N>, BC=<N>, and CA=<N>. The circle through B tangent to line AC at A and the circle  |
| DA02 | 8 | 2 | 162 | 1.98–8.4518 | In triangle ABC, angle BAC is <N> degrees, AB=<N>, and AC=<N>. An interior point T satisfies angle ATB =  |
| DA03 | 8 | 2 | 169 | 16.391–70.518 | Let O be the circumcenter of an acute scalene triangle ABC. The circle through A and C tangent to line AB |
| DA04 | 8 | 3 | 185 | 2.8986–11.805 | Point P lies inside chord AB of circle Omega, with AP=<N> and PB=<N>. A circle through A and P internally |
| DA06 | 8 | 2 | 191 | 1.0619–2.2069 | Let O be the circumcenter and M the midpoint of BC in an acute scalene triangle ABC with AB>AC. Circle om |
| DA07 | 8 | 3 | 215 | 3.457–42.752 | In an acute scalene triangle ABC, let O and H be the circumcenter and orthocenter. Let M be the intersect |
| DA08 | 8 | 2 | 176 | 0.23744–3.1875 | In an acute scalene triangle ABC, let O be the circumcenter. On the circle through B,O,C, let Q be the po |
| DA11 | 8 | 3 | 174.5 | 5.3084–16.85 | An acute scalene triangle ABC has AB=<N>, BC=<N>, and circumradius <N>. Let I and J be the midpoints of A |
| DB02 | 8 | 3 | 178 | 5.4088–13.712 | Let ABC be a triangle with AB=<N>, AC=<N>, and BC=<N>. Choose P and Q in the interior of BC so that angle |
| DB12 | 8 | 3 | 207 | 3.9114–9.7586 | In triangle ABC, angle BAC is <N> degrees and BC=<N>. Let D_1 and D_2 divide BC internally in the ratios  |

## Saved digit-loss diagnostic

The available 80-row probe compares base to SFT-A-128 under **teacher forcing**: each token is evaluated with the full correct answer prefix. On the 80 training rows, all-target token-weighted CE is 2.523 → 2.029 (Δ -0.494). The target has 1517 scored tokens: the first six significant digits contribute Δ -0.079 to the all-target change, remaining digits Δ -0.396, format tokens Δ -0.023, while EOS contributes **+0.004** (worse). Most of the CE reduction therefore comes from later digits, with a smaller first-six-digit gain; token/format loss also improves and EOS loss worsens. This is a conditional next-token fit result, not evidence that the model can generate a correct answer unaided.

The 80-row SFT-A-128 also has a saved posthoc greedy direct-number fit summary: 29 / 80 training answers and 3 / 10 new-shape answers are within 10%. The old 56-row saved loss diagnostic is also teacher-forced, but it reports aggregate loss by presentation and token-weighted aggregates rather than these semantic digit groups. No comparable old56 first-six-versus-remaining-digit probe or exact-training-prompt greedy/free-generation fit score was found in the old recipe artifacts inspected.

## Interpretation

The training recipe machinery is effectively held constant between old128 and new A128; the observed changes are in the teaching set and its per-example exposure. The new 80-row set offers three more source shapes and expands numeric scale downward below 1 while dropping the old extreme upper tail. It also reduces average repeats per example by about 30% at the same optimizer-step count, even though total target-token presentations remain within 0.6%. Any of these could matter, and they change together. The comparison cannot say which caused the outcome. The dose-control correct512 run is a separate dose comparison (512 updates, 25.6 mean passes through the 80 rows), not evidence that 128-update differences are caused by the learning rate or optimizer.

A minimal next causal check, if needed, is to score the saved old128 adapter on its exact 56 training prompts with the same greedy decoding settings used by the 80-row direct-fit diagnostic, then compare each dataset's train-fit to its own held-out transfer under a common generation seed. This would fill the missing old free-generation-fit baseline; it would not by itself isolate dataset breadth from repetitions. The exact old adapter is `qwen/.runtime/program_self_training_followup_20260926/train-numeric128/final/adapter-vllm` (saved VLLM adapter SHA-256: `aca6d2f78e713b8979322728a397839536067a4bd827ee71b8e7b3f4a77e19da`).

## Reproduction

Run `python3 docs/research/numeric-sft-success-failure-analysis-2026-09-28/recipe-comparison.py` from the repository root. It reads only the frozen training data/config/receipts and the saved CE summaries, then regenerates this report and `recipe-comparison.json`.
