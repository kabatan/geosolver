# Fresh3 numeric job set

## Purpose and status

This directory freezes a third deterministic numeric problem set for a later
50-row diverse-source teacher comparison. It contains the same nine source IDs
and evaluation roles as the existing `heldout-near-transfer` fresh1/fresh2
sets: five heldout-transfer targets (`H03`, `H04`, `H08`, `H14`, `H15`) and four
source-retention controls (`H01`, `H02`, `H07`, `H13`). It was prepared with
CPU-only exact arithmetic. No model was run and no evaluation output was read.

This is a **result-informed supplementary diagnostic**, created after seeing
that the untouched base had a low retention floor on the earlier four-item
retention slice. It is not a confirmatory transfer test, and fresh3 must not be
described as preregistered or independent of earlier result inspection. The
five target IDs and their transfer clusters are unchanged; the four retention
IDs are retained to make the later source comparison easier to interpret.

## Construction and checks

`freeze_fresh3.py` replays fixed parameter tuples through the canonical exact
generators in `benchmarks/humpty_configurations_v2/authoring/gen_variants.py`.
The generator's checked construction record and independent exact
shape-answer formula must agree for every item. Separate exact checkers
reconstruct the key geometric branches (including intersection order,
segment/ray membership, nondegeneracy, and the requested construction relation)
before any files are written.

The freezer checks every selected ID against all four canonical training
variants (`v0`-`v3`) and both earlier frozen numeric sets. It rejects any
collision in complete givens, canonical problem text, or approved English
problem text. It also checks that each ID's designated visible novelty value
is absent from the original variant values and that seeds differ from the
corresponding fresh1/fresh2 seeds. English text is rendered through the
approved numeric templates. The separate answer key is grader-only and is
absent from every model message.

## Reproduction

From the repository root:

```bash
.venv/bin/python3.12 docs/research/qwen35-external-teacher-2026-09-25/heldout-near-transfer/followup-fresh3/freeze_fresh3.py
```

The freezer writes only this directory. `hashes.json` records SHA-256 digests
for the job files, answer key, construction checks, protocol, freezer, and
source artifacts. Do not regenerate after evaluation begins; preserve this
directory as the frozen fresh3 input.

## Limits

Fresh3 is a small, deterministic set over the same nine configuration IDs and
lemmas as fresh1/fresh2, so the three sets are repeated numeric instances, not
independent geometry families. The retention subset has four items and is a
supplementary diagnostic. A later comparison must report its own training
composition and keep answer keys out of model inputs. No claim about model
performance follows from freezing these inputs.
