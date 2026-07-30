# EXP-STRUCT-001 metamorphic S0 evidence

Status: **generated truth-free safety screen passed; no formal outcome claim**.

## Tested transformations

- All 24 residual permutations and all 24 variable permutations of a four-block
  triangular graph preserved applicability, block sizes `(1,1,1,1)`, and the
  structural factor-work ratio `0.0625`.
- The full 24 × 24 cross product passed 576 equivalent-plan checks.
- All 36 residual/variable permutations of an irreducible three-cycle remained
  `irreducible` and baseline-only.
- Reordering independent construction bindings and replacing an alias with an
  equivalent repeated expression preserved extracted supports and the plan.

## Counterexamples and closure

- A construction forward reference previously risked dependency
  under-approximation. Value names that are neither prior bindings, variables,
  nor the scalar constants `pi/e` now make extraction fail closed. The worker
  sends such inputs through the exact frozen-worker passthrough.
- Proposal-factory exceptions, nonfinite points, wrong dimensions, duplicates,
  and empty accepted proposal sets now preserve the original endpoint stream.
- A generated proposal was admitted only when a fake original source replay
  accepted it. The overlay reported both source-replay and canonical-verifier
  bypass as false.

`failure-taxonomy.json` records ten observable classes and their fixed
baseline-safe disposition. None uses case identity, family, target, answer, or
known target count. `run_metamorphic_s0.py` reproduces the aggregate evidence;
no development score, formal screen, validation, sealed input, or truth record
was opened for this screen.

The common campaign `run_arm.py` dry contract also passed with lowercase arm
ID `exp-struct-001-btf-champion-overlay`, full 40-hex base commit, manifest-
relative `worker.py`, and the raw entrypoint SHA-256. This contract check
selected the screen24 manifest only to construct a non-executing plan; no
worker, scorer, or outcome run was started.
