# Projection-ID leave-one-out lower-bound experiment

## Purpose and limitation

This is a small, result-informed exploratory lower-bound check for the three projection-family configurations H03, H04, and H14. Each arm removes one configuration's original teacher answer while retaining the other two related projection configurations. It therefore tests transfer from sibling configurations, **not** transfer to a held-out lemma family. For any arm, the other two projection IDs plus H08 and H15 are in its training set; their fresh target jobs are prohibited in that arm's evaluation.

The three datasets are exact filters of the original 37-row external-teacher `train.json`:

| Arm | Excluded teacher ID | Included sibling projection IDs | Only target job allowed for this arm |
|---|---|---|---|
| `minus-H03` | H03 | H04, H14 | existing fresh H03 job |
| `minus-H04` | H04 | H03, H14 | existing fresh H04 job |
| `minus-H14` | H14 | H03, H04 | existing fresh H14 job |

H08 and H15 are also present in all three 36-row training sets. Their target prompts must not be run or scored in this leave-one-out experiment.

Each arm also uses the same four existing fresh retention controls: H01, H02, H07, and H13. Thus an arm is evaluated on exactly five jobs: its one corresponding target plus all four controls. Compare each adapter to the untouched base on those exact prompt/seed pairs. For efficiency, the base can be evaluated once on the union of the three target jobs and four shared retention jobs; reuse only those base outputs for the corresponding paired comparisons.

## Training conditions

Train three independent adapters, each initialized from the original `Qwen/Qwen3.5-9B` revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`:

| Condition | Dataset | Examples | Learning rate | Epochs | Seed | Updates |
|---|---|---:|---:|---:|---:|---:|
| minus-H03 | `train-minus-H03.json` | 36 | `1e-5` | 1 | `2026092431` | 36 |
| minus-H04 | `train-minus-H04.json` | 36 | `1e-5` | 1 | `2026092431` | 36 |
| minus-H14 | `train-minus-H14.json` | 36 | `1e-5` | 1 | `2026092431` | 36 |

Use the same low-dose recipe as the main comparison: LoRA rank 8/alpha 16, existing attention and MLP projection modules, gradient clip 1.0, AdamW with zero weight decay and constant learning rate, micro-batch 1, maximum sequence length 8192, visible teacher answer plus EOS, and the same non-thinking conversation template. Each run starts from the original base; do not continue or share adapters between arms.

The low-dose setting was chosen after prior development diagnostics showed collapse at `5e-5 × 2 epochs`. That result informed the setting, so this is exploratory, not confirmatory. Do not use the results below to select checkpoints or revise these three datasets.

## Evaluation rules

- Use existing `target_eval_jobs.json` entries for H03, H04, and H14 and existing `retention_control_jobs.json` entries for H01, H02, H07, and H13. Do not copy, edit, or regenerate these frozen jobs.
- `minus-H03` receives only H03 plus the four controls; `minus-H04` receives only H04 plus the controls; `minus-H14` receives only H14 plus the controls.
- Do not score H04 or H14 under `minus-H03`; do not score H03 or H14 under `minus-H04`; do not score H03 or H04 under `minus-H14`. Those answers were included in the corresponding training dataset.
- Compare every arm to base with identical prompt text and frozen seed. Use the existing decoding settings: non-thinking, temperature 1.0, top-p 0.95, top-k 20, presence penalty 1.5, up to 32768 new tokens, one sample per job.
- Score exact value, useful relation, self-contained proof including branches, and correct use of the fresh givens as separate binary criteria. The complete-solution score is their conjunction. Report each arm's one target separately from its shared retention controls; do not pool the three targets as independent-family transfer.
- If a second sample is needed, use only the existing repeat1 job with the matching target and all four controls for every compared condition in that arm. Do not selectively repeat an item or change a prompt.

## Integrity and files

`prepare_leave_one_out.py` writes only the three datasets, `arm_manifest.json`, and `hashes.json` in this subfolder. The manifest records each dataset hash, excluded/included IDs, allowed target and retention job IDs, plus hashes of the frozen upstream files. All three files must have 36 rows and differ from the original only by the named omitted row. No existing 32-original, 36-multi, 36-repeat dataset or frozen evaluation file is modified.

Recreate the three local datasets and manifest with:

```bash
python3 docs/research/qwen35-external-teacher-2026-09-25/heldout-near-transfer/leave-one-projection-id/prepare_leave_one_out.py
```
