# Supplementary numeric retention sentinel

## Status and purpose

This is a **result-informed supplementary retention diagnostic**, not a confirmatory transfer test. It adds seven fresh English numeric problems from source configurations that are in the 32-row near-transfer training set and outside both its held-out target IDs and its four existing retention IDs. The historical untouched-base grades informed which configuration IDs were selected. The questions use new numeric instances, so historical same-configuration results are selection evidence rather than item-level baseline scores.

The sentinel is intended to make numeric retention easier to interpret alongside the frozen near-transfer results. It cannot establish new-configuration transfer, autonomous relation discovery, or a causal training effect by itself. Report its result separately from the frozen nine-job comparison.

## Selection basis

The selector read only grade fields from the old 37-configuration, two-sample untouched-base numeric development evaluation at `qwen/.runtime/qwen35_diverse_sft_20260924/eval-numeric-base-en-32k/manual-grades.json`. After excluding the held-out targets H03/H04/H08/H14/H15 and the current retention controls H01/H02/H07/H13, three eligible configurations had at least one complete sample: DB02 (2/2), DA18 (1/2), and DB06 (1/2). Four more eligible configurations had correct exact values, useful relations, and applications on both historical samples, but no complete proofs: H12, HX01, DA03, and DA07 (each 0/2 complete, 2/2 exact, 2/2 relation, 0/2 proof, 2/2 application).

All seven IDs are present in `heldout-near-transfer/train.json`; none is H03, H04, H08, H14, H15, H01, H02, H07, or H13. The full per-ID grade counts, selection rule, and historical grade-file hash are frozen in `selection_basis.json`.

## Frozen inputs

- `eval_jobs.json`: one English job per selected source ID, with a fixed deterministic seed. Every comparison arm should receive the same prompt and seed. Keep the answer key out of model input.
- `answer_key.json`: exact answer, givens, expected decisive lemma, and construction parameters for grading.
- `construction_checks.json`: canonical generator and answer checks, novelty audit against all four v0-v3 training rows per ID, authoring-witness checks, and source hashes.
- `hashes.json`: SHA-256 hashes of all frozen outputs and source inputs.

HX01 uses the canonical construction generator with a fixed parameter tuple extended beyond its finite sampling options. DB02, DA18, DB06, H12, DA03, and DA07 use the canonical exact similarity transform at scale 7/4, which is outside the predefined similarity-scale list. The independent H12 relation check is also applied after scaling. Exact full-given signatures were compared with each selected ID's v0-v3 training variants; no collision was found. The English questions are rendered with the approved templates and common English instruction.

For DA03, DA07, and DA18, the existing CPU authoring witness is numerical; all source givens and answers were matched to the exact authoring cards within its stated 1e-8 tolerance. The new answers themselves are exact because the similarity transform applies the declared homogeneity degree symbolically. DB02 and DB06 source-witness comparisons are exact symbolic checks. H01, H12, and HX01 use exact generator relations.

## Reproduction and interpretation

Run from the repository root with:

```bash
.venv/bin/python3.12 docs/research/qwen35-external-teacher-2026-09-25/supplementary-retention-sentinel/freeze_supplementary_retention.py
```

This preparation is CPU-only. It does not open old numeric-dev prompt text, current evaluation answers, near-transfer/fresh2 generation outputs, or second-seed outputs. The artifact selection uses prior base outcomes, and all selected configurations have already appeared in model development. Any result is therefore descriptive, result-informed retention evidence only.
