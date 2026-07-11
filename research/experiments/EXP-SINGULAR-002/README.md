# EXP-SINGULAR-002: invariant singular-root successor

Status: **preregistered design plus static diagnostic seam; no input or outcome
has been materialized**.

This is a new experiment.  Frozen `EXP-SINGULAR-001` and its S4 result are
inputs to the design rationale only; this directory does not change, reinterpret,
or rerun them.

## Hypothesis

S4 recovered 11/15 eligible endpoints with no S4 false promotion, but its
shared candidate/control final decision failed on the orthogonal representation
of four groups.  A successor must therefore change the shared numerical model,
not merely finite-difference acquisition or a named failing case.

The candidate represents variable and residual errors in declared normalized
metrics.  It uses spectral uncertainty from `J_h-J_(h/2)`, Weyl singular-value
intervals, left/right null projectors, and a projected Hessian tensor
`T[alpha,i,j]`.  The flattened map

```text
Sym^2(N_right) -> N_left
```

is diagnostic only: its full row rank does not imply a usable rank-one step.
Finite candidate lines instead come from the uncertainty-separated simple
eigenlines of

```text
K[i,j] = sum(T[alpha,i,k] * T[alpha,j,k], alpha, k).
```

For every such line whose paper-style contraction
`B(q)[alpha,j]=sum(T[alpha,i,j]*q[i],i)` is Weyl-full-rank at both radii and
precisions, both signs are evaluated.  All resulting canonical endpoints must
agree before their covariant barycenter may enter one common finite safeguard.
Degenerate `K`, no valid `B(q)`, or endpoint disagreement returns unknown.

All norms used for routing, stopping, corrections, and error evidence are
Euclidean norms in the declared metrics.  No coefficient vector tied to an
arbitrary SVD null basis, eigenvalue tie-break, or infinite eigenspace
enumeration may choose a correction direction.

The full frozen protocol is in
[`preregistration.json`](preregistration.json).  The code in `src/` implements
only the invariant diagnostic primitives needed for pre-input falsification.
It deliberately contains no corpus generator, Gold reader, materializer,
outcome runner, production adapter, or solver route.  `Manifest.toml` pins only
the standard-library test environment; it contains no algorithm dependency.
The pre-input link from the S4 counterexample to this replacement is recorded
in [`DESIGN_AUDIT.md`](DESIGN_AUDIT.md).

## Review barrier

The first root review approved the Jacobian/Weyl/projector diagnostic seam and
rejected the earlier `Sym^2` tensor-Gauss-Newton correction as mathematically
insufficient and non-finite under degeneracy.  Revision A1 implements the
finite `K`/`B(q)` static seam above.  The second root review found its
all-line/all-sign paper step, endpoint reconciliation, barycenter, and common
safeguard mathematically coherent with Algorithm 1 of arXiv:2305.10803 and
approved the map for preregistration.

That approval is not efficacy evidence, permission to open a holdout, or a
product decision.  This checkpoint still contains no input generator,
candidate trajectory, Gold artifact, outcome benchmark, or solver route.

Changing a threshold or map after viewing case outcomes requires a new
experiment id.  Static unit tests are not outcome evidence.

## Static checks

Run with the pinned Julia toolchain and one thread:

```bash
JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  julia +1.12.6 --startup-file=no --history-file=no \
  --project=research/experiments/EXP-SINGULAR-002 \
  -e 'using Pkg; Pkg.test()'
```
