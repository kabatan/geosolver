# EXP-MULTITARGET-001 metamorphic S0 evidence

## Counterexample and correction

The first post-answer prototype used the frozen worker's pairwise normalized
target distance, `abs(a-b) / max(abs(a), abs(b), 1)`. A reversible target
translation changed this ratio and could therefore change the order of the
finite HP tranche. The policy now uses `abs(a-b)` before its existing unit-range
normalization. Translation cancels in the difference and every nonzero affine
scale contributes the same positive factor, so ordering is preserved.

This correction affects scheduling only. Original-source replay, HP authority,
canonical validation, and final exact descriptor keys remain frozen.

## Truth-free generated panel

`run_metamorphic_s0.py` constructs anonymous endpoints, residual vectors,
provisional targets, and generated authority descriptors. It uses no corpus,
Gold target, case ID, family, or known answer count.

- Four non-identity reversible target affine transformations produced zero
  trace or descriptor-set mismatches.
- All six permutations of three variables and all six permutations of three
  residual rows produced zero trace or descriptor-set mismatches.
- Two distinct configurations with the same provisional target both reached
  authority and produced two distinct generated descriptors; suppression was
  false.
- A virtual-clock deadline test consumed the full admitted attempts
  `[18, 4, 6]` seconds, stopped at 28 of 30 seconds, and preserved the two-second
  finalization reserve without sub-three-second attempts.
- AST inspection covered 27 scheduler/overlay conditionals and found zero
  conditions referring to case ID, problem ID, family, Gold target, known
  target count, answer count, or benchmark outcome.

## Boundary

This is S0 mechanism evidence, not a claim of real-corpus recall improvement.
No formal screen, development truth, scorer, validation, or sealed data was
used. The common arm entrypoint hash remains the SHA-256 of `worker.py`; the
transitive tail mechanism digest is recorded by every dry plan.
