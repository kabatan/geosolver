# EXP-LOCAL-001 pilot v0

Status: diagnostic; **not eligible for promotion**  
Runner commit: `b4c245e361096d354c0d20be82cfeb02e7d5a235`  
Toolchain: Julia 1.12.6, one Julia thread, OpenBLAS ILP64  
Starts: eight materialized starts per instance, paired across all variants

Variants isolate bounds-based variable normalization (`X`) and declared
residual scaling (`R`): `L0`, `LX`, `LR`, and `LXR`. The local algorithm,
finite-difference policy, launch set, bounds, tolerances and evaluation budget
are otherwise identical.

## Observations

- On the high-curvature chain, residual scaling changed internal candidate
  recovery from 2/8 to 8/8 and reduced median evaluations from 595 to 107–109.
- On the redundant system, variable normalization reduced median evaluations
  from 28 to 19 without changing recovery.
- On the near-tangent two-root system, variable normalization recovered both
  target values; the raw-coordinate variants recovered only one.
- The linear scale ladder was solved identically by all four variants. This is
  a useful counterexample to any claim that scaling always improves a problem.
- Near-rank-deficient and warped multi-root systems produced residual-qualified
  internal candidates whose targets did not match Gold within `1e-6`. Thus a
  Float64 residual gate is not a validated answer gate under poor conditioning.
  Target-aware error estimation/high-precision validation must remain separate.
- None of the variants recovered the four-target warped family at this launch
  count. Global discovery and/or a stronger local singular lane is still needed.

## Decision

This micro-run supports continuing the preregistered factorial experiment but
does not promote a default. It contains one instance per family and eight
starts, lacks confidence intervals, and intentionally does not cover S4/S6.
The strongest immediate engineering consequence is to keep residual-qualified
candidates distinct from `ProvisionalAnswer`, exactly as the public assurance
model requires.
