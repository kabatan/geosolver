# Geometry-family near-transfer split (exploratory positive control)

## Research question and scope

This is a small test of whether the model can reuse relations present in external-teacher answers on a new numerical instance of a related configuration. It is a positive-control step for the larger research hypothesis; it does **not** test whether the model autonomously invents useful relations or learns them from its own unsuccessful attempts.

The five held-out IDs form three evidential groups, not five independent examples:

| Group | Held-out IDs | Relation to training answers |
|---|---|---|
| Orthocenter/median projection | H03, H04, H14 | H01 directly teaches the projection parameter involving `(BC/2)^2/AM^2`; H04 also shares the half-base-square term with DA05. Treat the three targets as one lemma cluster. |
| Tangent-circle/reflection near transfer | H08 | H07 teaches tangent-circle equations and a base-line reflection. The target's acute-branch angle relation is not in the audited teacher lemmas. Several DA/DB answers use related tangent-circle methods; see `lemma_overlap.json`. |
| Three-reflection midpoint exploration | H15 | No audited training answer gives the decisive three-reflection midpoint lemma. H07 has a weak one-reflection overlap and DA15 has a nearby perpendicular-bisector construction. Report separately from H08. |

The specific source/target lemma audit is in `lemma_overlap.json`. The project has already inspected related development material, and an earlier assistant subtask had seen portions of existing d1/job material. Therefore this is explicitly **post-hoc exploratory**, not an untouched confirmatory holdout. Do not reuse the six proof-development prompts as confirmatory evidence; they were already inspected and have teacher-lemma overlap.

## Frozen files

- `train.json`: 32 of the 37 existing audited external-teacher answer rows. H03, H04, H08, H14, and H15 are excluded as whole configuration families. Only each source's v0 answer is used; no v1-v3 teacher answers are added.
- `target_eval_jobs.json`: one fresh English numeric prompt for each held-out target.
- `retention_control_jobs.json`: fresh numerical instances of four trained configurations (H01, H02, H07, H13). These measure same-configuration generalization, not training-example memorization.
- `eval_jobs.json`: the nine first-pass prompts in a fixed order. The original base and the adapter must receive these exact prompts and seeds.
- `eval_jobs_repeat1.json`: one pre-rendered second-seed pass for every prompt. Run it only under the rule below, for all four conditions and all nine items.
- `answer_key.json`: exact answers, parameters, givens, and expected decisive relations. Never include it in model input.
- `construction_checks.json`, `lemma_overlap.json`, `split_manifest.json`, and `hashes.json`: construction, leakage, split, and integrity records.

The fresh givens are parameter-extended through a wrapper in this folder only. The canonical generator and approved problem templates are read-only. Every candidate passed the generator's exact construction assertions, full-template parse, and independent answer-formula check. The designated visible given for each candidate lies outside the projection of the canonical generator's finite old parameter domain; candidates were also checked against all canonical v0-v3 training-variant signatures and the declared similarity scales. This lets the freeze avoid reading the existing d1 file. The d1 file and model outputs were not opened during this freeze run.

The generation order is deterministic: choose the first valid tuple in the fixed Cartesian parameter order in `freeze_near_transfer.py`, subject to those predeclared novelty and construction checks. Recreate the files with Python 3.12 and SymPy 1.14.0:

```bash
uv run --no-project --with sympy --python /path/to/python3.12 python \
  docs/research/qwen35-external-teacher-2026-09-25/heldout-near-transfer/freeze_near_transfer.py
```

## Training comparison

Train three independent adapters, each initialized from the same original `Qwen/Qwen3.5-9B` revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`. Do not resume any of them from the 37-example or another comparison adapter.

| Condition | Frozen input | Rows | Learning rate | Epochs | Seed | Planned updates |
|---|---|---:|---:|---:|---:|---:|
| 32-original (primary near-transfer arm) | `train.json` in this folder | 32 | `1e-5` | 1 | `2026092431` | 32 |
| 36-multi (comparison arm A) | `multi-A-train.json` (numeric counterfactual additions) | 36 | `1e-5` | 1 | `2026092431` | 36 |
| 36-repeat (comparison arm B) | `multi-B-train.json` (exact v0 duplicate controls) | 36 | `1e-5` | 1 | `2026092431` | 36 |

The mapping is fixed: **A = multi** uses the audited H01/H07 v1/v2 candidates; **B = repeat** adds exact prompt-and-answer copies of the matching H01/H07 v0 rows. Both files use the same ordered 32-row base and matched source-presentation counts; their manifests and hashes are recorded in `multi-comparison-manifest.json`.

For all three, keep LoRA rank 8/alpha 16, the existing attention and MLP projection modules, gradient clip `1.0`, AdamW with zero weight decay and constant learning rate, micro-batch 1, maximum sequence length 8192, and the same non-thinking conversation template. Train on the visible teacher answer plus EOS only. The three adapters must be independent runs with the same seed, not continuation runs.

Both 36-row files must follow the same heldout-family boundary as `train.json`: no answer/example from H03, H04, H08, H14, or H15 may appear in any training arm, regardless of variant or repetition. Freeze and hash the two files and verify those IDs are absent before launching training; if either file violates this condition, do not run the four-condition comparison until its split is repaired.

This lower dose was selected after prior development-set diagnostics showed collapse under `5e-5 × 2 epochs`; that is a result-informed exploratory choice, not a blind confirmatory setting. The high-dose `32-original` recipe (`5e-5 × 2 epochs`) is reserved as a separate diagnostic only if needed; it is not part of the main comparison and cannot replace the low-dose adapter based on these heldout outcomes. Record receipts and adapter hashes next to experiment outputs, outside this frozen-input folder.

## Evaluation and scoring

Evaluate four conditions on the same nine jobs in `eval_jobs.json`: untouched base, 32-original, 36-multi, and 36-repeat. Every condition receives identical job text, per-job seed, decoding settings, and output budget: non-thinking generation, temperature 1.0, top-p 0.95, top-k 20, presence penalty 1.5, maximum 32768 new tokens, one sample per job. Keep raw outputs out of this frozen-input directory.

Blind the scorer to model condition and score each answer on four separate binary criteria:

1. **Exact value:** the final value is mathematically equivalent to the answer key.
2. **Useful relation:** it states a true, nontrivial relation that reduces the target problem and is relevant to this construction.
3. **Proof:** it derives the relation from the construction, including decisive branch/sign conditions.
4. **Use:** it correctly substitutes the fresh givens and obtains the exact answer.

The primary complete-solution score is the conjunction of all four. Preserve each component score and configuration-level results; do not replace them with a fluency score.

Interpret results in this order:

- **Projection-cluster transfer:** for 32-original, report H03/H04/H14 together. A preliminary positive signal requires complete solutions on at least two of the three after SFT and at least one target on which 32-original is complete while the base is not. This is evidence for reuse of the H01-like projection relation, not three independent transfer successes. Compare 36-multi and 36-repeat on the same items as secondary data-regime controls.
- **H08 near-transfer:** report separately for all three adapters. It supports broader near transfer only if an adapter newly gives a complete solution relative to the base; it is the one target testing tangent-circle/reflection methods beyond the exact projection cluster.
- **H15 exploration:** report on its own. Success is interesting evidence on an independent three-reflection case, but it is not counted as direct teacher-lemma transfer.
- **Retention:** compare the four fresh same-configuration controls for each adapter. Call retention approximately preserved only if that adapter's number of complete solutions is no more than one below the base's. With four controls this is a coarse descriptive guard, not a statistical claim.

Report numeric and proof components separately, all nine item-level paired outcomes, and the three target groups. No significance test is warranted at this sample size. Even a positive result does not establish the broader self-generated-learning hypothesis.

## Sequential rule

1. Run one sample for all nine prompts for each of the four conditions (base, 32-original, 36-multi, 36-repeat) with the frozen first-pass seeds.
2. If the 32-original projection-cluster score is near its two-of-three threshold (exactly one or two complete answers), or H08 is partial/discordant between base and 32-original, or the aggregate near-transfer comparison is within one complete solution of zero, run `eval_jobs_repeat1.json` for **all nine prompts in all four conditions**. Do not repeat only favorable items or edit prompts.
3. Score the combined two-sample record descriptively. Do not choose a checkpoint, prompt, or decoding setup using these outcomes. Any follow-up training/data adjustment gets a new dated split and a new independent test family.

## Freeze caveat

`split_manifest.json` records that this was not blind to the earlier research context. The procedural freeze did not inspect existing d1 contents or model outputs, but prior assistant work had already seen some d1/job material and the target IDs arose from an earlier overlap audit. Treat this as an exploratory design artifact and use independently authored, not-yet-inspected families for a later confirmatory study.
