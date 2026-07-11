# EXP-LOCAL-004 local globalization comparators

This experiment-local adapter exposes pinned NonlinearSolve 4.20.2
`TrustRegion` (`NLS-TR`) and `LevenbergMarquardt` (`NLS-LM`) as truth-blind
solver-lab variants scored by the common schema-v2 assessor. Both use midpoint/half-range coordinates, declared
residual scaling, central finite differences, and an external hard callback
cap. Library return codes are convergence diagnostics only. Reported acceptance
uses the general truth-blind screen: a finite endpoint inside its declared
bounds, a valid public numeric semantic state (including guards/domain/branch),
and scaled residual L-infinity norm at most `1e-12`. The screening evaluation
uses the same counted callback budget; the shared solver-lab assessor still
owns independent endpoint qualification.

The LM comparator explicitly preserves NonlinearSolve's geodesic acceleration
(`step=0.1`, `alpha=0.75`); these extra residual calls are included by the
adapter counter even though they are not represented by `stats.nf`.

NonlinearSolve applies its logistic unconstraining transform because these two
algorithms do not natively implement box bounds. `NLS-TR` therefore names the
library algorithm and is not described as a native projected/bound-aware trust
region method.

The dependency lock is reused unchanged from `EXP-LOCAL-002`:

```console
julia +1.12.6 --startup-file=no --history-file=no \
  --project=research/experiments/EXP-LOCAL-002 \
  research/experiments/EXP-LOCAL-004/test/runtests.jl
```

Run the five-case T0 comparison (three Core controls, both external candidates,
and the native scale-aware safeguarded LM candidate):

```console
julia +1.12.6 --startup-file=no --history-file=no \
  --project=research/experiments/EXP-LOCAL-002 \
  research/experiments/EXP-LOCAL-004/run_t0.jl
```

The frozen T0 and T1 decisions are in `t0-decision.json` and
`t1-decision.json`. Run the representative
nine-case T1 screen with only the three controls and the promoted NLS-TR
candidate:

```console
julia +1.12.6 --startup-file=no --history-file=no \
  --project=research/experiments/EXP-LOCAL-002 \
  research/experiments/EXP-LOCAL-004/run_t0.jl --suite=t1 \
  --output=benchmarks/results/raw/exp-local-004-t1-linux.json
```

## Frozen T2 generalization screen

T2 reuses the open `DevelopmentLocal002` generator but does not read its
historical input manifest, routing amendment, or any U1--U4 holdout material.
It materializes the fixed 8-family x 6-instance development corpus with 32
saved starts per instance once, then compares only `prod-tol-120x600`,
`prod-options-250x2000`, and the T1 survivor `NLS-TR` at prefixes 8/16/32.
Every attempt remains subject to the common runner hard cap of 2000 callbacks.

First freeze the new input manifest. Creation refuses to overwrite any
existing path; later runs regenerate the development material in memory and
require a byte-for-byte match, so either input or source tampering is rejected.
Run preparation and execution with one Julia thread and one BLAS thread:

```console
JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  julia +1.12.6 --startup-file=no --history-file=no \
  --project=research/experiments/EXP-LOCAL-002 \
  research/experiments/EXP-LOCAL-004/prepare_t2.jl

JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  julia +1.12.6 --startup-file=no --history-file=no \
  --project=research/experiments/EXP-LOCAL-002 \
  research/experiments/EXP-LOCAL-004/run_t2.jl
```

The tracked `t2-input-manifest.json` is development-only and explicitly
reserves U1, U2, U3, and U4 for later blind validation. Its source hash table
includes the benchmark module entry point, every included benchmark family,
the legacy generator modules, the shared scorer, and the candidate adapter.
