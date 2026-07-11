# EXP-LOCAL-005 — deterministic bound-constrained DFO-LS

This experiment challenges the current local winner with DFO-LS 1.6.5, a
derivative-free interpolation trust-region method for nonlinear least squares.
It is an experiment-local comparator, not a production dependency.

## Pre-registered applicability decision

- MINPACK `hybrd`/`hybrj` implements Powell's hybrid root method only for `n`
  equations in `n` variables and has no native box constraints. It is therefore
  killed before benchmarking because GeoTarget also has overdetermined systems
  and finite bounds.
- LeastSquaresOptim.jl 0.8.10 supports square/overdetermined least squares and
  bounds. Its Dogleg implementation first computes an unconstrained dogleg step
  and clips that step to the box. It remains a viable later comparator, but is
  not this wave's candidate.
- DFO-LS 1.6.5 accepts an arbitrary residual vector, never evaluates outside
  native bounds, exposes `maxfun`, and uses a deterministic coordinate
  interpolation set when random initialization is disabled. It applies to the
  complete solver-lab corpus without identity routing.

Primary/official sources checked on 2026-07-12:

- MINPACK `hybrj`: https://fortran-lang.github.io/minpack/proc/hybrj.html
- LeastSquaresOptim source and API:
  https://github.com/matthieugomez/LeastSquaresOptim.jl
- DFO-LS 1.6.5 user guide:
  https://numericalalgorithmsgroup.github.io/dfols/build/html/userguide.html
- DFO-LS version history:
  https://numericalalgorithmsgroup.github.io/dfols/build/html/history.html

## Fixed candidate

- midpoint/half-range variable normalization to `[-1, 1]`;
- native non-relaxable DFO-LS bounds;
- declared residual scales;
- `n + 1` deterministic coordinate interpolation points;
- no random directions, parallel initialization, noise mode, or restarts;
- `rhobeg=1e-1`, `rhoend=1e-12`, squared-residual objective threshold `1e-24`;
- 1,999 DFO-LS evaluations plus one reserved common endpoint screen;
- solution flags are diagnostic only; finite/bounds/semantics/scaled-residual
  screening alone sets `reported_accepted`;
- every opaque Julia residual callback is counted independently of DFO-LS.

## Environment and tests

```bash
uv sync --project research/experiments/EXP-LOCAL-005/python \
  --python 3.12.11 --frozen
julia --project=research/experiments/EXP-LOCAL-005 -e \
  'using Pkg; Pkg.instantiate()'
env JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 julia --startup-file=no --history-file=no \
  --project=research/experiments/EXP-LOCAL-005 \
  research/experiments/EXP-LOCAL-005/test/runtests.jl
```

## T0/T1 runner and outer case sharding

Wall time includes Python interoperability and is diagnostic. Observed opaque
residual callbacks are the primary matched-work measure. To use physical cores,
launch independent serial processes over case shards; do not add threads inside
a case.

```bash
env JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 julia --startup-file=no --history-file=no \
  --project=research/experiments/EXP-LOCAL-005 \
  research/experiments/EXP-LOCAL-005/run.jl \
  --suite=t0 --prefixes=2,4,8 --shard-index=0 --shard-count=1
```

For multiple processes choose `shard-count <= case count`, and assign each
zero-based shard index exactly once. Artifacts contain the modulo rule and shard
metadata. There is intentionally no permanent merge service.
