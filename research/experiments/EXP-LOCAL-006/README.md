# EXP-LOCAL-006 — native-bound SciPy exact TRF comparator

This experiment-local candidate evaluates SciPy 1.18.0's official
`scipy.optimize.least_squares(method="trf", tr_solver="exact")` implementation
as a general dense nonlinear least-squares comparator. It is not a production
dependency and it does not edit or connect Core.

## Fixed candidate contract

- Variables use the declared finite box midpoint and half-range to normalize to
  `[-1, 1]`; SciPy receives that box as its native `bounds`. This is materially
  different from EXP-LOCAL-004's NonlinearSolve TRF comparator, whose library
  path used logistic unconstraining because that algorithm did not natively
  support bounds.
- Residuals are divided by their declared residual scales before SciPy sees
  them. The dense subproblem is fixed to `tr_solver="exact"`, linear loss, and
  explicit `ftol=xtol=gtol=1e-12`, `x_scale=1.0`.
- The Jacobian is a candidate-owned Julia callback. It prefers central finite
  differences, retains a valid one-sided fallback, and retries semantic-invalid,
  nonfinite/domain-invalid, or throwing probes at `h/2` for at most eight
  backoffs. Every attempted residual/Jacobian probe is charged to the same Julia
  truth-blind callback ledger.
- Each attempt has a 600-callback candidate hard cap: at most 599 callbacks are
  available to SciPy and exactly one is reserved for the common endpoint screen.
  The screen alone determines `reported_accepted`: finite endpoint, declared
  bounds, public semantic validity, and declared-scaled residual L-infinity at
  most `1e-12`. SciPy's `success`, status, message, `nfev`, and `njev` remain
  diagnostics only.
- Candidate and Python bridge receive no case/family identity, saved-start
  matrix, Gold configuration, or Gold target. There is no identity routing.
  Those data remain exclusively in the outer runner/scorer.

Official API reference:
https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.optimize.least_squares.html

## Negative-result non-repetition contract

This study does not reopen NEG-016 by porting the failed EXP-LOCAL-004
configuration. The candidate is a separate official SciPy TRF implementation
with native normalized bounds and its own guarded derivative callback. T0 is
only a kill screen; it cannot authorize a native port, product routing, or a
general-champion claim. Any later promotion still requires a fresh registered
study and the endpoint-correction/high-precision and safety gates stated by
NEG-016.

This study also does not repeat NEG-006. It performs no up-front rank estimate,
condition estimate, SVD, or diagnostic solve and has no LM/TR routing predicate.
The guarded Jacobian probes are solver-requested derivative work and are fully
charged; they are not a separate warm routing tax. Reopening rank/condition
routing would require solver-native state and its own preregistered gate.

## Frozen T0 survive/kill gate

The implementation and this gate are committed before any clean T0 outcome is
created. The earlier one-case, 600-callback dirty smoke checked wiring only; it
is non-gating, is excluded from every decision artifact, and cannot tune this
candidate.

At the final 4,800-callback case threshold, `SCIPY-TRF-EXACT` advances to T1 if
and only if all of the following hold against `prod-tol-120x600` under the
common assessor:

- accepted-endpoint safety violations, evaluation-count mismatches, runner-cap
  violations, and unhandled exceptions are all zero;
- aggregate assessor-qualified target count and safe-full case count are both
  noninferior, and at least one is strictly higher;
- observed callback work, including attempt-boundary overshoot, is at most
  1.2 times the control;
- qualified target count does not decrease in any of Curved, NearRank,
  Tangent, or the two-case Warped stratum.

Failure of any condition kills this frozen SciPy configuration at T0. Passing
only authorizes the predeclared representative-nine-case T1 comparison; it
does not authorize a native port, production connection, or T2 promotion.
There are no tuning rounds in EXP-LOCAL-006.

## Locked environment and targeted tests

Python 3.12.11 and SciPy 1.18.0 are locked by `python/uv.lock`; PythonCall is
forced to that exact experiment-local virtual environment.

```bash
uv sync --project research/experiments/EXP-LOCAL-006/python \
  --python 3.12.11 --frozen
julia --project=research/experiments/EXP-LOCAL-006 -e \
  'using Pkg; Pkg.instantiate()'
env JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 julia --startup-file=no --history-file=no \
  --project=research/experiments/EXP-LOCAL-006 \
  research/experiments/EXP-LOCAL-006/test/runtests.jl
```

## T0 case-cumulative callback prefixes

For each `(case, variant)`, the runner consumes the same paired saved-start
order once. It snapshots after the first completed attempt whose cumulative
observed callbacks reach 600, 1200, 2400, and 4800. An attempt is never split;
the artifact records threshold overshoot and the crossing start index. Prefixes
are not rerun, so later prefixes are true extensions of the same stream.
The per-attempt candidate hard cap, outer runner defensive cap, and cumulative
case thresholds are separate artifact fields.

The formal runner also rejects a dirty worktree, verifies every replay
checksum before launching a shard, and fills schema-v2 suffix-stable work from
the complete single stream rather than from a truncated prefix.

Start with the killable short T0 prefix; do not run full T1 in this wave:

```bash
env JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 julia --startup-file=no --history-file=no \
  --project=research/experiments/EXP-LOCAL-006 \
  research/experiments/EXP-LOCAL-006/run_t0.jl \
  --callback-prefixes=600 --shard-index=0 --shard-count=1
```

For outer parallelism, launch each zero-based case shard exactly once. Each
process and every native numerical library must remain single-threaded. No T1
runner or T1 result is created by this implementation.
