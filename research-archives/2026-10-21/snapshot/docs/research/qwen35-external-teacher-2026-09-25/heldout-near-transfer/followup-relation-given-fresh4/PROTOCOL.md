# Relation-given proof diagnostic for fresh4

## Purpose and status

This directory contains six relation-given proof prompts paired to the six
fresh4 numerical inputs: two each for H03, H04, and H14. It is a diagnostic of
theorem execution after a common lemma is supplied. It does not measure
independent transfer or relation discovery, and it is not an untouched
confirmatory evaluation set.

Each job preserves its fresh4 `id`, `source_id`, numerical problem text, and
seed. The model message adds one general orthocenter-projection lemma and
requires a proof of any construction mapping, branch/order, sign, and
nonzero-factor conditions before numerical use. The addition does not name a
target-specific constructed point or provide target proof steps. Exact answers
and branch audits remain in grader-only files.

## Supplied lemma

In a nondegenerate triangle ABC, let H be the orthocenter and M the midpoint
of BC. If P is the orthogonal projection of H onto line AM, then the directed
vector identity

`(vector MP) dot (vector MA) = (BC/2)^2`

holds. Equivalently, `vector MP = ((BC/2)^2 / AM^2) vector MA`. The lemma
does not identify a problem-defined point as P or settle an intersection
branch. The model is asked to prove the necessary identification and branch
from each numerical problem's construction.

## Interpretation

Compare this diagnostic only against its paired fresh4 inputs under the same
evaluation settings. Success here means the model can use a supplied general
relation while still establishing the construction bridge and branch; it
does not show that it can discover the relation without help. Report H03,
H04, and H14 separately and do not treat two numerical instances per ID as
independent geometry families.

## Reproduction and integrity

From the repository root, reproduce the CPU-only freeze with:

```bash
.venv/bin/python3.12 docs/research/qwen35-external-teacher-2026-09-25/heldout-near-transfer/followup-relation-given-fresh4/freeze_relation_given_fresh4.py
```

The freezer reads only the fresh4 problem inputs, grader-only answer key,
construction checks, and their hash manifest. It writes only this directory.
It does not run a model or inspect model outputs or scores. `math_audit.json`
contains a coordinate proof of the supplied lemma and confirms that the
fresh4 construction checks remain separate from prompts. `hashes.json`
records the source and generated SHA-256 digests. Do not regenerate after
evaluation begins.
