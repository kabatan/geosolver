# EXP-LOCAL-015 — rank/precision endpoint rescue

Status: **pre-outcome implementation and conformance phase**.

This experiment changes one axis: hard local convergence after the frozen E4
pipeline reaches a semantics-valid but numerically unresolved endpoint.  Such
an endpoint is retained only as a `RefinementSeed`; it is never an answer.

The wave separates a fixed-512 reference diagnostic, an adaptive-precision
full-rank candidate, a stable one-dimensional weak-bracket candidate, equal
work isotropic/no-bracket controls, and unchanged E4.  Every promoted endpoint
must still pass the existing compiled-512 refinement, independent reference-768
replay and `1e-100` gates.

Before any performance outcome, the implementation must pass the primary
source trace, minimum-success fixtures, typed break conditions, exact weighted
work closure, mechanism activation, and signed-permutation/orthogonal replicas.
The fixed-512 reference is explicitly nonpromotional because its complete d8
stencil cannot fit the 600 weighted-work budget.

T0 will use a new parameterized open-development corpus rather than tuning the
already observed Stage-D misses.  It includes rotated ill-conditioned linear
systems, clustered simple-root weak-lane systems, and stationary-nonroot,
multiple-root, manifold and semantic-crossing controls.  Gold/root material is
held only by the assessor.  Candidate interfaces receive no family, case,
plugin, primitive, target or Gold identity.

No Core/public API, production route, holdout input or completion claim is
changed in this phase.

## Formal T0 invocation

`run_t0.jl` is not a self-contained shebang program.  Julia 1.12.6, JSON3 and
its frozen dependency graph come from `EXP-LOCAL-002`, so every conformance and
outcome run must use the explicit project below (from the repository root):

```bash
JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  taskset -c 0 julia --startup-file=no \
  --project=research/experiments/EXP-LOCAL-002 \
  research/experiments/EXP-LOCAL-015/run_t0.jl \
  --case-index 1 \
  --registration research/experiments/EXP-LOCAL-015/preregistration-t0-r2.json \
  --output artifacts/raw/EXP-LOCAL-015/case-001.json
```

Formal execution uses one case per process and at most the detected physical
core count (capped at 16 for this preregistration).  Each process is pinned to
one physical core; SMT siblings are not used.  The raw shard records and the
scorer checks Julia/BLAS/solver thread counts, the active Project/Manifest
hashes, clean revision, corpus checksum, registration hash, and independent
physical callback ledgers.  A direct `./run_t0.jl` invocation is not valid.

The original `preregistration-t0.json` campaign stopped before aggregation due
to a runner result-contract defect and is permanently invalidated by
`invalid-run-cb81114.json`.  Revision r2 adds the missing typed-false activation
fields and an all-safety-path fixture; it does not change candidate mechanics,
parameters, corpus, or decision gates.

Formal aggregation uses the locked Python 3.12.11 environment; importing the
module for unit tests remains version-independent:

```bash
python/.venv/bin/python \
  research/experiments/EXP-LOCAL-015/aggregate_t0.py \
  --output artifacts/raw/EXP-LOCAL-015/aggregate.json \
  artifacts/raw/EXP-LOCAL-015/case-*.json
```
