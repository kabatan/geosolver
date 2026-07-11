# EXP-LOCAL-004 local globalization comparators

This experiment-local adapter exposes pinned NonlinearSolve 4.20.2
`TrustRegion` (`NLS-TR`) and `LevenbergMarquardt` (`NLS-LM`) as truth-blind
solver-lab variants scored by the common schema-v2 assessor. Both use midpoint/half-range coordinates, declared
residual scaling, central finite differences, and an external hard callback
cap. Library return codes are diagnostics; the shared solver-lab assessor owns
endpoint qualification.

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

The frozen T0 decision is in `t0-decision.json`. Run the representative
nine-case T1 screen with only the three controls and the promoted NLS-TR
candidate:

```console
julia +1.12.6 --startup-file=no --history-file=no \
  --project=research/experiments/EXP-LOCAL-002 \
  research/experiments/EXP-LOCAL-004/run_t0.jl --suite=t1 \
  --output=benchmarks/results/raw/exp-local-004-t1-linux.json
```
