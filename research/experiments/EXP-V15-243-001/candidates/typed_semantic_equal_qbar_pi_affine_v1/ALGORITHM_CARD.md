# TYPED_SEMANTIC_EQUAL_QBAR_PI_AFFINE_V1

- Hypothesis: two current exact-replay failures are representation failures, not numerical failures. A closed, equality-only semantic domain for `Q`, `Qbar`, `pi`-affine expressions, and direct exact angles can recover them without weakening proof-bearing replay.
- Mechanism: run the unmodified exact fallback first with at least 75% of the local budget. Only when its exact failure class matches and a source-only scanner proves the relation closed, rerun the copied QQBar worker with root subtraction replaced by typed equality. The side route receives at most 25%.
- Repair A: permit only the canonical root-equality embedding `Q -> Qbar`. It is unavailable to arithmetic, mutation, ordering, sign, approximation, or unknown types.
- Safety/fallback: source, coordinates, guards, branches, raw target, minimal polynomial, ordinal, isolator, and numeric parity remain required. Side rejection, error, or timeout returns the baseline mapping by object identity. Canonical source replay is never bypassed.
- Routing features: source DAG operators, exact leaf types, relation root, angle domain/unit, DAG size, and baseline failure class only. No problem/family ID, truth, target value, or case result is read.
- Nearest prior mechanism: generic exact QQBar replay. Reopen gate is satisfied by the aggregate evidence that Repair A raises anonymous eligible coverage from 6 attempts/1 cluster to 10 attempts/2 clusters while leaving unknown and out-of-route Qbar equality rejected.
- D0: 7/7 positive, 17/17 negative/near-miss, 5/5 metamorphic; executable Julia QQBar affine replay and containment tests pass.
- Formal status: not run in this lane. Root benchmark owner must perform all corpus/scorer/truth evaluation.

## Repair-A no-gain disposition

Root's aggregate-only debug ran the connector once and the side once without
exception, but returned the byte-identical baseline rejection `scalar is not
an exact angle expression`.  The source-AST occurrence scanner then covered
synthetic and explicit add/subtraction, exact integer angle scaling, scalar
comparison and lowered `Assume*`, and `min/max`, which are every generic
`as_angle` entry in the current extended worker.  On that source it found
three Repair-A-selected relation roots, zero selected rejecting roots, and
zero rejecting occurrences in construction, constraint operands/synthetic
roots, guards, bounds, or the raw answer.

Thus the eligible equalities were unrelated to the actual runtime rejection,
and no source-generic exact typed replacement was identified.  Repair B is
`STOP_NO_EXACT_REJECTING_OCCURRENCE`; no threshold, radius, seed, or budget
tuning is permitted.  Reopen only if a source-only trace identifies the
rejecting semantic occurrence and supplies an exact, typed, domain-preserving
replacement.  No individual debug row, scorer, truth, 98-case, validation, or
sealed artifact was accessed in this analysis.
