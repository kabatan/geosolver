# NULLSPACE_LOW_HEIGHT_WITNESS_TRANSPORT D0

## Hypothesis

A numerically valid witness on a positive-dimensional source component may be
hard to exactify only because its free coordinate has accidental high height.
Without using target values or expected answers, a stable Jacobian nullspace can
select a free chart.  Low-denominator rational slices in that chart, followed
by range Newton on the dependent coordinate, can preserve the source residual
while producing lower-degree/lower-height coordinate descriptors.

## Disposable mechanism

The two-variable D0 forms `J'J` by finite differences and uses its smallest
eigenvector only when the numerical rank ratio is at most `1e-8`.  The largest
nullspace component selects the free coordinate; this also chooses the stronger
dependent Jacobian column.  Up to 25 rational slices are enumerated from bounded
continued-fraction approximants and nearby low-denominator fractions.  The free
coordinate remains fixed while least-squares range Newton reconverges the other
coordinate.

The first 75 IID/Cauchy proposals are identical in control and candidate.  The
transport replaces only the last 25.  When the rank gate rejects a full-rank or
numerically unsupported system, those 25 proposals revert to the same baseline.

No geometry, corpus, formal result, runtime manifest/result, scorer, truth, case
ID, target, or expected answer is read.  Generated scoring may inspect the
synthetic source equation only after proposal generation.

## D0

Five synthetic families, 32 scenarios, four residual-row representations, and
two arms produce 1,280 traces on CPU15.  The primary positive-dimensional
families all improve exact-recognizable witness rate:

- affine: `0.00000 -> 0.96875`;
- curved rational slice: `0.34375 -> 1.00000`;
- singular narrow guard: `0.00000 -> 1.00000`.

The irrational-only safety family improves `0.06250 -> 1.00000` through a
rational free coordinate plus the unchanged quadratic dependent coordinate.
The isolated full-rank family never activates and reproduces fallback exactly.

Shared baseline mismatch, invalid residual/guard acceptance, fallback mismatch,
and row permutation/scale/rotation invariance failure are all zero.

## Decision

**ADVANCE from synthetic D0.**  This is a mechanism handoff, not evidence of a
development-score improvement.  The next experiment should connect the same
rank gate and rational-slice proposals to an existing source-only proof replay;
the ordinary numerical lane must retain at least 75%.  Do not tune denominator,
rank threshold, or slice radius on case outcomes.
