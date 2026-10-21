# Fresh4 projection-bridge evaluation inputs

## Purpose and status

This directory freezes six CPU-generated English numerical inputs: two each
for H03, H04, and H14. They are exploratory candidate evaluation inputs for a
possible decomposed projection-bridge leave-one-ID-out comparison. The same
target IDs and construction family were examined earlier, so fresh4 is not an
untouched confirmatory holdout and must not be described as one.

No model was run. No LOO model answer or condition score was opened. The
answer key, exact values, parameters, and construction branch conditions are
grader-only data; `eval_jobs.json` contains only the approved English
instruction and numerical problem text.

## Construction and exclusions

`freeze_fresh4.py` replays the fixed, ordered tuples in `CANDIDATE_ORDER`
through the canonical exact generators. It reuses the separate exact branch
checkers from fresh3 and checks the generator's exact answer against the
independent shape-answer formula. The H04 checks also record that acuteness
makes `AM^2 - (BC/2)^2` strictly positive, so the relevant canceled factor is
nonzero on the generated branch.

Each selected item is checked against the same ID's complete givens and
problem text in fresh1, fresh2, and fresh3; against the same ID's v0-v3
training givens, problem signatures, and text; and against the original finite
projection of visible givens. The freezer accesses only the v0-v3 problem,
variant, and givens fields for those collision checks. It does not copy a
target proof into a model prompt. Candidate parameter tuples are fixed in
advance and recorded in `construction_checks.json` and `hashes.json`.

All jobs use the approved numeric English templates and standard relation,
proof, and application instruction. The exact answer and branch data are
stored separately in `answer_key.json` and `construction_checks.json`.

## Possible use

If a leave-one-ID-out audit supports a repeatable missing-bridge diagnosis,
these six jobs may be used as one exploratory evaluation slice for a matched
comparison of decomposed bridge teaching against ordinary complete solutions.
Keep the source IDs and numbers matched, balance example and token budgets,
and keep fresh4 keys outside every model input. Do not use previous target
proofs as teacher examples. Report H03, H04, and H14 separately and treat two
instances per target as a small repeated-numeric diagnostic, not independent
geometry-family replication. Lock the model, decoding, scoring rules, and
comparison plan before evaluation.

## Reproduction and integrity

From the repository root, reproduce the CPU-only freeze with:

```bash
.venv/bin/python3.12 docs/research/qwen35-external-teacher-2026-09-25/heldout-near-transfer/followup-fresh4/freeze_fresh4.py
```

The freezer writes only this directory. `hashes.json` records SHA-256 digests
for the generated inputs, grader-only artifacts, protocol, freezer, and
source artifacts. Do not regenerate after evaluation starts; preserve this
directory as the frozen fresh4 input.
